# Action Queue — Design

**Date:** 2026-11-19
**Status:** Proposed, awaiting approval
**Scope:** The four long-running, user-initiated actions in the UI
**Ledger:** T-109

## Problem

The app has four actions that can take seconds to minutes:

| Action | Where | Work |
|---|---|---|
| Load Series | `sidebar.py:158-207` | DICOM read of up to hundreds of files |
| Load Measurements | `projection_panel.py:399-441` | sinogram file/folder read |
| Generate dummy measurement | `projection_panel.py:484-517` | Shepp-Logan + forward projection + scatter + noise |
| Run Forward Projection | `projection_panel.py:950-983` | CPU/GPU projection |

All four run **on the Streamlit script thread**, and each one writes its result to
`st.session_state` only *after* the computation. That is the failure mode the user
reports: clicking a second action while the first is running loses the first one.

The mechanism is in Streamlit 1.39.1 itself, not in our code:

- `ScriptRunner` handles a pending RERUN/STOP request only at *yield points* —
  `_maybe_handle_execution_control_request` (`streamlit/runtime/scriptrunner/script_runner.py:354-386`),
  called from `enqueue_forward_msg` (`:344-347`) and via `SafeSessionState`'s
  yield callback (`:171`).
- A yield point is any `st.*` call that emits a forward message. A long NumPy or
  parallelproj call is **not** one, so the click cannot interrupt it mid-call:
  the page just freezes until the call returns.
- When it returns, the next `st.*` call raises `RerunException`, which unwinds
  the script **before** our session-state assignment. The finished work is
  discarded and the new click starts from scratch.

Concretely, `render_measurement_sidebar` does
`load_sinogram(...)` → `progress_bar.empty()` (line 429, a yield point) →
`st.session_state["sinogram"] = sinogram` (line 434). A click during the load
raises at line 429 and the loaded sinogram is lost. `Load Series`
(`sidebar.py:188-196`) and `Run Forward Projection`
(`projection_panel.py:964-976`, next message is the toast at 980) have the same
shape. `background_load.py` already solves this for the startup load (T-83); the
four user actions were explicitly left blocking in that design
(`2026-11-09-background-startup-load-design.md`, Non-goals).

## Goal

A per-session FIFO queue of actions:

- A click **enqueues** instead of computing inline. The click returns
  immediately; the page stays interactive.
- Exactly one queued action runs at a time, in click order. A second click does
  not cancel, replace, or wait behind a frozen page — it appends.
- A finished action's result is applied to `st.session_state` by the main
  thread, before any widget is instantiated, so it cannot be lost to a rerun.
- A developer can make the queue visible (`Show queue`, a plain sidebar
  checkbox, default off) to inspect, cancel pending items and watch progress.
  Hiding it changes only what is rendered, never whether results are applied.

## Non-goals

- **No parallel execution.** Forward projection is CPU/GPU-bound, and parallel
  side effects on one session's state are not worth it. Serial is the queue.
- **No dependency graph.** A forward projection needs a volume *at enqueue
  time*; queueing "Load Series + Forward Projection" in one go is not
  supported (the FP button keeps saying "load a volume first"). Chaining jobs
  is a separate change if it is ever wanted.
- **No conflict detection.** Queueing two volume-producing actions applies both
  results in order; the last one wins. The queue list shows the order.
- **No interruption of a running job.** Python cannot kill a thread stuck in a
  C call. "Cancel" removes pending jobs and refuses running ones (the panel
  offers no button for them); a running job always finishes and its result is
  applied.
- The startup load keeps its own registry (`background_load.py`). It works,
  it is tested, and its hand-over to the empty state is bespoke.

## Architecture

```
enqueue ──> pending ──worker picks──> running ──> done ──main script──> applied
                                        │
                                        └──> failed ──main script──> reported
```

One daemon worker thread per session queue. It starts on the first enqueue,
drains the queue, and exits when empty. A new enqueue restarts it.

```
UI (main thread)                    action_queue.py (no Streamlit)         worker
────────────────                    ─────────────────────────────         ──────
button -> enqueue(session, spec) ──> [pending, pending, ...] ──────────> run(spec.run)
                                          │                                   │
mount_queue_poller() polls snapshot <─────┘                             result/error
main(): drain_results() ──> spec.apply(result, state)                          │
```

