"""Session-scoped FIFO queue for long-running UI actions.

Streamlit executes one script run per session at a time and only honours a
pending rerun at ``st.*`` yield points, so a long action on the script thread
freezes the page and its result is discarded when the next click unwinds the
run. This module moves such work onto one daemon thread per session.

Deliberately framework-free: nothing here imports or calls ``streamlit``. A
worker thread has no Streamlit script context, so it must never render, read
session state, or apply a result. The caller hands finished items to the main
script with :func:`drain_results` and applies them there.

One worker per session, one item at a time, FIFO: the queue *is* the ordering
guarantee. Each result is drained exactly once.
"""

import threading
import time
import uuid
from dataclasses import dataclass, field, replace
from typing import Callable, Optional

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"

TERMINAL_STATUSES = (STATUS_DONE, STATUS_FAILED, STATUS_CANCELLED)

# A worker that overruns this is reported failed, so the queue panel never
# spins forever. A thread stuck inside a C call cannot be killed; this bounds
# what the UI shows, not the work itself.
ITEM_TIMEOUT_S = 600.0


@dataclass
class QueueItem:
    """One queued action and its outcome.

    ``run`` is the only callable that crosses into the worker thread. It must
    be free of Streamlit calls and of session-state access. ``apply`` lives at
    the caller (``visualization.actions``), not here.
    """

    label: str
    run: Callable[[], object]
    kind: str = ""
    id: str = ""
    status: str = STATUS_PENDING
    result: object = None
    error: Optional[BaseException] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    progress: Optional[tuple[int, int]] = None
    applied: bool = False
    # Applied by the caller on the main thread (result, state) -> optional
    # message. Carried here so a drained item knows what to do with its
    # result; the worker never touches it.
    apply: Optional[Callable] = None


@dataclass
class _SessionQueue:
    items: list = field(default_factory=list)
    thread: Optional[threading.Thread] = None


_lock = threading.Lock()
_queues: dict[str, _SessionQueue] = {}


def _settle(item: QueueItem, now: float, deadline_s: float) -> None:
    """Mark an overrunning item failed (must be called under the lock)."""
    if item.status != STATUS_RUNNING or item.started_at is None:
        return
    if now - item.started_at <= deadline_s:
        return
    item.status = STATUS_FAILED
    item.error = TimeoutError(f"Action did not finish within {deadline_s:.0f} s")
    item.finished_at = now


def _execute(item: QueueItem) -> None:
    """Run one item and record its outcome (never raises)."""
    try:
        result = item.run()
    except BaseException as exc:  # noqa: BLE001 - reported to the UI
        with _lock:
            if item.status == STATUS_RUNNING:
                item.error = exc
                item.finished_at = time.time()
                item.status = STATUS_FAILED
    else:
        with _lock:
            if item.status == STATUS_RUNNING:
                item.result = result
                item.finished_at = time.time()
                item.status = STATUS_DONE


def _work(session: str, queue: _SessionQueue) -> None:
    """Drain one session queue, then exit.

    ``queue`` is identified, not the session key: a :func:`reset_queue` pops
    the object, and the abandoned worker must never attach to the replacement
    queue created by the next enqueue.
    """
    while True:
        with _lock:
            if _queues.get(session) is not queue:
                return
            item = next((i for i in queue.items if i.status == STATUS_PENDING), None)
            if item is None:
                queue.thread = None
                return
            item.status = STATUS_RUNNING
            item.started_at = time.time()
            item.progress = None

        _execute(item)


def enqueue(session: str, item: QueueItem) -> str:
    """Append ``item`` and start this session's worker if it is idle."""
    with _lock:
        item.id = item.id or uuid.uuid4().hex
        item.status = STATUS_PENDING
        item.applied = False
        queue = _queues.setdefault(session, _SessionQueue())
        queue.items.append(item)
        if queue.thread is None or not queue.thread.is_alive():
            queue.thread = threading.Thread(
                target=_work,
                args=(session, queue),
                name=f"action-queue-{session}",
                daemon=True,
            )
            queue.thread.start()
    return item.id


