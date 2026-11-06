"""Fast UI smoke test for the app layout.

One module-scoped ``AppTest`` instance is shared by all assertions: a single
``AppTest.run()`` costs 10-30 s (full Streamlit script run), so running it per
test made the suite unusable (see plan.md T-81).

The cache path is skipped explicitly: ``auto_load_cache=False`` stops
``load_initial_volume()`` from touching the 87 KB cache file with its hundreds
of dead network paths, which alone cost ~3.6 s per run.
"""

import os
import tempfile
from pathlib import Path

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[2] / "src" / "visualization" / "app.py"

SIDEBAR_SECTIONS = ["Image", "Projection Geometry", "Measurements"]
TAB_LABELS = ["🩻 Viewer", "📐 Geometry", "⚡ Real vs Simulated"]


@pytest.fixture(scope="module")
def app():
    at = AppTest.from_file(str(APP_PATH), default_timeout=90)
    at.session_state["auto_load_cache"] = False
    at.run()
    return at


def test_app_renders_without_exception(app):
    assert list(app.exception) == []


def test_three_tabs_are_rendered_in_order(app):
    assert [tab.label for tab in app.tabs] == TAB_LABELS


def test_geometry_tab_shows_default_geometry_hint(app):
    """Fresh start loads no geometry file, so the app falls back to the default
    geometry and points at the upload control."""
    messages = " ".join(
        [info.value for info in app.info] + [caption.value for caption in app.caption]
    ).lower()
    assert "geometry file" in messages


def test_comparison_tab_lists_missing_inputs(app):
    messages = " ".join(info.value for info in app.info).lower()
    assert "measured data" in messages


def test_sidebar_sections_are_collapsible_in_order(app):
    assert [expander.label for expander in app.sidebar.expander] == SIDEBAR_SECTIONS


def test_image_and_measurements_start_expanded_geometry_collapsed(app):
    """The two frequently used sections are open; the geometry section, which
    is only needed when a geometry file exists, starts collapsed."""
    expanded = {
        expander.label: expander.proto.expanded for expander in app.sidebar.expander
    }
    assert expanded == {
        "Image": True,
        "Projection Geometry": False,
        "Measurements": True,
    }


def test_sidebar_no_longer_has_a_data_header(app):
    headers = [h.value for h in app.sidebar.header]
    assert "Data" not in headers


def _label(element) -> str:
    return getattr(element, "label", None) or getattr(element, "value", "")


def _index_of_sidebar_child(app, predicate) -> int:
    for index, child in app.sidebar.children.items():
        if predicate(child):
            return index
    raise AssertionError("Sidebar element not found")


def test_cache_controls_are_above_the_image_section(app):
    """Cache controls must come before the image section, so they are visible
    without scrolling past the whole load section."""
    cache_index = _index_of_sidebar_child(
        app, lambda e: "Auto-load cache" in str(_label(e))
    )
    clear_index = _index_of_sidebar_child(
        app, lambda e: str(_label(e)).endswith("Clear Cache")
    )
    image_index = _index_of_sidebar_child(
        app, lambda e: getattr(e, "type", "") == "expander" and _label(e) == "Image"
    )

    assert cache_index < image_index
    assert clear_index < image_index


def test_load_measurements_from_npy(app):
    """The measurement loader works through the new Measurements expander."""
    expected = np.arange(4 * 6 * 8, dtype=np.float32).reshape(4, 6, 8)
    with tempfile.TemporaryDirectory() as tmp_dir:
        sinogram_path = Path(tmp_dir) / "sinogram.npy"
        np.save(sinogram_path, expected)

        app.sidebar.text_input(key="sinogram_path").set_value(str(sinogram_path))
        app.sidebar.button(key="load_measurements").click()
        app.run()

    assert list(app.exception) == []
    assert "sinogram" in app.session_state
    loaded = app.session_state["sinogram"]
    assert loaded.data.shape == (4, 6, 8)
    np.testing.assert_array_equal(loaded.data, expected)
