"""Tests for the action definitions and the main-thread drain."""

from types import SimpleNamespace

import pytest

from visualization import action_queue, actions
from visualization.action_queue import QueueItem


@pytest.fixture(autouse=True)
def clean_queue():
    action_queue.clear_registry()
    yield
    action_queue.clear_registry()


def _series(files):
    return SimpleNamespace(files=list(files), n_slices=len(files), patient_id="P")


def _volume(shape=(1, 1, 1)):
    return SimpleNamespace(array=SimpleNamespace(shape=shape), n_slices=shape[0])


def test_series_file_list_prefers_the_series_and_honours_the_limit(tmp_path):
    selected = _series([tmp_path / "a.dcm", tmp_path / "b.dcm"])

    assert actions.series_file_list(selected, 1, tmp_path) == [tmp_path / "a.dcm"]
    assert actions.series_file_list(selected, None, tmp_path) == list(selected.files)


def test_series_file_list_falls_back_to_the_folder(tmp_path):
    (tmp_path / "a.dcm").write_text("x")
    (tmp_path / "b.dcm").write_text("x")

    files = actions.series_file_list(_series([]), None, tmp_path)

    assert sorted(path.name for path in files) == ["a.dcm", "b.dcm"]


def test_apply_series_writes_state_and_persists(tmp_path):
    files = [tmp_path / "a.dcm"]
    volume = _volume()
    state = {
        "volume": "old",
        "axial_slice": 4,
        "coronal_slice": 5,
        "sagittal_slice": 6,
    }
    saved = []

    message = actions.apply_series(
        volume, state, series="S", files=files, save_cache=saved.append
    )

    assert state["volume"] is volume
    assert state["series"] == "S"
    assert state["loaded_files"] == files
    assert not {"axial_slice", "coronal_slice", "sagittal_slice"} & set(state)
    assert saved == [files]
    assert message == "Loaded 1 slices!"


def test_apply_measurements_sets_the_sinogram():
    state = {}

    message = actions.apply_measurements("sino", state)

    assert state["sinogram"] == "sino"
    assert message == "Measurements loaded!"


def test_apply_dummy_measurement_sets_the_trio_and_presets():
    dummy = SimpleNamespace(
        volume="V", geometry="G", sinogram="S", params={"fp_from_cache": False}
    )
    cleared = []
    state = {}

    message = actions.apply_dummy_measurement(
        dummy, state, clear_edits=lambda: cleared.append(True)
    )

    assert state == {
        "volume": "V",
        "projection_geometry": "G",
        "geometry_is_default": False,
        "geometry_loaded_original": "G",
        "sinogram": "S",
        "sample_proj_mode": "all",
        "sample_row_mode": "all",
        "sample_col_mode": "all",
    }
    assert cleared == [True]
    assert message == "Dummy measurement ready (projection computed)."


def test_apply_forward_projection_sets_the_result():
    result = SimpleNamespace(projections=SimpleNamespace(shape=(3, 2, 2)))
    state = {}

    message = actions.apply_forward_projection(result, state)

    assert state["forward_projection"] is result
    assert message == "Computed 3 projections."


def test_drain_applies_each_finished_item_once():
    state = {}
    notes = []

    def apply(value, target):
        target["value"] = value
        return "applied A"

    item = QueueItem(label="A", run=lambda: "value", apply=apply)
    action_queue.run_now("drain-test", item)

    first = actions.drain_action_results(
        "drain-test", state=state, notify=lambda level, msg: notes.append((level, msg))
    )

    assert state["value"] == "value"
    assert [item.label for item in first] == ["A"]
    assert notes == [("success", "applied A")]

    again = actions.drain_action_results(
        "drain-test", state=state, notify=lambda level, msg: notes.append((level, msg))
    )
    assert again == []
    assert len(notes) == 1


def test_drain_reports_a_failed_action_without_applying():
    notes = []
    applied = []

    def boom():
        raise ValueError("nope")

    item = QueueItem(
        label="Load Measurements",
        run=boom,
        apply=lambda result, state: applied.append(result),
    )
    action_queue.run_now("drain-fail", item)

    actions.drain_action_results(
        "drain-fail",
        state={},
        notify=lambda level, msg: notes.append((level, msg)),
    )

    assert applied == []
    assert notes[0][0] == "error"
    assert "Load Measurements failed" in notes[0][1]
    assert "nope" in notes[0][1]


def test_drain_reports_a_failing_apply():
    notes = []
    item = QueueItem(
        label="A",
        run=lambda: "value",
        apply=lambda result, state: 1 / 0,
    )
    action_queue.run_now("drain-apply-fail", item)

    actions.drain_action_results(
        "drain-apply-fail",
        state={},
        notify=lambda level, msg: notes.append((level, msg)),
    )

    assert notes[0][0] == "error"
    assert "could not be applied" in notes[0][1]


def test_inline_submit_runs_and_applies_on_the_calling_thread(monkeypatch, tmp_path):
    import streamlit as st

    volume = _volume(shape=(2, 2, 2))
    saved = []
    monkeypatch.setattr(
        "visualization.volume_cache.load_volume_cached",
        lambda paths, **kwargs: volume,
    )
    monkeypatch.setattr("visualization.volume_cache.save_last_loaded", saved.append)

    st.session_state["actions_inline"] = True
    try:
        files = [tmp_path / "a.dcm"]
        item_id = actions.enqueue_series("inline-session", files, _series(files))

        assert st.session_state["volume"] is volume
        [item] = action_queue.snapshot("inline-session")
        assert item.id == item_id
        assert item.status == action_queue.STATUS_DONE
        assert saved == [files]
    finally:
        for key in ("actions_inline", "volume", "series", "loaded_files"):
            st.session_state.pop(key, None)


def test_inline_submit_keeps_a_failed_action_visible(monkeypatch):
    import streamlit as st

    def boom(paths, **kwargs):
        raise OSError("disk gone")

    monkeypatch.setattr("visualization.volume_cache.load_volume_cached", boom)
    st.session_state["actions_inline"] = True
    try:
        actions.enqueue_series("inline-fail", ["a.dcm"], _series(["a.dcm"]))

        [item] = action_queue.snapshot("inline-fail")
        assert item.status == action_queue.STATUS_FAILED
        assert isinstance(item.error, OSError)
        assert "volume" not in st.session_state
    finally:
        st.session_state.pop("actions_inline", None)


def test_elapsed_time_freezes_when_an_item_finishes():
    item = QueueItem(label="A", run=lambda: None)
    item.started_at = 100.0
    item.finished_at = 103.5
    item.status = action_queue.STATUS_DONE

    assert actions._elapsed(item, now=500.0) == 3.5

    item.status = action_queue.STATUS_RUNNING
    assert actions._elapsed(item, now=500.0) == 400.0
