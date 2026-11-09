# Background Startup Load — Design

**Date:** 2026-11-09
**Status:** Approved design, pending implementation plan
**Scope:** Streamlit startup data loading only

## Problem

`main()` calls `load_initial_volume()` directly:

```python
volume, projection_geometry, n_projections, trajectory_downsample = render_sidebar()

if volume is None:
    with st.status("Lade Daten …", expanded=True) as status:
        volume = load_initial_volume()
        status.update(label="Daten geladen", state="complete", expanded=False)
    ...
```

`load_initial_volume()` reads a DICOM series (potentially hundreds of files on a
slow or offline network drive) and can take many seconds. Streamlit executes one
script run at a time per session, so **every widget is unresponsive while that
call blocks**: sidebar expanders cannot collapse and tabs cannot switch. The page
appears frozen on first load.

## Goal

The app shell, sidebar, and all three tabs render and stay interactive
immediately. Startup loading happens off the script thread, and the viewer area
shows a compact status block that is replaced by the volume when the job
finishes.

**Non-goals:** the explicit "Load Series" button and "Load Measurements" remain
blocking (they are user-initiated and already carry progress UI). Measurement
loading feeds the comparison tab and is out of scope.

## Architecture

A loader registry, `src/visualization/background_load.py`, owns job lifecycle
with **no Streamlit dependency**, so its behaviour is unit-testable.

```
state: idle ──start()──> running ──success()──> done
                            │
                            └──failure()──> failed
```

- Jobs live in a module-level dict keyed by job name (`"startup"`), guarded by a
  `threading.Lock`. One `threading.Thread(daemon=True)` per job.
- The worker calls a supplied callable and stores exactly one outcome — the
  result, or the exception. It **never touches `st.*`**: Streamlit APIs are not
  thread-safe and a worker thread has no script run context.
- `st.session_state["volume"]` is assigned from the **main script** after the job
  completes, keeping session state single-threaded.
- Polling uses `st.fragment(run_every="1s")`. Only the status block re-executes,
  so the rest of the page remains interactive. `st.fragment` is available in the
  pinned Streamlit 1.39.1.

## Components

| Unit | Responsibility | Depends on |
|---|---|---|
| `background_load.Job` | Hold status + result/exception; thread-safe read | `threading` |
| `background_load.start_job(name, fn)` | Start once; no-op if already running or done | `threading` |
| `background_load.job_state(name)` | Return a snapshot `(status, result, error)` | — |
| `background_load.reset_job(name)` | Drop a job (retry, cache clear) | — |
| `app.render_startup_status()` | `st.fragment(run_every="1s")` status block; on success stores the volume and reruns | `background_load` |
| `sidebar.load_initial_volume()` | Decide *what* to load (cached series vs demo phantom) and return a **pure** callable — no I/O and no `st.*` at call time | `volume_cache` |
| `sidebar.create_demo_volume_job()` | Return a callable producing a `Volume` without touching `st` | `visualization.phantom` |
| `sidebar.load_demo_volume()` | Streamlit wrapper: call the pure factory, store in session state, toast | above |

The split that matters: **deciding what to load** stays pure and testable;
**performing the I/O** moves into the worker thread.

`status` is one of `"idle" | "running" | "done" | "failed"`.

### Why the demo path must be split

`load_demo_volume()` today does three things: build the phantom, write
`st.session_state`, and call `st.toast()`. Streamlit calls are not valid inside a
worker thread. The callable handed to the job may therefore only build and
return the `Volume`; storing it in session state and toasting stays in the main
script, in the fragment's success branch.

## Data Flow

1. `main()` renders the shell, sidebar and the three tabs immediately; nothing
   blocks.
2. If no `volume` is in session state and no `data_path` is entered, `main()`
   calls `start_job("startup", load_initial_volume())`. `load_initial_volume()`
   now returns a zero-argument callable rather than a volume.
3. Candidate selection is cheap and stays outside the thread:
   `load_last_loaded()` performs a single `exists()` check; choosing the demo
   phantom only constructs a callable.
4. The viewer tab renders `render_startup_status()` in the reserved plot slot.
   While running it shows `st.status("Lade Daten …", expanded=True)`.
5. Every 1 s the fragment re-runs:
   - **running** → no change;
   - **done** → write `st.session_state["volume"]`, `reset_job("startup")`,
     `st.rerun()` to swap the whole page to the volume;
   - **failed** → render the failure state (see below) and stop polling.
6. The status block is rendered *in place of* the 3D plot, so the layout does not
   jump when the volume arrives.

## Failure Handling

