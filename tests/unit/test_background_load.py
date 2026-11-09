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
    waited = 0.0
    while waited < timeout:
        status, _, _ = job_state(name)
        if status != STATUS_RUNNING:
            return status
        threading.Event().wait(0.01)
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

    assert _wait_until_settled("startup") == STATUS_FAILED
    status, result, error = job_state("startup")
    assert status == STATUS_FAILED
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

    def boom():
        raise RuntimeError("x")

    run_and_capture(state, boom)

    assert state["status"] == STATUS_FAILED