def run_now(session: str, item: QueueItem) -> str:
    """Run ``item`` synchronously on the calling thread.

    Deterministic seam for the integration suite: it records start/finish the
    same way the worker does, without a second thread. Production enqueues.
    """
    with _lock:
        item.id = item.id or uuid.uuid4().hex
        item.status = STATUS_PENDING
        item.applied = False
        _queues.setdefault(session, _SessionQueue()).items.append(item)
        item.status = STATUS_RUNNING
        item.started_at = time.time()
        item.progress = None
    _execute(item)
    return item.id


def snapshot(session: str) -> list[QueueItem]:
    """Return copies of this session's items, in queue order."""
    now = time.time()
    with _lock:
        queue = _queues.get(session)
        if queue is None:
            return []
        for item in queue.items:
            _settle(item, now, ITEM_TIMEOUT_S)
        return [replace(item) for item in queue.items]


def drain_results(session: str) -> list[QueueItem]:
    """Return each finished item exactly once, for the main script to apply.

    ``done`` and ``failed`` both count: the caller needs to report failures as
    well. Applied items stay in the queue as history.
    """
    now = time.time()
    drained = []
    with _lock:
        queue = _queues.get(session)
        if queue is None:
            return []
        for item in queue.items:
            _settle(item, now, ITEM_TIMEOUT_S)
            if item.applied:
                continue
            if item.status not in (STATUS_DONE, STATUS_FAILED):
                continue
            item.applied = True
            drained.append(replace(item))
    return drained


def is_busy(session: str) -> bool:
    """Whether anything in this session is pending or running."""
    now = time.time()
    with _lock:
        queue = _queues.get(session)
        if queue is None:
            return False
        for item in queue.items:
            _settle(item, now, ITEM_TIMEOUT_S)
        return any(
            item.status in (STATUS_PENDING, STATUS_RUNNING) for item in queue.items
        )


def cancel(session: str, item_id: str) -> bool:
    """Remove a pending item. Running items cannot be cancelled.

    A running item is refused (``False``) rather than marked: Python cannot
    stop a thread inside a C call, and a cancel button that does nothing is
    worse than not offering one.
    """
    with _lock:
        queue = _queues.get(session)
        if queue is None:
            return False
        for index, item in enumerate(queue.items):
            if item.id != item_id:
                continue
            if item.status != STATUS_PENDING:
                return False
            item.status = STATUS_CANCELLED
            item.finished_at = time.time()
            queue.items.pop(index)
            return True
        return False


def set_progress(session: str, item_id: str, current: int, total: int) -> None:
    """Record x/y progress for one running item (thread-safe).

    Called from a worker's progress callback, so it may never touch ``st``.
    Values are clamped to ``0..total`` and never move backwards.
    """
    if total <= 0:
        return
    total = int(total)
    current = max(0, min(int(current), total))
    with _lock:
        queue = _queues.get(session)
        if queue is None:
            return
        for item in queue.items:
            if item.id != item_id or item.status != STATUS_RUNNING:
                continue
            if item.progress is not None and current < item.progress[0]:
                return
            item.progress = (current, total)
            return


def clear_finished(session: str) -> None:
    """Drop terminal items whose result has already been applied."""
    with _lock:
        queue = _queues.get(session)
        if queue is None:
            return
        queue.items = [
            item
            for item in queue.items
            if not (
                item.status in TERMINAL_STATUSES
                and (item.status != STATUS_DONE or item.applied)
            )
        ]


def reset_queue(session: str) -> None:
    """Forget this session's queue (Clear Cache).

    Pending items are dropped; a running item is marked cancelled so its late
    result is discarded when the worker returns.
    """
    with _lock:
        queue = _queues.pop(session, None)
        if queue is None:
            return
        for item in queue.items:
            if item.status in (STATUS_PENDING, STATUS_RUNNING):
                item.status = STATUS_CANCELLED
            if item.finished_at is None:
                item.finished_at = time.time()


def clear_registry() -> None:
    """Drop every session queue. Tests only."""
    with _lock:
        sessions = list(_queues)
    for session in sessions:
        reset_queue(session)
