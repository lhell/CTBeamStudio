"""Tests for the Streamlit-free action queue."""

import threading
import time

import pytest

import visualization.action_queue as action_queue
from visualization.action_queue import (
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
    QueueItem,
    cancel,
    clear_finished,
    clear_registry,
    drain_results,
    enqueue,
    is_busy,
    reset_queue,
    run_now,
    set_progress,
    snapshot,
)

SESSION = "session-a"


@pytest.fixture(autouse=True)
def clean_registry():
    clear_registry()
    yield
    clear_registry()


def _wait_until(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError("condition not met within timeout")


def test_runs_items_in_fifo_order_one_at_a_time():
    gate = threading.Event()
    seen = []

    def first():
        seen.append("first-start")
        gate.wait(5)
        seen.append("first-end")
        return "one"

    enqueue(SESSION, QueueItem(label="First", run=first))
    enqueue(SESSION, QueueItem(label="Second", run=lambda: seen.append("second")))

    _wait_until(lambda: snapshot(SESSION)[0].status == STATUS_RUNNING)
    assert seen == ["first-start"]
    assert snapshot(SESSION)[1].status == STATUS_PENDING

    gate.set()
    _wait_until(lambda: not is_busy(SESSION))
    assert seen == ["first-start", "first-end", "second"]


def test_success_is_drained_exactly_once():
    item_id = enqueue(SESSION, QueueItem(label="A", run=lambda: "value"))
    _wait_until(lambda: not is_busy(SESSION))

    first = drain_results(SESSION)
    assert [(item.id, item.status, item.result) for item in first] == [
        (item_id, STATUS_DONE, "value")
    ]
    assert drain_results(SESSION) == []


def test_exception_is_captured_and_drained():
    def boom():
        raise ValueError("nope")

    enqueue(SESSION, QueueItem(label="A", run=boom))
    _wait_until(lambda: not is_busy(SESSION))

    [item] = drain_results(SESSION)
    assert item.status == STATUS_FAILED
    assert isinstance(item.error, ValueError)
    assert item.result is None


def test_cancel_removes_a_pending_item_and_it_never_runs():
    gate = threading.Event()
    ran = []
    enqueue(SESSION, QueueItem(label="A", run=lambda: gate.wait(5) or "a"))
    _wait_until(lambda: snapshot(SESSION)[0].status == STATUS_RUNNING)
    pending_id = enqueue(SESSION, QueueItem(label="B", run=lambda: ran.append("b")))

    assert cancel(SESSION, pending_id) is True
    assert [item.label for item in snapshot(SESSION)] == ["A"]

    gate.set()
    _wait_until(lambda: not is_busy(SESSION))
    assert ran == []


def test_cancel_is_refused_for_a_running_item():
    gate = threading.Event()
    item_id = enqueue(
        SESSION,
        QueueItem(label="A", run=lambda: "done" if gate.wait(5) else "timeout"),
    )
    _wait_until(lambda: snapshot(SESSION)[0].status == STATUS_RUNNING)

    assert cancel(SESSION, item_id) is False

    gate.set()
    _wait_until(lambda: not is_busy(SESSION))
    [item] = drain_results(SESSION)
    assert item.status == STATUS_DONE
    assert item.result == "done"


def test_progress_is_monotonic_and_clamped():
    gate = threading.Event()
    item_id = enqueue(SESSION, QueueItem(label="A", run=lambda: gate.wait(5) or "x"))
    _wait_until(lambda: snapshot(SESSION)[0].status == STATUS_RUNNING)

    set_progress(SESSION, item_id, 5, 10)
    set_progress(SESSION, item_id, 3, 10)  # backwards: ignored
    set_progress(SESSION, item_id, 20, 10)  # clamped to total
    assert snapshot(SESSION)[0].progress == (10, 10)

    gate.set()


def test_progress_is_ignored_before_the_item_runs():
    gate = threading.Event()
    enqueue(SESSION, QueueItem(label="A", run=lambda: gate.wait(5) or "a"))
    pending_id = enqueue(SESSION, QueueItem(label="B", run=lambda: "b"))
    _wait_until(lambda: snapshot(SESSION)[0].status == STATUS_RUNNING)

    set_progress(SESSION, pending_id, 1, 10)

    assert snapshot(SESSION)[1].progress is None
    gate.set()


def test_snapshot_returns_copies():
    enqueue(SESSION, QueueItem(label="A", run=lambda: "value"))
    _wait_until(lambda: not is_busy(SESSION))

    copy = snapshot(SESSION)[0]
    copy.status = STATUS_FAILED
    copy.progress = (1, 1)

    live = snapshot(SESSION)[0]
    assert live.status == STATUS_DONE
    assert live.progress is None


def test_sessions_are_isolated():
    enqueue("one", QueueItem(label="A", run=lambda: "x"))

    assert snapshot("two") == []
    assert is_busy("two") is False

    _wait_until(lambda: not is_busy("one"))
    assert [item.label for item in snapshot("one")] == ["A"]


def test_unknown_session_is_empty_and_idle():
    assert snapshot("never-used") == []
    assert is_busy("never-used") is False
    assert drain_results("never-used") == []
    assert cancel("never-used", "nope") is False


def test_run_now_executes_on_the_calling_thread():
    item = QueueItem(label="A", run=lambda: "value")

    item_id = run_now("inline", item)

    assert item_id
    assert not is_busy("inline")
    [drained] = drain_results("inline")
    assert drained.status == STATUS_DONE
    assert drained.result == "value"


def test_clear_finished_waits_for_an_unapplied_result():
    enqueue(SESSION, QueueItem(label="A", run=lambda: "value"))
    _wait_until(lambda: not is_busy(SESSION))

    clear_finished(SESSION)
    assert [item.label for item in snapshot(SESSION)] == ["A"]

    drain_results(SESSION)
    clear_finished(SESSION)
    assert snapshot(SESSION) == []


def test_reset_queue_discards_the_running_result_and_keeps_new_work_apart():
    gate = threading.Event()
    enqueue(
        SESSION,
        QueueItem(label="A", run=lambda: "late" if gate.wait(5) else "timeout"),
    )
    _wait_until(lambda: snapshot(SESSION)[0].status == STATUS_RUNNING)

    reset_queue(SESSION)
    assert snapshot(SESSION) == []

    gate.set()
    enqueue(SESSION, QueueItem(label="B", run=lambda: "fresh"))
    _wait_until(lambda: not is_busy(SESSION))

    drained = drain_results(SESSION)
    assert [item.label for item in drained] == ["B"]
    assert drained[0].result == "fresh"


def test_stuck_item_is_reported_failed(monkeypatch):
    started = threading.Event()
    gate = threading.Event()

    def run():
        started.set()
        return "late" if gate.wait(5) else "timeout"

    enqueue(SESSION, QueueItem(label="A", run=run))
    assert started.wait(5)
    _wait_until(lambda: snapshot(SESSION)[0].status == STATUS_RUNNING)

    # Shrink the deadline only after the item is observed running: with a
    # tiny deadline from the start, snapshot() can settle it before the poll
    # ever sees STATUS_RUNNING (the flake this test used to hit).
    monkeypatch.setattr(action_queue, "ITEM_TIMEOUT_S", 0.01)
    _wait_until(lambda: snapshot(SESSION)[0].status == STATUS_FAILED)
    [item] = drain_results(SESSION)
    assert isinstance(item.error, TimeoutError)

    gate.set()
    _wait_until(lambda: not is_busy(SESSION))
    # The late result must not overwrite the terminal timeout state.
    assert snapshot(SESSION)[0].status == STATUS_FAILED
    assert snapshot(SESSION)[0].result is None
