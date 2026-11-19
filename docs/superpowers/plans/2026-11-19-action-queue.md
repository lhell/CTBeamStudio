# Action Queue — Implementation Plan

> **For agentic workers:** work task by task, tests first, in the conda env
> `ct-viewer`. Stop for approval after Task 1.

**Goal:** Long-running UI actions append to a per-session FIFO queue and run off
the Streamlit script thread, so a second click never freezes the page or
discards a finished result.

**Architecture:** `action_queue.py` is a Streamlit-free registry with one daemon
worker per session (same shape as `background_load.py`). `actions.py` turns the
clicked widget values into frozen `run()` closures, and applies finished
results to session state on the main thread. `main()` drains before any widget
is created; a sidebar fragment polls while work is active only.

**Tech Stack:** Python `threading`, Streamlit 1.39.1, pytest, existing backend
loaders / `forward_project`.

**Spec:** `docs/superpowers/specs/2026-11-19-action-queue-design.md`

**Ledger:** T-109 in `docs/plan.md`

## Global constraints

- No `streamlit` import in `action_queue.py`; the worker never calls `st.*`,
  never reads session state, never applies results.
- Session state is written only from the main script thread; `apply` runs
  inside `main()` **before** `render_sidebar()`.
- One worker per session; one item at a time; FIFO.
- Running jobs are never killed. Cancel = drop pending, discard a running
  result.
- Inputs are snapshotted at click time (paths, selections, geometry, energy,
  volume reference). Later widget changes must not alter a queued job.
- No new `AppTest` runs: the existing module-scoped instance in
  `tests/integration/test_ui_smoke.py` is reused.
- Suite must stay at **0 skipped**; update the test bar in `AGENTS.md` when the
  count changes.
- English UI copy; German ledger entry; conventional commits
  (`feat(actions): …`).

## Task 1 — Plan checkpoint

**Files:** none.

- [x] Present this plan and the spec; wait for approval.
- [x] UX decided (Nov 19, 2026): Option A — every action button enqueues
      immediately; no checkbox multi-select.

## Task 2 — `action_queue.py` + unit tests

**Files:**
- Create `src/visualization/action_queue.py`
- Create `tests/unit/test_action_queue.py`

**Interfaces:**
- `QueueItem`: `id`, `label`, `kind`, `status` (`pending|running|done|failed|cancelled`),
  `run`, `apply` (main-thread consumer, never called by the worker), `result`,
  `error`, `created_at`, `started_at`, `finished_at`,
  `progress: tuple[int, int] | None`, `applied`.
- `enqueue(session: str, item: QueueItem) -> str`
- `snapshot(session: str) -> list[QueueItem]` (copies; no live mutation leaks)
- `drain_results(session: str) -> list[QueueItem]` (done/failed items, exactly
  once; remaining done items leave the snapshot as "applied")
- `cancel(session: str, item_id: str) -> bool`
- `set_progress(session: str, item_id: str, current: int, total: int) -> None`
- `clear_finished(session: str)`, `reset_queue(session: str)`,
  `clear_registry()` (tests only)
- `is_busy(session: str) -> bool` (any `pending`/`running` item) — the mount
  condition for the poller.
- `run_now(session: str, item: QueueItem) -> str` — synchronous execution on
  the calling thread; the integration-test seam (same start/finish recording).

- [x] Write failing tests first:
  - FIFO: A then B → A is `running` while B is still `pending`.
  - One at a time: B's worker starts only after A finishes (gated by an
    `Event`).
  - Success stores the result and reaches `done`.
  - Exception stores the error, reaches `failed`, raises nothing.
  - `drain_results` returns each finished item exactly once.
  - `cancel` removes a pending item and it never runs.
  - Cancel of a running item is refused and it still completes.
  - Progress snapshots are visible and monotonic.
  - Two sessions do not see each other's items.
  - `snapshot` of an unknown session is `[]`.
- [x] Implement with one `threading.Lock` and a per-session worker thread
      (`daemon=True`), started lazily.
- [x] Run `python -m pytest tests/unit/test_action_queue.py -q -rs`.
      **13 passed**, 8 repeat runs stable, flake8/black/isort clean.

## Task 3 — `actions.py`: specs, snapshots, apply

**Files:**
- Create `src/visualization/actions.py`
- Create `tests/unit/test_actions.py`

