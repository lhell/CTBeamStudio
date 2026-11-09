"""Fast UI smoke test for the app layout.

One module-scoped ``AppTest`` instance is shared by all assertions: a single
``AppTest.run()`` costs 10-30 s (full Streamlit script run), so running it per
test made the suite unusable (see plan.md T-81).

The cache path is skipped explicitly: ``auto_load_cache=False`` stops
``load_initial_volume()`` from touching the 87 KB cache file with its hundreds
of dead network paths, which alone cost ~3.6 s per run.
"""

import json
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


def test_load_completion_message_does_not_stay_on_screen(app):
    """A completed ``st.status`` box is permanent: it would sit above the
    viewer for the rest of the session. Loading is a one-shot event, so the
    completion notice is a toast, which dismisses itself after ~5 s."""
    status_labels = [status.label for status in app.status]

    assert "Daten geladen" not in status_labels
    assert any("Daten geladen" in toast.value for toast in app.toast)


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


def test_3d_plot_has_a_projection_geometry_toggle_in_the_corner(app):
    """The geometry overlay is switched on/off from inside the Plotly canvas:
    the spec carries the slider, and its Off step hides every overlay trace
    while keeping the volume visible."""
    spec = None
    for key, child in app.main.children.items():
        for element in _walk(child):
            if getattr(element, "type", None) == "plotly_chart" or hasattr(
                element, "spec"
            ):
                spec = element.spec
                break
    assert spec is not None, "no Plotly chart found"

    chart = json.loads(spec)
    menus = chart["layout"]["updatemenus"]
    assert len(menus) == 1
    assert menus[0]["type"] == "buttons"
    assert menus[0]["xanchor"] == "right"
    assert menus[0]["yanchor"] == "bottom"
    assert [button["label"] for button in menus[0]["buttons"]] == ["On", "Off"]

    # It is a click control, not a drag slider.
    assert chart["layout"].get("sliders", []) == []

    texts = [annotation.get("text") for annotation in chart["layout"]["annotations"]]
    assert "Projection Geometry" in texts

    on_visible = menus[0]["buttons"][0]["args"][0]["visible"]
    off_visible = menus[0]["buttons"][1]["args"][0]["visible"]
    assert len(on_visible) == len(chart["data"])
    assert all(on_visible)
    # The iso-surface volume traces stay; the overlay traces go away.
    assert any(off_visible)
    assert not all(off_visible)


def _walk(element):
    yield element
    for child in getattr(element, "children", {}).values():
        yield from _walk(child)


def test_3d_options_no_longer_offer_a_show_trajectory_checkbox(app):
    """The trajectory is chosen automatically when a geometry is loaded, and
    the overlay is switched from the in-plot control. A second driver for the
    same thing would only be able to contradict it."""
    labels = [checkbox.label for checkbox in app.checkbox]

    assert "Show Trajectory" not in labels


def test_render_mode_offers_only_iso_surface(app):
    """The PyVista render mode is shelved for now: it produced a static PNG,
    so it could not host the interactive geometry toggle. Only the Plotly
    iso-surface path is offered until it is re-enabled."""
    render_modes = [box for box in app.selectbox if box.label == "Render Mode"]

    assert len(render_modes) == 1
    assert list(render_modes[0].options) == ["Iso-Surface"]
    assert render_modes[0].value == "iso"


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
