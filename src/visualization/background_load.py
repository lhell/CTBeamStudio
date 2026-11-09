"""Background job registry for the startup volume load.

Streamlit executes one script run per session at a time, so performing a slow
DICOM read inline freezes every widget until it returns. This module runs such a
read in a daemon thread and stores exactly one outcome, so the UI can poll it and
stay interactive.

Deliberately framework-free: nothing here imports or calls ``streamlit``. A
worker thread has no Streamlit script context, so it must never render, read
session state, or touch any ``st`` API. The caller is responsible for applying
the result from the main script.
"""

import threading
from typing import Callable

STATUS_IDLE = "idle"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_FAILED = "failed"

# name -> {"status": str, "result": object | None, "error": BaseException | None}
_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def run_and_capture(state: dict, fn: Callable[[], object]) -> None:
    """Run ``fn`` and record its outcome in ``state``.

    The ``finally`` block guarantees the job leaves ``running`` even when the
    callable raises. Without it an exception would leave the status stuck at
    ``running`` forever and the UI would poll it indefinitely.
    """
    try:
        result = fn()
    except BaseException as exc:  # noqa: BLE001 - reported to the UI, not swallowed
        with _lock:
            state["result"] = None
            state["error"] = exc
            state["status"] = STATUS_FAILED
    else:
        with _lock:
            state["result"] = result
            state["error"] = None
            state["status"] = STATUS_DONE
    finally:
        with _lock:
            if state["status"] == STATUS_RUNNING:
                state["status"] = STATUS_FAILED


def start_job(name: str, fn: Callable[[], object]) -> bool:
    """Start ``fn`` in a daemon thread under ``name``.

    Returns ``True`` when a worker was started. Returns ``False`` when a job
    with this name is already running or already finished: a finished job is
    not restarted, so callers must :func:`reset_job` before retrying.
    """
    with _lock:
        existing = _jobs.get(name)
        if existing is not None and existing["status"] in (
            STATUS_RUNNING,
            STATUS_DONE,
        ):
            return False
        state = {"status": STATUS_RUNNING, "result": None, "error": None}
        _jobs[name] = state

    thread = threading.Thread(
        target=run_and_capture,
        args=(state, fn),
        name=f"background-load-{name}",
        daemon=True,
    )
    thread.start()
    return True


def job_state(name: str) -> tuple[str, object | None, BaseException | None]:
    """Return a ``(status, result, error)`` snapshot for ``name``.

    An unknown name reports ``idle`` rather than raising, so callers do not need
    to know whether a job was ever started.
    """
    with _lock:
        state = _jobs.get(name)
        if state is None:
            return (STATUS_IDLE, None, None)
        return (state["status"], state["result"], state["error"])


def reset_job(name: str) -> None:
    """Forget the job called ``name``, returning it to ``idle``."""
    with _lock:
        _jobs.pop(name, None)
