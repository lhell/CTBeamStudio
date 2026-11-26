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
from visualization.phantom import DummyMeasurement, create_demo_volume

APP_PATH = Path(__file__).resolve().parents[2] / "src" / "visualization" / "app.py"

SIDEBAR_SECTIONS = ["Image", "Measurements"]
TAB_LABELS = [
    "🩻 Viewer",
    "📐 Geometry",
    "🚀 Forward Projection",
    "🔍 Sinogram Inspection",
]


@pytest.fixture(scope="module")
def app():
    at = AppTest.from_file(str(APP_PATH), default_timeout=90)
    # Seed a volume and the dataclass-default geometry so the app starts in
    # the state these assertions were written against. Without the geometry
    # seed the app restores the machine's data/.last_geometry.json cache
    # (the last loaded or edited geometry), which makes the simulated FP
    # shapes machine-dependent.
    at.session_state["volume"] = create_demo_volume()
    at.session_state["projection_geometry"] = ProjectionGeometry()
    at.session_state["geometry_is_default"] = True
    at.session_state["geometry_loaded_original"] = ProjectionGeometry()
    # The worker-driven queue cannot advance under AppTest (run_every fragments
    # never fire). Run actions inline so click-then-assert tests still observe
    # their result in the same run, exactly as they did before T-109.
    at.session_state["actions_inline"] = True
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


def test_tabs_are_rendered_in_order(app):
    assert [tab.label for tab in app.tabs] == TAB_LABELS


def test_geometry_tab_shows_default_geometry_hint(app):
    """Fresh start loads no geometry file, so the app falls back to the default
    geometry and points at the upload control."""
    messages = " ".join(
        [info.value for info in app.info] + [caption.value for caption in app.caption]
    ).lower()
    assert "geometry file" in messages


def test_comparison_tab_lists_missing_inputs(app):
    """Empty slots are square placeholder divs (markdown), not st.info."""
    messages = " ".join(
        [c.value for c in app.caption]
        + [m.value for m in app.markdown]
        + [i.value for i in app.info]
    ).lower()
    assert "measured data" in messages


def test_sidebar_sections_are_collapsible_in_order(app):
    assert [expander.label for expander in app.sidebar.expander] == SIDEBAR_SECTIONS


def test_image_expanded_and_measurements_collapsed(app):
    """Only the image section is open. Measured data is an optional second
    input, so it starts collapsed to keep the load controls near the top. The
    `Show queue` switch is a plain checkbox, not another expander."""
    expanded = {
        expander.label: expander.proto.expanded for expander in app.sidebar.expander
    }
    assert expanded == {
        "Image": True,
        "Measurements": False,
    }


def test_show_queue_switch_is_off_by_default(app):
    """The queue is a developer tool: present, but hidden until asked for."""
    boxes = {box.label: box for box in app.sidebar.checkbox}

    assert "Show queue" in boxes
    assert boxes["Show queue"].value is False


def test_show_queue_lists_pending_actions_with_cancel(app):
    """Option A: queued clicks are visible and only pending ones can be
    cancelled. A real worker is held on a gate so the second item stays
    pending; the poller's run_every cannot be driven under AppTest, but its
    first render still shows the live snapshot.
    """
    import threading

    from visualization import action_queue

    token = app.session_state["action_queue_token"]
    gate = threading.Event()
    action_queue.enqueue(
        token,
        action_queue.QueueItem(
            label="Blocking load",
            run=lambda: "ok" if gate.wait(30) else "timeout",
        ),
    )
    pending = action_queue.QueueItem(label="Queued Series", run=lambda: "never")
    pending_id = action_queue.enqueue(token, pending)

    app.sidebar.checkbox(key="dev_show_queue").check()
    try:
        app.run()

        captions = " ".join(c.value for c in app.get("caption"))
        assert "Blocking load · running" in captions
        assert "Queued Series · pending" in captions
        cancels = [b for b in app.sidebar.button if b.label == "✕ Cancel"]
        assert len(cancels) == 1

        cancels[0].click()
        app.run()
        assert pending_id not in [i.id for i in action_queue.snapshot(token)]
    finally:
        gate.set()
        action_queue.reset_queue(token)
        if "_action_queue_signature" in app.session_state:
            del app.session_state["_action_queue_signature"]
        app.sidebar.checkbox(key="dev_show_queue").uncheck()
        app.run()


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


def test_startup_shows_an_empty_state_with_both_load_actions(tmp_path, monkeypatch):
    """A fresh start loads nothing automatically: the viewer shows "Nothing to
    show" and offers the sidebar plus the demo phantom as the two ways in.

    Uses its own AppTest (no seeded volume) because the shared fixture starts
    with a volume present.
    """
    from visualization import volume_cache

    monkeypatch.setattr(volume_cache, "CACHE_FILE", tmp_path / "missing.json")
    at = AppTest.from_file(str(APP_PATH), default_timeout=90)
    at.run()

    assert list(at.exception) == []

    messages = " ".join(info.value for info in at.info).lower()
    assert "nothing to show" in messages

    labels = [button.label for button in at.button]
    assert "Load Demo Phantom" in labels