**Interfaces:**
- `QueueItem` carries `apply(result, state) -> str | None`; there is no separate
  `ActionSpec` (the item *is* the spec).
- `enqueue_series(session, files, series) -> str`
- `enqueue_measurements(session, path, selection, axis_order, geometry) -> str`
- `enqueue_dummy_measurement(session) -> str`
- `enqueue_forward_projection(session, volume, geometry, *, proj_indices, row_indices, col_indices, energy_kev, use_cuda) -> str`
- Each `enqueue_*` builds the item, attaches the progress sink, enqueues,
  toasts `Added to queue`, and returns the item id.
- `drain_action_results(session, state=None, notify=None) -> list[QueueItem]`
  (main thread; `state` defaults to `st.session_state`, `notify` to a logger;
  the app passes `streamlit_notify` explicitly).
- `streamlit_notify(level, message)` — `st.error` / `st.toast`; only called
  from the app, never from a worker.
- `session_token() -> str` (uuid stored in `session_state`)
- `inline_mode() -> bool` — the integration-test seam (`actions_inline` in
  session state); when true, `enqueue_*` runs and applies synchronously.
- Pure `series_file_list(selected_series, n_slices, data_path)`.

- [x] Pure part first: `series_file_list(...)` — no `st`, unit tested.
      (The forward-projection indices are resolved at the click site with the
      existing `resolve_selection`; no new resolver was needed.)
- [x] `apply` functions take a dict-like state so tests use a plain `dict`:
      - series → `volume`, `series`, `loaded_files`, pop slice keys, save cache
      - measurements → `sinogram`
      - dummy → the existing trio + sample presets + `clear_geometry_edit_state`
      - FP → `forward_projection`
- [x] Tests: apply writes the expected keys; dummy seeds `all` presets; drain
      applies once, reports failures, and reports a failing apply; inline
      submit runs on the calling thread.
- [x] Run the module's tests: **12 passed** (25 with the queue module),
      flake8/black/isort clean.

## Task 4 — Wire Load Series

**Files:** `src/visualization/sidebar.py`

- [x] Replace the inline `load_volume_cached` block with `enqueue_series`.
- [x] Delete the `st.progress`/`st.empty` writes from the worker path; forward
      the existing `_progress_callback` to `set_progress`.
- [x] Keep `save_last_loaded` in `apply`, not in the worker.
- [x] No `st.rerun()` after enqueue; the queue fragment reruns on completion.

## Task 5 — Wire Load Measurements

**Files:** `src/visualization/projection_panel.py`

- [x] Replace the inline `load_sinogram` + progress elements with
      `enqueue_measurements`.
- [x] Keep "Enter a path first" / "Path not found" validation synchronous —
      they are cheap and belong to the click.
- [x] Keep the axis-order re-read path synchronous (it is fast for an
      already-loaded file) and document why.
- [x] After a queued load finishes, the reoriented data appears on the next
      poll rerun.

## Task 6 — Wire dummy measurement and forward projection

**Files:** `src/visualization/projection_panel.py`

- [x] Dummy: enqueue `create_dummy_measured_sinogram`; `apply` keeps the exact
      current set of keys and preset resets.
- [x] FP: enqueue `prepare_projection_volume` + `forward_project`, passing the
      per-chunk `progress=` callback (T-108) into the item's progress sink.
      `n_projections_total` is passed as the scan length so the helix stays
      centred even for a subset (T-110).
- [x] FP `apply` sets `forward_projection` and toasts.
- [x] Remove the inline spinners (and the inline `st.progress`, which cannot be
      written from the worker) from both paths.

## Task 7 — Show queue switch, poller, drain wiring

**Files:** `src/visualization/actions.py`, `src/visualization/sidebar.py`,
`src/visualization/app.py`

- [x] `render_developer_options()`: one plain `st.checkbox("Show queue",
      key="dev_show_queue")` at the bottom of the sidebar, default off — no
      expander wrapper. No auth, no persistence.
- [x] `render_action_queue(session)`: one row per entry (icon, label, elapsed,
      progress when known, error). **Only pending rows get `✕ Cancel`**;
      running rows simply have no cancel control (a compiled C call cannot be
      stopped). `Clear finished` removes terminal rows. Rendered in the
      sidebar directly below the expander when the switch is on; not rendered
      at all when it is off. Elapsed time freezes at `finished_at` for terminal
      rows.