The registry is a module-level dict keyed by a per-session token, guarded by a
`threading.Lock` — the same isolation `startup_job_name()` uses
(`sidebar.py:269-281`). The worker **never touches `st.*`**, never reads
session state, and never calls `apply`.

### Components

| Unit | Responsibility | Depends on |
|---|---|---|
| `action_queue.QueueItem` | id, label, kind, status, result/error, timestamps, progress, `apply` | `threading` |
| `action_queue.enqueue(session, item) -> str` | Append, start the worker if idle | `threading` |
| `action_queue.snapshot(session) -> list[View]` | Thread-safe copy for rendering | — |
| `action_queue.drain_results(session) -> list[Item]` | Hand finished items to the main script exactly once | — |
| `action_queue.cancel(session, id)` | Drop a pending item; refuse a running one | — |
| `action_queue.set_progress(session, id, current, total)` | Thread-safe progress sink | — |
| `action_queue.clear_finished(session)` / `reset_queue(session)` | Housekeeping / Clear Cache | — |
| `QueueItem.apply(result, state)` | Carried by the item, called by the main thread only; returns a message or None | — |
| `actions.enqueue_*` factories | Freeze the clicked widget values into a `run()` closure and submit | widget values, `action_queue` |
| `actions.drain_action_results()` | Main-thread glue: `drain_results` + `spec.apply` | `action_queue`, `st` |
| `actions.render_developer_options()` | Bottom sidebar expander with the `Show queue` switch | `st` |
| `actions.mount_queue_poller(session)` | 1 s fragment while busy; renders nothing, reruns the app when the queue signature changes | `action_queue`, `st` |

`apply` takes a `MutableMapping` (the session state) rather than calling
`st.session_state` directly, so it is unit-testable; the glue passes
`st.session_state`.

### Data flow

1. A button click builds an `ActionSpec` **from current widget values**
   (snapshot) and calls `enqueue`.
2. The worker runs `spec.run()`; progress callbacks call
   `set_progress(session, id, current, total)` instead of `st.progress`.
3. `main()` mounts the poll fragment at the end of the script while the worker
   is busy — by then the FP button in a tab has also been evaluated. It renders
   nothing and calls `st.rerun(scope="app")` when the queue signature changes,
   which redraws the sidebar panel if it is visible and applies results even
   when it is hidden.
4. `main()` calls `drain_action_results()` immediately after
   `st.set_page_config` and **before** `render_sidebar()`. Widget-backed keys
   (e.g. the sample presets) are therefore set before those widgets are
   instantiated, which is mandatory in Streamlit.
5. `apply` writes session state, may toast, and never calls `st.rerun()` —
   the current run already renders the new state.

### Progress

Every long action has a progress hook: `load_volume_cached(_progress_callback=)`,
`load_sinogram(progress=)`, and `forward_project(progress=)` (the per-chunk
callback added by T-108). The runner forwards it into the queue item; the
fragment renders `st.progress(current / total)` and "Loading 42/300 ...". The
worker never creates or modifies a Streamlit element.

Dummy generation has no hook and reports only its start/finish. An action
without a hook shows a running state and elapsed time — never a fake
percentage.

### Failure handling

- `run_and_capture`-style `try/finally`: an item always leaves `running`, even
  on `BaseException` (same rule as `background_load.run_and_capture`).
- A failed item keeps its exception; the queue list shows
  `st.error(label: message)` and offers "Remove".
- A wall-clock timeout (`effective_status`-style, default 10 min) marks a stuck
  item failed so the list never spins forever.
- Result application is guarded: an exception in `apply` is reported in the
  queue list and does not kill the script run.

### Session lifecycle

- Token is created on first use and stored in session state
  (`action_queue_token`), so two browser tabs never share a queue.
- Clear Cache calls `reset_queue(token)`: pending items are dropped, a running
  item still finishes but its result is discarded.
- Worker threads are daemons; a closed tab leaves nothing blocking shutdown.
- Items hold references to their inputs (volume array, file paths). The array
  is not copied — the volume is replaced, never mutated, so this is safe and
  costs no memory.

## UI

The queue is **not** a normal user-facing panel. It lives behind a developer
switch at the bottom of the sidebar:

