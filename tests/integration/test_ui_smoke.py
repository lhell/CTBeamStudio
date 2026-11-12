"""Fast UI smoke test for the app layout.

One module-scoped ``AppTest`` instance is shared by all assertions: a single
``AppTest.run()`` costs 10-30 s (full Streamlit script run), so running it per
test made the suite unusable (see plan.md T-81).

A demo volume is seeded into session state before the first run. Startup
loading happens in a background thread (see
docs/superpowers/specs/2026-11-09-background-startup-load-design.md), so
without a seed the viewer would render the empty state instead of the
3D plot these assertions expect. Startup behaviour is covered by
tests/unit/test_background_load.py and test_startup_selection.py.
"""

import json
import os
import tempfile
from pathlib import Path

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from backend.forward_project import ForwardProjectionResult
from backend.geometry import ProjectionGeometry
from backend.loaders.sinogram import SelectionConfig, SinogramData
from visualization.phantom import create_demo_volume

APP_PATH = Path(__file__).resolve().parents[2] / "src" / "visualization" / "app.py"

SIDEBAR_SECTIONS = ["Image", "Projection Geometry", "Measurements"]
TAB_LABELS = ["🩻 Viewer", "📐 Geometry", "🔍 Sinogram Inspection"]


@pytest.fixture(scope="module")
def app():
    at = AppTest.from_file(str(APP_PATH), default_timeout=90)
    # Seed a volume so the app starts in the state these assertions were
    # written against ("a volume is present"). ``at.run()`` used to block until
    # startup loading finished; now loading happens in a background thread, so
    # without a seed the viewer would render the status block instead of the 3D
    # plot. Startup behaviour itself is covered by tests/unit, not here, because
    # ``st.fragment(run_every=...)`` never fires under AppTest.
    at.session_state["volume"] = create_demo_volume()
    at.run()
    return at


def test_app_renders_without_exception(app):
    assert list(app.exception) == []


def test_no_completed_load_status_is_shown(app):
    """A completed ``st.status`` box is permanent: it would sit above the
    viewer for the rest of the session. Loading is a one-shot event, so the
    app never leaves a completed status element behind.

    The completion toast itself is emitted inside the polling fragment, which
    cannot be driven under AppTest (``run_every`` never fires), so it is not
    asserted here.
    """
    status_labels = [status.label for status in app.status]

    assert "Daten geladen" not in status_labels


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