def _plotly_spec(app):
    """Return the parsed spec of the app's Plotly 3D chart."""
    for child in app.main.children.values():
        for element in _walk(child):
            if getattr(element, "type", None) == "plotly_chart" or hasattr(
                element, "spec"
            ):
                return json.loads(element.spec)
    raise AssertionError("no Plotly chart found")


def test_3d_plot_carries_no_in_canvas_overlay_button(app):
    """The overlay's on/off control is the "Show projections" checkbox in the
    3D options now, so the Plotly canvas itself carries neither an update menu
    nor a slider."""
    chart = _plotly_spec(app)

    assert chart["layout"].get("updatemenus", []) == []
    assert chart["layout"].get("sliders", []) == []


def test_3d_options_offer_the_show_projections_checkbox(app):
    """The overlay is switched from the 3D options, and starts visible."""
    boxes = {checkbox.label: checkbox for checkbox in app.checkbox}

    assert boxes["Show projections"].value is True


def test_projection_count_lives_in_the_geometry_tab(app):
    """The trajectory length is a scan property, so its control sits next to the
    geometry readouts instead of the sidebar."""
    counts = [box for box in app.number_input if box.label == "Projections"]

    assert len(counts) == 1
    assert counts[0].value == 2304


def _walk(element):
    yield element
    for child in getattr(element, "children", {}).values():
        yield from _walk(child)