- [x] `@st.fragment(run_every="1s")` poller, mounted from **the end of
      `main()`** (not the sidebar) while `is_busy()`: by then every action
      button, including the FP button in a tab, has been evaluated. It renders
      nothing and calls `st.rerun(scope="app")` when the queue signature
      changes. This is what applies results with the panel hidden.
- [x] Enqueue paths show `st.toast("Added to queue")`, so a click is
      acknowledged with the panel hidden.
- [x] `main()`: call `drain_action_results(session_token(), notify=streamlit_notify)`
      right after `st.set_page_config`, before any widget is created (an apply
      writes widget-backed keys).
- [x] Clear Cache calls `reset_queue`.
- [x] No `st.rerun()` after an enqueue click.

## Task 8 — Tests, docs, ledger

**Files:** `tests/integration/test_ui_smoke.py`, `docs/plan.md`,
`docs/actions.md` (new, short operator note), `AGENTS.md`

- [x] `SIDEBAR_SECTIONS` and the `expanded` expectation stay at `Image` and
      `Measurements`; `Show queue` is a plain checkbox, not a third expander.
- [x] Assert `Show queue` exists and is `False` by default. An extra UI-smoke
      test enqueues a gated item plus a pending one to assert both status rows
      and the single `✕ Cancel` button; the FP test needs one extra `app.run()`
      because captions render above the button.
- [x] Set `actions_inline` in the module fixture so the existing click-then-
      assert tests keep their meaning against the same single run.
- [x] Test bar pinned at **387 passed, 0 skipped** (14 queue + 12 action unit
      tests, 2 new UI-smoke tests).
- [x] Ledger `T-109` row: implementation notes, manual-verification note.
- [x] `docs/actions.md`: what queues, what does not, cancel semantics, one job
      at a time, and where the `Show queue` switch lives.

## Task 9 — Verification

- [x] `cmd /c "set PATH=C:\Program Files\Git\bin;%PATH% && call C:\Users\hellwege\miniforge3\Scripts\activate.bat ct-viewer && python -m pytest -q -rs --no-header"`
      — **387 passed, 0 skipped** (Git Bash must be on `PATH` for the release
      tests).
- [x] `flake8 . --ignore=F841,E501,E402,F541,F401,W503,E203`, `black .`,
      `isort .` in that order — clean, no reformat left.
- [x] Manual browser checks on port 8502 (not covered by `AppTest`):
  1. `Show queue` off: a full FP ran to completion and its result appeared
     (`Simulated: (60, 192, 512) · 60 projections`); hiding the panel did not
     strand it. A second FP queued while hidden also completed.
  2. With the panel on, rows showed `running · Ns · k/60` with live progress,
     then `done · 25s · 60/60`; elapsed stayed frozen after completion.
  3. Clicking a second FP while the first was running left the page responsive
     and produced a pending row; the first result was applied.
  4. Not performed with real DICOM/projection files (none available locally);
     FIFO ordering is covered by the queue unit tests and the browser
     FP-then-second-action case.
  5. Switching tabs while an action ran did not produce a console error and
     the item completed.
  6. `✕ Cancel` removed the pending FP; only the running/done item remained and
     no second projection was computed.
  7. A fresh tab inherited no queue and showed no console errors; `app.log`
     had no queue errors.
  8. This machine has no CUDA device (`parallelproj CUDA present ..: False`).
     The worker FP ran with the CUDA checkbox on and finished normally;
     `use_cuda=True` and `use_cuda=False` give identical sums (54.10578) in a
     direct backend comparison. A real-GPU numeric comparison remains open.
- [x] Recorded the results in the T-109 status line.

## Acceptance

- No action blocks the script thread; no result is lost to a rerun.
- Clicking a new action appends; nothing is cancelled or interrupted.
- The queue is reachable via the sidebar **Show queue** checkbox (default off),
  and hiding it does not stop results from being applied.
- Pending jobs are removable, failures are visible with their message.
- Suite green with 0 skips, lint clean, test bar updated.
- Manual checks above are recorded, with the two environment-limited gaps
  named (no real DICOM/projection files; no CUDA device on this machine).