def test_image_expanded_geometry_and_measurements_collapsed(app):
    """Only the image section is open. Geometry is only needed when a geometry
    file exists, and measured data is an optional second input, so both start
    collapsed to keep the actual load controls near the top."""
    expanded = {
        expander.label: expander.proto.expanded for expander in app.sidebar.expander
    }
    assert expanded == {
        "Image": True,
        "Projection Geometry": False,
        "Measurements": False,
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


def test_clear_cache_is_above_the_image_section(app):
    """Clear Cache must come before the image section, so it is visible
    without scrolling past the whole load section. The cache is always on, so
    there is no Auto-load checkbox any more."""
    clear_index = _index_of_sidebar_child(
        app, lambda e: str(_label(e)).endswith("Clear Cache")
    )
    image_index = _index_of_sidebar_child(
        app, lambda e: getattr(e, "type", "") == "expander" and _label(e) == "Image"
    )

    assert clear_index < image_index

    labels = [str(_label(child)) for child in app.sidebar.children.values()]
    assert not any("Auto-load cache" in label for label in labels)


def test_startup_shows_an_empty_state_with_both_load_actions():
    """A fresh start loads nothing automatically: the viewer shows "Nothing to
    show" and offers the sidebar plus the demo phantom as the two ways in.

    Uses its own AppTest (no seeded volume) because the shared fixture starts
    with a volume present.
    """
    at = AppTest.from_file(str(APP_PATH), default_timeout=90)
    at.run()

    assert list(at.exception) == []

    messages = " ".join(info.value for info in at.info).lower()
    assert "nothing to show" in messages

    labels = [button.label for button in at.button]
    assert "Load Demo Phantom" in labels


def test_3d_plot_has_a_projection_geometry_toggle_in_the_corner(app):
    """The geometry overlay is switched on/off from inside the Plotly canvas:
    the spec carries the button pair, and its Off button hides every overlay
    trace while keeping the volume visible."""
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


def test_viewer_options_are_floating_popovers(app):
    """The option panels float over the views instead of pushing them down.

    Both used to be always-open expanders above the canvas, so every control
    pushed the 3D view further down the page.
    """
    labels = [block.proto.popover.label for block in app.get("popover")]

    assert "⚙️ Slice Options" in labels
    assert "⚙️ 3D Options" in labels


def test_view_switcher_offers_all_three_layouts(app):
    """The All / 2D / 3D switcher is the only way to change the split, and it
    must be rendered outside the columns so it survives a collapse."""
    switchers = [radio for radio in app.radio if radio.key == "viewer_view"]

    assert len(switchers) == 1
    assert list(switchers[0].options) == ["All", "2D", "3D"]
    assert switchers[0].value == "All"


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


def test_changing_axis_order_reorients_without_reloading(app):
    """Picking a different file axis order must redraw immediately.

    The dropdown is the user's only way to say "the file is stored the other
    way round", and they judge it by looking at the image. Requiring a second
    click on Load Measurements makes the control appear broken.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        sinogram_path = Path(tmp_dir) / "axis_order.npy"
        np.save(sinogram_path, np.zeros((4, 6, 8), dtype=np.float32))

        app.sidebar.text_input(key="sinogram_path").set_value(str(sinogram_path))
        app.sidebar.button(key="load_measurements").click()
        app.run()
        assert app.session_state["sinogram"].data.shape == (4, 6, 8)

        app.sidebar.selectbox(key="sinogram_axis_order").set_value(
            ("proj", "col", "row")
        )
        app.run()

        assert list(app.exception) == []
        assert app.session_state["sinogram"].data.shape == (4, 8, 6)
        assert app.session_state["sinogram"].axis_order == ("proj", "col", "row")

        # The AppTest instance is module-scoped: restore the canonical order so
        # later tests do not inherit this declaration for their seeded data.
        app.sidebar.selectbox(key="sinogram_axis_order").set_value(
            ("proj", "row", "col")
        )
        app.run()


def test_sidebar_shows_absolute_path_of_loaded_measurements(app):
    """The Measurements panel must name the exact file it loaded, so a user
    can tell several sinograms apart without trusting the text input."""
    expected = np.arange(4 * 6 * 8, dtype=np.float32).reshape(4, 6, 8)
    with tempfile.TemporaryDirectory() as tmp_dir:
        sinogram_path = Path(tmp_dir) / "path_check.npy"
        np.save(sinogram_path, expected)

        app.sidebar.text_input(key="sinogram_path").set_value(str(sinogram_path))
        app.sidebar.button(key="load_measurements").click()
        app.run()

        sidebar_text = " ".join(c.value for c in app.get("caption"))

    assert list(app.exception) == []
    assert "Path:" in sidebar_text
    assert str(sinogram_path.resolve()) in sidebar_text
    assert "path_check.npy" in sidebar_text


def test_sidebar_lists_every_file_read_for_a_folder_load(app, create_projection_dicom):
    """A DICOM folder load must list the files actually read, not just the
    folder — the user needs to see which projections went in."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        folder = create_projection_dicom(tmp_dir)

        app.sidebar.text_input(key="sinogram_path").set_value(str(folder))
        app.sidebar.button(key="load_measurements").click()
        app.run()

        text = " ".join(
            [c.value for c in app.get("caption")] + [c.value for c in app.get("code")]
        )

    assert list(app.exception) == []
    assert "Files read: 3" in text
    for index in range(3):
        assert f"proj_{index}.dcm" in text


# ---------------------------------------------------------------------------
# Sinogram Inspection tab
# ---------------------------------------------------------------------------

# Calculated from the default geometry (2304 projections, 64 rows, 512
# columns) with the tab's fp defaults (proj step 100, row step 4, col step
# 8): ceil-ish index counts 2304/100=24, 64/4=16, 512/8=64.
FP_DEFAULT_SIM_SHAPE = (24, 16, 64)


def _seed_measurements(at, shape, fmt="numpy"):
    rng = np.random.default_rng(7)
    data = rng.random(shape, dtype=np.float32)
    at.session_state["sinogram"] = SinogramData(
        data=data,
        geometry=None,
        selection=SelectionConfig(),
        original_shape=tuple(shape),
        source_axis_order=("proj", "row", "col"),
        path=None,
        format=fmt,
    )
    return data


def _main_text(at) -> str:
    """Concatenate every caption/info/warning string rendered in main."""
    return " ".join(
        [c.value for c in at.caption]
        + [i.value for i in at.info]
        + [w.value for w in at.warning]
    )


def test_sinogram_inspection_renders_single_projection(app):
    """The user's exact case: measurements (1, 736, 64) must be visible with
    a volume loaded, before any forward projection runs."""
    app.session_state["volume"] = create_demo_volume()
    _seed_measurements(app, shape=(1, 736, 64))

    app.run()

    assert list(app.exception) == []
    text = _main_text(app)
    assert "Measured: (1, 736, 64)" in text
    assert "Measured projection 1/1" in text


def test_sinogram_inspection_crash_regression_no_volume(app):
    """Regression: with no volume, the old preview branch rendered a
    0..0 slider for a 1-projection sinogram and raised
    StreamlitAPIException ('min_value must be less than max_value')."""
    app.session_state["volume"] = None
    _seed_measurements(app, shape=(1, 736, 64))

    app.run()

    assert list(app.exception) == []
    text = _main_text(app)
    assert "Measured projection 1/1" in text
    assert "run the forward projection" in text.lower()


def test_sinogram_inspection_shape_mismatch_hints(app):
    """Shapes differ → both image columns stay visible, difference and
    metric plots are omitted with an in-slot hint, no exception."""
    app.session_state["volume"] = create_demo_volume()
    _seed_measurements(app, shape=(1, 736, 64))
    app.session_state["forward_projection"] = ForwardProjectionResult(
        projections=np.zeros((2, 3, 4), dtype=np.float32),
        geometry=ProjectionGeometry(),
        row_indices=[0, 1],
        col_indices=[0, 1, 2],
        proj_indices=[0, 1],
    )

    app.run()

    assert list(app.exception) == []
    text = _main_text(app)
    assert "shapes differ" in text.lower()
    assert "Measured projection 1/1" in text
    assert "Simulated: (2, 3, 4)" in text


def test_sinogram_inspection_empty_frame_hints(app):
    """Nothing loaded → the frame renders with hints, not a dead end."""
    app.session_state["sinogram"] = None
    app.session_state["forward_projection"] = None
    app.session_state["volume"] = create_demo_volume()

    app.run()

    assert list(app.exception) == []
    hints = _main_text(app).lower()
    assert "measured data" in hints
    assert "run the forward projection" in hints


def _block_heights(node) -> list[int]:
    """Collect the fixed heights of every ``st.container(height=...)``."""
    heights = []
    proto = getattr(node, "proto", None)
    if proto is not None:
        try:
            if proto.HasField("vertical") and proto.vertical.height:
                heights.append(proto.vertical.height)
        except Exception:
            pass
    for child in (getattr(node, "children", {}) or {}).values():
        heights.extend(_block_heights(child))
    return heights


def test_sinogram_inspection_placeholders_are_square_blocks(app):
    """The empty slots must reserve the same vertical space a projection
    image will occupy, so the layout does not jump when data arrives.

    A one-line st.info leaves the three columns as thin strips. Each empty
    slot therefore renders inside a fixed-height, square-ish container.
    """
    from visualization.projection_panel import PLACEHOLDER_HEIGHT_PX

    app.session_state["sinogram"] = None
    app.session_state["forward_projection"] = None
    app.session_state["volume"] = create_demo_volume()

    app.run()

    assert list(app.exception) == []
    # Square-ish: tall enough to match an image slot rather than a one-line
    # hint. (The viewer's own image box uses a different height, so match on
    # the placeholder's rather than counting every sized block in the app.)
    assert PLACEHOLDER_HEIGHT_PX >= 240
    heights = [h for h in _block_heights(app.main) if h == PLACEHOLDER_HEIGHT_PX]
    # One per empty slot: measured, simulated, difference.
    assert len(heights) == 3, heights


def test_sinogram_inspection_run_button_produces_simulation(app):
    """Placeholder backend: with a matching measured shape (fp defaults
    on the default geometry yield the (24, 16, 64) simulated stack),
    clicking Run fills the simulated column and the metric plots,
    without exception."""
    app.session_state["volume"] = create_demo_volume()
    _seed_measurements(app, shape=FP_DEFAULT_SIM_SHAPE)

    app.button(key="fp_run").click()
    app.run()

    assert list(app.exception) == []
    text = _main_text(app)
    assert "Simulated: (24, 16, 64)" in text
    assert "Simulated projection" in text