### Cached series exists but fails to load

Nothing is substituted. The status block shows:

```
No cached image data found. Select image data in the sidebar or load the demo phantom.
```

followed by a **Load Demo Phantom** button (and the sidebar remains usable). This
replaces the previous silent fallback to the demo phantom.

### No cache at all (fresh install)

Unchanged behaviour: the demo phantom loads automatically, with no prompt. A
first run is not an error.

### Robustness rules

- Worker exceptions are captured, never raised in the thread. An uncaught thread
  exception would be lost and leave the job stuck in `running` forever.
- A `finally` block guarantees the job leaves `running`.
- The fragment renders status and returns — no busy loop.
- `Clear Cache` calls `reset_job("startup")` so a stale failed/done job cannot
  mask a fresh load.
- Threads are daemons, so a stuck network read cannot block server shutdown.
- A wall-clock timeout (default 10 min) bounds the fragment: if a job somehow
  stays `running` past the deadline it is treated as failed and polling stops,
  rather than spinning indefinitely.
- **A terminal state stops the polling loop.** `run_every="1s"` cannot be
  switched off from inside the fragment, so a `failed` job would otherwise be
  re-polled every second for the rest of the session. A `startup_polling` flag in
  `st.session_state` is set to `True` when the job starts and cleared on the
  terminal transition; the fragment returns immediately when it is `False`.
  Costs one dict lookup, not one script run per second.

## Testability Boundary

`st.fragment(run_every=...)` does **not** fire under `AppTest`: each
`AppTest.run()` executes the script once, and no timer-driven fragment reruns
occur. Verified empirically against Streamlit 1.39.1. Therefore:

- The suite **can** cover job lifecycle, the startup decision, and rendering in a
  given state.
- The suite **cannot** cover polling, automatic hand-over, or "the page stays
  clickable while loading". Those are verified manually in the browser and are
  recorded as such in the plan — a green suite is not evidence for them.

## Files Touched

| File | Change |
|---|---|
| `src/visualization/background_load.py` | **New.** Job registry, worker thread, snapshots, reset |
| `src/visualization/app.py` | Startup wiring; `render_startup_status()` fragment; `main()` no longer blocks |
| `src/visualization/sidebar.py` | `load_initial_volume()` returns a callable and performs no I/O; pure demo-phantom factory added |
| `src/visualization/volume_cache.py` | Expose the cached-series loader as a callable factory (no behaviour change) |
| `tests/unit/test_background_load.py` | **New.** Registry/thread behaviour |
| `tests/unit/test_volume_cache.py` | Cover the loader factory |
| `tests/integration/test_ui_smoke.py` | Fixture seeds a demo volume (one line); no new runs |

## Testing

**Unit — `background_load` (no Streamlit):**
- `start_job` moves `idle → running` and invokes the callable exactly once.
- Success stores the result and reaches `done`.
- An exception stores the error and reaches `failed`; nothing is raised.
- Starting an already-running job does not spawn a second worker.
- A completed job is not restarted by another `start_job` call.
- `reset_job` returns the job to `idle` and clears the result/error.
- `job_state` on an unknown name returns `idle` rather than raising.

**Unit — `load_initial_volume()`:**
- Returns a demo-loader when no cache exists.
- Returns a cache-loader when a cache exists.
- Returns `None` when `data_path` is set (sidebar load owns it).
- Performs no filesystem reads beyond `load_last_loaded()`'s single `exists()`.

**Integration — `test_ui_smoke.py`:** no new `AppTest` runs. The existing
module-scoped fixture is updated to **seed a demo `Volume`** into
`at.session_state["volume"]` before `at.run()`, so the app starts with a volume
present — the same state the tests observe today, because `at.run()` used to
block until loading finished. All existing assertions keep their meaning and the
suite runtime does not change.

This is a deliberate boundary: with a seeded volume the startup job never starts,
so the smoke tests cannot detect broken fragment wiring. That gap is closed by
manual browser verification (see Testability Boundary), not by more `AppTest`
runs. Startup behaviour is covered by the unit tests above, which do not need
Streamlit.

## Verification

- `pytest` green (baseline: 237 passed, 2 skipped, ~30 s).
- `flake8` clean with the repo ignore set; `black`/`isort` unchanged.
- **Manual (required — not covered by the suite):** restart the server, point the
  cache at a slow or unreachable path, open the app and confirm while
  "Lade Daten …" is displayed that sidebar expanders collapse and tabs switch.
  Then confirm the viewer swaps to the volume on its own, and that a broken cache
  path produces the "No cached image data found…" message plus the demo button.
