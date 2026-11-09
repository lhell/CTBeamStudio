# Background Startup Load Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the startup volume load off the Streamlit script thread so the shell, sidebar and all three tabs stay interactive while a series is read.

**Architecture:** A Streamlit-free job registry (`background_load.py`) runs the loader in a daemon thread and stores exactly one outcome. `main()` renders the page immediately, then a `st.fragment(run_every="1s")` status block polls the job; on success the volume is written to session state from the main script and the app reruns.

**Tech Stack:** Python 3.11+, Streamlit 1.39.1 (pinned `<1.40.0`), `threading`, pytest.

**Spec:** `docs/superpowers/specs/2026-11-09-background-startup-load-design.md`

## Global Constraints

- Streamlit is pinned `>=1.28.0,<1.40.0`; `st.fragment` and `st.rerun` are available in 1.39.1.
- Jobs must be reachable from the main script only — **no `st.*` call may execute inside a worker thread**.
- Worker threads must be `daemon=True`.
- Failure message copy, verbatim: `No cached image data found. Select image data in the sidebar or load the demo phantom.`
- Polling interval: `run_every="1s"`.
- Baseline suite: **237 passed, 2 skipped, ~30 s**. Runtime must not grow materially (no new `AppTest` runs).
- Lint: `flake8 --ignore=F841,E501,E402,F541,F401,W503,E203`, then `black`, then `isort`.
- German UI text already in use (`Lade Daten …`) stays as-is.

## Review Focus

- **A job that never finishes** — if the worker raises in a way that skips the `finally`, the UI must surface a failure rather than poll forever; the spec's 10-minute deadline and `startup_polling` flag both exist for this. Covered by Task 2.
- **Clear Cache while a load is running** — the user clears the cache mid-load; the stale job must not then repopulate the viewer with the old volume. Covered by Task 2 (`reset_job`) and Task 5.
- **Sidebar "Load Series" while a startup job is running** — the user picks a DICOM folder before the background job finishes; the startup result must not overwrite the explicitly loaded series. Covered by Task 5 (the fragment only writes when `volume` is still absent).
- **A cached series that fails** — must show the message plus the demo button, never a silent substitute and never a blank viewer. Covered by Task 4 (decision returns the callable; the failure path is rendered by the fragment).
- **Thread leakage across session clears** — `Clear Cache` deletes `st.session_state`; the registry lives outside it, so the job handle must be reset explicitly or a second `start_job` silently no-ops. Covered by Task 2 and Task 5.

---

### Task 1: Job registry

**Files:**
- Create: `src/visualization/background_load.py`
- Test: `tests/unit/test_background_load.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `STATUS_IDLE = "idle"`, `STATUS_RUNNING = "running"`, `STATUS_DONE = "done"`, `STATUS_FAILED = "failed"`
  - `start_job(name: str, fn: Callable[[], object]) -> bool` — returns `True` if a worker was started, `False` if a job with that name is already `running` or `done`
  - `job_state(name: str) -> tuple[str, object | None, BaseException | None]` — `(status, result, error)`; unknown name returns `(STATUS_IDLE, None, None)`
  - `reset_job(name: str) -> None` — removes the job entirely
  - `run_and_capture(state: dict, fn: Callable[[], object]) -> None` — the worker body, exported so the `finally` guarantee is unit-testable without a thread

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for the Streamlit-free background load registry."""

import threading

import pytest

from visualization.background_load import (
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_IDLE,
    STATUS_RUNNING,
    job_state,
    reset_job,
    run_and_capture,
    start_job,
)


@pytest.fixture(autouse=True)
def clean_registry():
    for name in ("startup", "other"):
        reset_job(name)
    yield
    for name in ("startup", "other"):
        reset_job(name)


def _wait_until_settled(name, timeout=5.0):
    deadline = threading.Event()
    waited = 0.0
    while waited < timeout:
        status, _, _ = job_state(name)
        if status != STATUS_RUNNING:
            return status
        deadline.wait(0.01)
        waited += 0.01
    raise AssertionError("job did not settle")


def test_unknown_job_reports_idle():
    assert job_state("never-started") == (STATUS_IDLE, None, None)


def test_start_job_runs_to_done_and_stores_result():
    started = start_job("startup", lambda: "volume")

    assert started is True
    assert _wait_until_settled("startup") == STATUS_DONE
    assert job_state("startup") == (STATUS_DONE, "volume", None)


def test_start_job_reports_running_immediately():
    gate = threading.Event()
    start_job("startup", lambda: gate.wait(5) and "slow")

    assert job_state("startup")[0] == STATUS_RUNNING
    gate.set()
    _wait_until_settled("startup")


def test_failure_is_captured_and_not_raised():
    def boom():
        raise ValueError("no dicom files")

    start_job("startup", boom)

    status, result, error = job_state("startup")
    assert _wait_until_settled("startup") == STATUS_FAILED
    status, result, error = job_state("startup")
    assert result is None
    assert isinstance(error, ValueError)


def test_completed_job_is_not_restarted():
    start_job("startup", lambda: "first")
    _wait_until_settled("startup")

    assert start_job("startup", lambda: "second") is False
    assert job_state("startup") == (STATUS_DONE, "first", None)


def test_running_job_is_not_started_twice():
    gate = threading.Event()
    assert start_job("startup", lambda: gate.wait(5) and "slow") is True
    assert start_job("startup", lambda: "second") is False
    gate.set()
    _wait_until_settled("startup")
    assert job_state("startup")[1] == "slow"


def test_reset_job_returns_to_idle():
    start_job("startup", lambda: "volume")
    _wait_until_settled("startup")

    reset_job("startup")

    assert job_state("startup") == (STATUS_IDLE, None, None)


def test_run_and_capture_always_leaves_running_state():
    """The worker must not be left 'running' when the callable raises, or the
    fragment would poll forever."""
    state = {"status": STATUS_RUNNING}

    run_and_capture(state, lambda: (_ for _ in ()).throw(RuntimeError("x")))

    assert state["status"] == STATUS_FAILED
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/unit/test_background_load.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'visualization.background_load'`

