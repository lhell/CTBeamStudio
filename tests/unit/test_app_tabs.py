"""Headless Streamlit smoke tests for the tab layout and measurement loader."""

from pathlib import Path

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[2] / "src" / "visualization" / "app.py"
TAB_LABELS = ["🩻 Viewer", "📐 Geometry", "⚡ Real vs Simulated"]


@pytest.fixture()
def app():
    # A full app run builds the demo phantom, which is slow on a busy machine.
    at = AppTest.from_file(str(APP_PATH), default_timeout=180)
    at.run()
    return at


def test_app_renders_without_exception(app):
    assert list(app.exception) == []


def test_three_tabs_are_rendered_in_order(app):
    assert [tab.label for tab in app.tabs] == TAB_LABELS


def test_sidebar_has_measurement_controls(app):
    text_input_keys = {widget.key for widget in app.sidebar.text_input}
    assert "sinogram_path" in text_input_keys

    button_labels = [button.label for button in app.sidebar.button]
    assert "Load Measurements" in button_labels


def test_geometry_tab_shows_default_geometry_hint(app):
    # No geometry file is loaded on a fresh start, so the app falls back to
    # the default (or cached) geometry and points at the upload control.
    messages = " ".join(
        [info.value for info in app.info] + [caption.value for caption in app.caption]
    ).lower()
    assert "geometry file" in messages


def test_comparison_tab_lists_missing_inputs(app):
    messages = " ".join(info.value for info in app.info).lower()
    assert "measured data" in messages


def test_load_measurements_from_npy(tmp_path):
    sinogram_path = tmp_path / "sinogram.npy"
    expected = np.arange(4 * 6 * 8, dtype=np.float32).reshape(4, 6, 8)
    np.save(sinogram_path, expected)

    # A full app run builds the demo phantom, which is slow on a busy machine.
    at = AppTest.from_file(str(APP_PATH), default_timeout=180)
    at.run()
    at.sidebar.text_input(key="sinogram_path").set_value(str(sinogram_path))
    at.sidebar.button(key="load_measurements").click()
    at.run()

    assert list(at.exception) == []
    assert "sinogram" in at.session_state
    loaded = at.session_state["sinogram"]
    assert loaded.data.shape == (4, 6, 8)
    np.testing.assert_array_equal(loaded.data, expected)