def test_3d_options_no_longer_offer_a_show_trajectory_checkbox(app):
    """The trajectory is chosen automatically when a geometry is loaded, and
    the overlay is switched by the single "Show projections" checkbox. A second
    Show Trajectory driver could only contradict it."""
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

        # The AppTest instance is module-scoped: restore the canonical order
        # so later tests do not inherit this declaration for their seeded data.
        app.sidebar.selectbox(key="sinogram_axis_order").set_value(
            ("proj", "row", "col")
        )


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
# columns) with the Forward Projection tab's defaults (proj step 100, row
# step 4, col step 8): ceil-ish counts 2304/100=24, 64/4=16, 512/8=64.
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
    """Concatenate every caption/markdown/info/warning string rendered in main."""
    return " ".join(
        [c.value for c in at.caption]
        + [m.value for m in at.markdown]
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


def test_sinogram_inspection_placeholders_are_square_blocks(app):
    """The empty slots must reserve the same vertical space a projection
    image will occupy, so the layout does not jump when data arrives.

    Each empty slot renders a square ``.sino-placeholder`` box, squared off
    by the stylesheet injected with the tab (aspect-ratio 1/1 at the
    column's rendered width) to match the square comparison views around it.
    """
    app.session_state["sinogram"] = None
    app.session_state["forward_projection"] = None
    app.session_state["volume"] = create_demo_volume()

    app.run()

    assert list(app.exception) == []
    bodies = [m.value for m in app.markdown]
    placeholders = [b for b in bodies if 'class="sino-placeholder"' in b]
    # One per empty slot: measured, simulated, difference in both the
    # projection row and the row-sinogram row.
    assert len(placeholders) == 6, placeholders
    # The tab injects the stylesheet that squares the slots and the views.
    styles = [b for b in bodies if "aspect-ratio" in b]
    assert any("iframe.stIFrame" in b for b in styles), bodies
    assert any(".sino-placeholder" in b for b in styles), bodies


def test_sinogram_inspection_run_button_produces_simulation(app):
    """Placeholder backend: with a matching measured shape (fp defaults
    on the default geometry yield the (24, 16, 64) simulated stack),
    clicking Run fills the simulated column and the metric plots,
    without exception."""
    app.session_state["volume"] = create_demo_volume()
    _seed_measurements(app, shape=FP_DEFAULT_SIM_SHAPE)

    app.button(key="fp_run").click()
    app.run()
    # The click applies the inline result after the comparison views have been
    # drawn in that run; in production the queue poller supplies this rerun.
    app.run()

    assert list(app.exception) == []
    text = _main_text(app)
    assert "Simulated: (24, 16, 64)" in text
    assert "Simulated projection" in text


def test_forward_projection_run_is_blocked_without_parallelproj(app, monkeypatch):
    """Without parallelproj the run button refuses to start: queueing the
    placeholder backend could only fill the tab with warned-about zeros
    (T-11-04). The button stays enabled so the reason appears at click time,
    as an st.error next to the passive st.warning above it."""
    import backend.forward_project as fp_module

    monkeypatch.setattr(fp_module, "PARALLELPROJ_AVAILABLE", False)

    app.session_state["volume"] = create_demo_volume()
    app.session_state["forward_projection"] = None
    app.button(key="fp_run").click()
    app.run()

    assert list(app.exception) == []
    errors = " ".join(e.value for e in app.error)
    assert "parallelproj is not installed" in errors
    # Nothing was enqueued or computed: the result state stays empty.
    assert app.session_state["forward_projection"] is None


def test_sinogram_inspection_row_sinogram_row(app):
    """The second row shows the rows → cols → projections sinogram with its
    own row slider, independent of the projection index slider above."""
    app.session_state["volume"] = create_demo_volume()
    app.session_state["forward_projection"] = None
    _seed_measurements(app, shape=(3, 4, 5))
    app.session_state["sino_row_index"] = 2

    app.run()

    assert list(app.exception) == []
    text = _main_text(app)
    assert "Measured sinogram, row 3/4" in text
    labels = [s.label for s in app.slider]
    assert "Projection index" in labels
    assert "Row index" in labels
    assert app.session_state["sino_row_index"] == 2


def test_sinogram_inspection_difference_sinogram(app):
    """Matching shapes fill all three sinogram panels, including the
    difference, using the same selected row on both sides."""
    app.session_state["volume"] = create_demo_volume()
    measured = _seed_measurements(app, shape=(3, 4, 5))
    app.session_state["forward_projection"] = ForwardProjectionResult(
        projections=measured + 1.0,
        geometry=ProjectionGeometry(),
        row_indices=[0, 1, 2, 3],
        col_indices=[0, 1, 2, 3, 4],
        proj_indices=[0, 1, 2],
    )
    app.session_state["sino_row_index"] = 3

    app.run()

    assert list(app.exception) == []
    text = _main_text(app)
    assert "Measured sinogram, row 4/4" in text
    assert "Simulated sinogram, row 4/4" in text
    assert "Difference sinogram" in text


# ---------------------------------------------------------------------------
# Dummy measurement button
# ---------------------------------------------------------------------------

DUMMY_BUTTON_LABEL = "🎲 Generate dummy measurement"


def test_measurements_panel_offers_dummy_measurement(app):
    """The Measurements expander carries the dummy-measurement button."""
    labels = [b.label for b in app.sidebar.button]
    assert DUMMY_BUTTON_LABEL in labels


def test_measurements_panel_offers_opt_in_sampling(app):
    """The Measurements expander carries the sampling options as an opt-in:
    the checkbox renders off by default (the whole file loads), and turning
    it on reveals the per-axis selection without another click."""
    boxes = {c.label: c.value for c in app.sidebar.checkbox}
    assert "Sample instead of the whole file" in boxes
    assert boxes["Sample instead of the whole file"] is False


def _stub_dummy_measurement() -> DummyMeasurement:
    """A tiny coherent stand-in for the (expensive) real generator."""
    geometry = ProjectionGeometry(
        n_det_cols=8,
        n_det_rows=4,
        projections_per_rotation=3,
        source="dummy-test",
    )
    data = np.zeros((3, 4, 8), dtype=np.float32)
    sinogram = SinogramData(
        data=data,
        geometry=geometry,
        selection=SelectionConfig(),
        original_shape=data.shape,
        source_axis_order=("proj", "row", "col"),
        path=None,
        format="synthetic",
    )
    return DummyMeasurement(
        volume=create_demo_volume(),
        geometry=geometry,
        sinogram=sinogram,
        params={
            "energy_kev": 70.0,
            "spr": 0.3,
            "scatter_sigma_mm": 25.0,
            "i0": 1e5,
            "seed": 42,
            "fp_from_cache": False,
        },
    )


def test_dummy_button_seeds_coherent_demo_pair(app, tmp_path, monkeypatch):
    """Clicking the dummy button seeds volume + geometry + measurement and
    presets the fp selection to "all", so a click on "Run Forward
    Projection" reproduces the measurement's shape exactly. The heavy
    generator is stubbed — its numerics are covered in
    tests/test_dummy_measurement.py."""
    from visualization import volume_cache

    monkeypatch.setattr(volume_cache, "CACHE_FILE", tmp_path / "last_loaded.json")
    monkeypatch.setattr(
        "visualization.phantom.create_dummy_measured_sinogram",
        _stub_dummy_measurement,
    )

    app.sidebar.button(key="dummy_measurement").click()
    app.run()

    assert list(app.exception) == []
    sinogram = app.session_state["sinogram"]
    assert sinogram.data.shape == (3, 4, 8)
    assert sinogram.format == "synthetic"
    geometry = app.session_state["projection_geometry"]
    assert geometry.projections_per_rotation == 3
    assert geometry.source == "dummy-test"
    assert app.session_state["geometry_is_default"] is False
    # The dummy is the full detector and every projection of its geometry:
    # "all" makes the simulated side reproduce it exactly.
    assert app.session_state["sample_proj_mode"] == "all"
    assert app.session_state["sample_row_mode"] == "all"
    assert app.session_state["sample_col_mode"] == "all"


def test_dummy_button_overrides_a_loaded_measurement(app, tmp_path, monkeypatch):
    """The dummy is a self-contained demo pair: it replaces whatever volume,
    geometry and measurement were in session state before."""
    from visualization import volume_cache

    monkeypatch.setattr(volume_cache, "CACHE_FILE", tmp_path / "last_loaded.json")
    _seed_measurements(app, shape=(5, 9, 11))
    monkeypatch.setattr(
        "visualization.phantom.create_dummy_measured_sinogram",
        _stub_dummy_measurement,
    )

    app.sidebar.button(key="dummy_measurement").click()
    app.run()

    assert list(app.exception) == []
    assert app.session_state["sinogram"].data.shape == (3, 4, 8)