- [ ] **Step 3: Implement the registry**

Module-level `_jobs: dict[str, dict]` and `_lock = threading.Lock()`. Each entry is `{"status": ..., "result": ..., "error": ...}`. `start_job` takes the lock, returns `False` when the entry is `running` or `done`, otherwise registers `running` and starts `threading.Thread(target=run_and_capture, args=(state, fn), daemon=True)`. `run_and_capture` calls `fn()` inside `try`, stores the outcome, and sets the terminal status in `finally`. `job_state` returns a tuple snapshot under the lock. `reset_job` deletes the entry under the lock.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/unit/test_background_load.py -q`
Expected: PASS (8 passed)
- [ ] **Step 5: Commit**

```bash
git add src/visualization/background_load.py tests/unit/test_background_load.py
git commit -m "feat(ui): add Streamlit-free background job registry"
```

---

### Task 2: Startup decision becomes a callable

**Files:**
- Modify: `src/visualization/sidebar.py:292-349` (`load_initial_volume`, `load_demo_volume`)
- Test: `tests/unit/test_startup_selection.py`

**Interfaces:**
- Consumes: `volume_cache.load_last_loaded()`, `volume_cache.load_volume_cached(...)`, `visualization.phantom.create_demo_volume()`.
- Produces:
  - `startup_loader(has_data_path: bool, auto_load_cache: bool, cache_lookup: Callable[[], list | None] = load_last_loaded) -> Callable[[], object] | None` — pure decision function in `sidebar.py`. Returns `None` when `has_data_path`; a demo-phantom callable when no cache; a cache-loading callable otherwise. Performs **no** DICOM I/O.
  - `create_demo_volume_job() -> Callable[[], object]` — returns a callable that builds and returns a `Volume` without touching `st`.
  - `load_demo_volume()` keeps its current Streamlit behaviour (session state + toast) and delegates the build to `create_demo_volume_job`.

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for the pure startup-load decision (no Streamlit, no I/O)."""

from visualization.sidebar import create_demo_volume_job, startup_loader


def test_data_path_set_defers_to_sidebar():
    assert startup_loader(True, True, cache_lookup=lambda: ["x.dcm"]) is None


def test_without_cache_returns_the_demo_job():
    loader = startup_loader(False, True, cache_lookup=lambda: None)

    volume = loader()
    assert volume is not None
    assert hasattr(volume, "array")


def test_cache_disabled_returns_the_demo_job():
    loader = startup_loader(False, False, cache_lookup=lambda: ["x.dcm"])

    volume = loader()
    assert hasattr(volume, "array")


def test_cache_lookup_is_not_consulted_when_disabled():
    calls = []

    def lookup():
        calls.append(1)
        return ["x.dcm"]

    startup_loader(False, False, cache_lookup=lookup)
    assert calls == []


def test_cache_hit_returns_a_callable_that_loads_those_files(monkeypatch):
    import visualization.sidebar as sidebar

    seen = {}

    def fake_load(files):
        seen["files"] = files
        return "loaded-volume"

    monkeypatch.setattr(sidebar, "load_volume_cached", fake_load)

    loader = startup_loader(False, True, cache_lookup=lambda: ["a.dcm", "b.dcm"])

    assert loader() == "loaded-volume"
    assert seen["files"] == ["a.dcm", "b.dcm"]


def test_demo_job_is_pure_and_repeatable():
    job = create_demo_volume_job()

    first = job()
    second = job()

    assert first.array.shape == second.array.shape
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/unit/test_startup_selection.py -q`
Expected: FAIL — `ImportError: cannot import name 'startup_loader'`