```
☐ Show queue
```

- `render_developer_options()` renders one plain checkbox directly in the
  sidebar after the collapsible sections — no extra expander:
  `st.checkbox("Show queue", key="dev_show_queue")`, default `False`.
- When `Show queue` is checked, the queue list renders directly below the
  checkbox, in the sidebar:

```
  Actions                                  [Clear finished]
  ▶ Forward Projection            12.4 s   [progress bar]
  ⏳ Load Measurements            queued    [✕ Cancel]
  ✅ Load Series                  3.1 s
  ❌ Load Measurements            File not found: ...
```

- Every **pending** row carries a `✕ Cancel` control: it removes the entry, and
  the worker never starts it.
- A **running** row has no cancel control — a job inside a C call cannot be
  stopped, and offering a button that does nothing is worse than saying so. The
  row's status simply reads `running`.
- Finished rows are removed with `Clear finished` (or with Clear Cache, which
  resets the whole queue). Their elapsed time is frozen at completion.
- When it is unchecked the list is not rendered at all, but **results still
  apply**: the poller stays mounted while work is active and reruns the whole
  app on state changes regardless of the switch. Hiding the queue must never
  mean results are stranded until the next unrelated click.
- The poll fragment is mounted only while an item is pending/running, following
  T-83: it is not re-registered once idle, so no per-second timer survives a
  finished queue.
- Enqueueing always shows a toast (`Added to queue`), so a click gives feedback
  even with the panel hidden.
- The flag is per session and not persisted. There is no role check — this is a
  desktop app with one operator.

`Show queue` is a checkbox, not an expander, so the smoke test's
`SIDEBAR_SECTIONS` and its `expanded` expectation stay at `Image` and
`Measurements`; the default-off state is asserted on the checkbox itself.

## Testability boundary

`st.fragment(run_every=...)` does not fire under `AppTest` (verified for T-83
against 1.39.1). Therefore the suite covers:

- queue ordering, one-at-a-time execution, status transitions, result hand-off
  exactly once, cancel semantics, progress snapshots, per-session isolation;
- the pure input-snapshot factories and the `apply` functions against a plain
  dict.

The suite cannot cover polling, "the page stays clickable", cross-thread GPU
use, or a click-during-work losing nothing. Those are **manual browser checks**
and are recorded as such in the ledger — a green suite is not evidence for them.

### Integration-test seam

The existing smoke tests click `load_measurements` / `dummy_measurement` and
assert `session_state` on the **same** run (e.g. shape, presets, file list).
With an async queue those assertions would need a second run plus a thread
wait, which is exactly the kind of `AppTest` timing the suite avoids.

`actions` therefore honours a session flag `actions_inline` (set only by the
integration fixture): enqueue then runs the spec and applies it synchronously
on the calling thread. Production never sets it, so the real path is the worker
thread. This is an explicit test seam, named as such in `actions.py` — not a
fallback that hides a broken queue.

The queue itself is covered by the unit tests, which have no Streamlit
dependency.

## Files

| File | Change |
|---|---|
| `src/visualization/action_queue.py` | **New.** Framework-free registry, worker, snapshots, progress |
| `src/visualization/actions.py` | **New.** `ActionSpec`, the four factories, apply functions, drain glue |
| `src/visualization/sidebar.py` | Load Series enqueues; `Show queue` checkbox call |
| `src/visualization/projection_panel.py` | Measurements/dummy/FP enqueue; inline spinners replaced |
| `src/visualization/app.py` | `drain_action_results()` at the top of `main()`; poller at the end |
| `tests/unit/test_action_queue.py` | **New.** Registry behaviour |
| `tests/unit/test_actions.py` | **New.** Snapshots and apply functions |
| `tests/integration/test_ui_smoke.py` | Sidebar sections, `Show queue` default and cancel-panel assertions, same module-scoped run |
| `docs/plan.md` | T-109 |

## Decisions

- **2026-11-19 — Option A, per-click enqueue.** Each action button enqueues
  immediately; the buttons stay next to their own inputs and the queue is the
  selection. No checkbox multi-select / "Queue selected" panel. A fixed
  full-run preset can be added later without changing the queue.
- The queue shows every entry and offers `Cancel` on pending rows only.