- [ ] **Step 3: Implement the decision functions**

`create_demo_volume_job()` returns a closure calling `create_demo_volume()` (imported lazily inside the closure, matching the module's existing import style). `startup_loader()` returns `None` for `has_data_path`, checks `auto_load_cache` before calling `cache_lookup`, and otherwise returns either the demo job or a closure loading `[str(f) for f in cached_files]` through `load_volume_cached`. Leave `load_initial_volume()` in place for now; Task 5 rewires `main()` and deletes it.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/unit/test_startup_selection.py -q`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/visualization/sidebar.py tests/unit/test_startup_selection.py
git commit -m "refactor(ui): extract pure startup-load decision"
```

---

### Task 3: Polling helper with a hard deadline

**Files:**
- Modify: `src/visualization/background_load.py`
- Test: `tests/unit/test_background_load.py` (append)

**Interfaces:**
- Consumes: `job_state`, `STATUS_*` from Task 1.
- Produces: `effective_status(status: str, started_at: float, now: float, deadline_s: float = 600.0) -> str` — returns `STATUS_FAILED` when `status == STATUS_RUNNING` and `now - started_at > deadline_s`, else returns `status` unchanged.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_job_past_its_deadline_is_reported_failed():
    assert effective_status(STATUS_RUNNING, 0.0, 601.0) == STATUS_FAILED


def test_a_job_within_its_deadline_stays_running():
    assert effective_status(STATUS_RUNNING, 0.0, 599.0) == STATUS_RUNNING


def test_terminal_states_are_never_overridden():
    assert effective_status(STATUS_DONE, 0.0, 10_000.0) == STATUS_DONE
    assert effective_status(STATUS_FAILED, 0.0, 10_000.0) == STATUS_FAILED
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/unit/test_background_load.py -q`
Expected: FAIL — `ImportError: cannot import name 'effective_status'`

- [ ] **Step 3: Implement `effective_status`**

Add the import to the test module's existing import block; implement as a single conditional comparing `now - started_at` to `deadline_s`.

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/unit/test_background_load.py -q`
Expected: PASS (11 passed)

- [ ] **Step 5: Commit**

```bash
git add src/visualization/background_load.py tests/unit/test_background_load.py
git commit -m "feat(ui): bound background jobs with a wall-clock deadline"
```

---

### Task 4: Non-blocking startup in `main()` with an inline status fragment

**Files:**
- Modify: `src/visualization/app.py:454-495` (`main`, `render_viewer_tab`)
- Test: none new (see spec "Testability Boundary")

**Interfaces:**
- Consumes: `start_job`, `job_state`, `effective_status`, `reset_job`, `STATUS_*` from Tasks 1–3; `startup_loader` from Task 2.
- Produces: `render_startup_status(started_at: float) -> None` — a `@st.fragment(run_every="1s")` function. On `done` it writes the result to `st.session_state["volume"]`, calls `reset_job("startup")`, clears `st.session_state["startup_polling"]`, and calls `st.rerun()`. On `failed` (or deadline exceeded) it renders `st.error` with the verbatim copy plus a `Load Demo Phantom` button, clears the polling flag, and returns. While `running` it renders `st.status("Lade Daten …", expanded=True)`.

- [ ] **Step 1: Rewire `main()`**

Replace the blocking block (lines 467–477) with: compute `loader = startup_loader(has_data_path=bool(st.session_state.get("data_path")), auto_load_cache=st.session_state.get("auto_load_cache", True))`; when `volume is None and loader is not None`, call `start_job("startup", loader)`, set `st.session_state["startup_polling"] = True` and `st.session_state["startup_started_at"] = time.time()`. Remove the now-dead `Daten geladen` toast. Keep the demo-mode banner and `shell.empty()`.

- [ ] **Step 2: Render the status block in the viewer tab**

In `render_viewer_tab`, `volume is None` currently renders the welcome screen and returns. Change that branch to: if `st.session_state.get("startup_polling")`, call `render_startup_status(st.session_state["startup_started_at"])` and return; otherwise keep the existing welcome screen.

- [ ] **Step 3: Implement `render_startup_status`**

Guard clause first: return immediately when `not st.session_state.get("startup_polling")` — this stops the 1 s loop after a terminal state, which `run_every` cannot switch off by itself. Then read `job_state("startup")` under `effective_status`, and branch to the three states described in Interfaces. The demo button's handler calls `create_demo_volume_job()()` and writes the result to session state before `st.rerun()`.

- [ ] **Step 4: Do not overwrite an explicitly loaded series**

The fragment must not clobber a volume the user loaded from the sidebar while the job ran. On `done`, write the result only when `st.session_state.get("volume") is None`; otherwise discard the result (still `reset_job` and clear the polling flag). Without this guard, clicking "Load Series" during a slow startup load would have its result replaced a second later.

- [ ] **Step 5: Verify the app still renders**

Run: `python -m pytest tests/integration/test_ui_smoke.py -q`
Expected: **3 failures** — `test_3d_plot_has_a_projection_geometry_toggle_in_the_corner`, `test_3d_options_no_longer_offer_a_show_trajectory_checkbox`, `test_render_mode_offers_only_iso_surface`. These are the tests that need a volume present at first render; Task 5 fixes the fixture. Any *other* failure is a real bug in this task.

- [ ] **Step 6: Commit**

```bash
git add src/visualization/app.py
git commit -m "feat(ui): load startup volume in the background

The script run no longer blocks on the DICOM read, so sidebar expanders
and tabs stay usable while data loads."
```

---

### Task 5: Re-enable the smoke tests, reset on cache clear, drop the dead loader

**Files:**
- Modify: `tests/integration/test_ui_smoke.py:27-32` (fixture)
- Modify: `src/visualization/sidebar.py` (delete `load_initial_volume`; reset the job in Clear Cache)
- Modify: `src/visualization/app.py` (remove the `load_initial_volume` import)

**Interfaces:**
- Consumes: everything above.
- Produces: no new symbols.

- [ ] **Step 1: Seed the smoke-test fixture**

Add `at.session_state["volume"] = create_demo_volume()` before `at.run()`, importing from `visualization.phantom`, with a comment explaining that a seeded volume keeps the app in the "volume present" state the assertions were written against, and that startup behaviour is covered by unit tests because `run_every` does not fire under `AppTest`.

- [ ] **Step 2: Reset the job in Clear Cache**

In `render_sidebar`, the `🗑️ Clear Cache` handler already deletes every `st.session_state` key. Add `reset_job("startup")` before `st.rerun()` (importing it at module top from `visualization.background_load`). Without this, the registry keeps a `done`/`failed` entry that survives the session-state wipe, and the next `start_job("startup", ...)` silently returns `False` — leaving the viewer permanently empty after a cache clear.

- [ ] **Step 3: Run the smoke tests**

Run: `python -m pytest tests/integration/test_ui_smoke.py -q`
Expected: PASS (13 passed) — the three failures from Task 4 are resolved.

- [ ] **Step 4: Delete `load_initial_volume` and its import**

Remove the function from `sidebar.py` and the `load_initial_volume` name from the import in `main()`. Confirm no references remain:

Run: `python -m pytest tests -q -k "startup or volume_cache or smoke"`
Expected: PASS

- [ ] **Step 5: Run the whole suite and the linters**

Run: `python -m pytest -q`
Expected: PASS — 254 passed, 2 skipped (baseline 237 + 17 new unit tests: 8 registry, 6 decision, 3 deadline). Runtime must be roughly unchanged from ~30 s.

Run: `python -m flake8 . --ignore=F841,E501,E402,F541,F401,W503,E203`
Expected: no output.

Run: `python -m black --check src tests && python -m isort --check-only src tests`
Expected: no files reformatted.

- [ ] **Step 6: Commit**

```bash
git add tests/integration/test_ui_smoke.py src/visualization/sidebar.py src/visualization/app.py
git commit -m "test(ui): seed smoke fixture; reset job on cache clear; drop blocking loader"
```

---

### Task 6: Documentation

**Files:**
- Modify: `docs/plan.md` (add T-83)

- [ ] **Step 1: Record the change in the plan**

Add a `### [x]` T-83 section describing the background startup load: goal, files, the `st.fragment` polling mechanism, the `startup_polling` guard, and an explicit note that polling and interactivity are **not** covered by the suite because `run_every` does not fire under `AppTest` — verified against 1.39.1 — and are browser-verified.

- [ ] **Step 2: Commit**

```bash
git add docs/plan.md
git commit -m "docs(plan): record T-83 background startup load"
```

---

## Manual Verification (not automated)

Required before claiming the change works, because no test in the suite can see it:

1. `python -m streamlit run src/visualization/app.py`
2. Point `data/.last_loaded.json` at a series on an unreachable network path (or a folder with hundreds of slices on a slow drive).
3. Reload the page. While `Lade Daten …` is visible: collapse and expand sidebar sections, switch between the three tabs. **These must respond immediately.**
4. Confirm the viewer swaps to the volume without any click.
5. Repeat with a broken cache path and confirm the `No cached image data found…` message plus the Load Demo Phantom button appear, and that the button loads the phantom.
6. Confirm the server log shows no traceback from the worker thread.
