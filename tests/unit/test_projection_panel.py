"""Tests for the projection panel helpers (no Streamlit / parallelproj needed)."""

import numpy as np
import pytest

from backend.geometry import ProjectionGeometry
from backend.loaders.sinogram import SelectionConfig
from visualization.projection_panel import (
    COMPARISON_VIEW_MAX_HEIGHT_PX,
    EDITABLE_GEOMETRY_FIELDS,
    PLACEHOLDER_HEIGHT_PX,
    apply_axis_order_change,
    apply_geometry_updates,
    build_selection_config,
    build_zoomable_image_html,
    cached_comparison_scales,
    clamp_index_state,
    comparison_view_height,
    difference_image,
    difference_scale,
    index_slider,
    png_data_uri,
    prepare_projection_volume,
    projection_display_image,
    projection_display_spacing,
    resolve_selection,
    resolve_view_index,
    row_sinogram,
    stack_window,
    window_image,
)


def test_projection_display_spacing_returns_detector_row_col_mm():
    """The display resampling gets the detector (row, col) spacing in mm:
    the raw projection pixels are anisotropic in mm, so the row axis is
    stretched by row/col spacing before display."""
    geometry = ProjectionGeometry(
        n_det_cols=512,
        n_det_rows=192,
        det_col_spacing_mm=1.0,
        det_row_spacing_mm=2.0,
    )
    assert projection_display_spacing(geometry) == (2.0, 1.0)


def test_projection_display_spacing_without_geometry_is_none():
    assert projection_display_spacing(None) is None


def test_stack_window_spans_every_stack():
    """One window for measured and simulated together: the measured stack
    alone would never reach the simulated values, and a per-frame normalize
    is exactly what this replaces."""
    measured = np.full((2, 3, 4), 10.0, dtype=np.float32)
    measured[1, 2, 3] = 20.0
    simulated = np.zeros((2, 3, 4), dtype=np.float32)

    assert stack_window(measured, simulated) == (0.0, 20.0)


def test_stack_window_without_data_falls_back_to_unit_range():
    assert stack_window(None, np.empty((0, 0))) == (0.0, 1.0)
    assert stack_window(np.full((2, 2), 5.0)) == (0.0, 1.0)


def test_window_image_maps_and_clips_through_the_shared_window():
    """A frame is mapped with the common window, not rescaled to itself: its
    own max (15) is mid-gray and anything past the window clips."""
    frame = np.array([[10.0, 15.0], [20.0, 25.0]], dtype=np.float32)

    out = window_image(frame, (10.0, 20.0))

    assert out.dtype == np.float32
    np.testing.assert_allclose(out, [[0.0, 0.5], [1.0, 1.0]])


def test_window_image_with_zero_span_is_black():
    out = window_image(np.full((3, 3), 42.0, dtype=np.float32), (5.0, 5.0))

    np.testing.assert_allclose(out, np.zeros((3, 3), dtype=np.float32))


def test_projection_display_image_keeps_a_value_at_one_gray_level():
    """The same detector value gets the same gray in every slice — that is
    what "common level/window" means for the two rows."""
    window = (0.0, 10.0)
    first = projection_display_image(np.full((2, 2), 2.5), window)
    second = projection_display_image(np.full((2, 2), 2.5), window)

    np.testing.assert_allclose(first, second)
    np.testing.assert_allclose(first, np.full((2, 2), 0.25, dtype=np.float32))


def test_difference_scale_takes_the_largest_error_of_all_slices():
    """A small error in one slice must stay dim: the scale comes from the
    whole stack, not from the slice currently on screen."""
    measured = np.array([[[1.0]], [[4.0]]], dtype=np.float32)
    simulated = np.zeros((2, 1, 1), dtype=np.float32)

    assert difference_scale(measured, simulated) == 4.0

    small = difference_image(measured[0] - simulated[0], 4.0)
    large = difference_image(measured[1] - simulated[1], 4.0)
    assert small[0, 0] < large[0, 0]


def test_difference_scale_needs_matching_shapes():
    assert difference_scale(np.zeros((2, 1, 1)), np.zeros((3, 1, 1))) == 0.0
    assert difference_scale(None, np.zeros((2, 1, 1))) == 0.0


def test_difference_image_maps_zero_to_mid_gray():
    diff = np.array([[-2.0, 0.0], [2.0, 1.0]], dtype=np.float32)

    out = difference_image(diff, 2.0)

    assert out.dtype == np.float32
    assert out.min() == pytest.approx(0.0)
    assert out.max() == pytest.approx(1.0)
    assert out[0, 1] == pytest.approx(0.5)


def test_difference_image_without_error_is_even_mid_gray():
    out = difference_image(np.zeros((3, 3), dtype=np.float32), 0.0)

    np.testing.assert_allclose(out, np.full((3, 3), 0.5, dtype=np.float32))


def test_cached_comparison_scales_recomputes_only_for_a_new_stack():
    import streamlit as st

    st.session_state.pop("_sino_display_scales", None)
    first = np.full((2, 3, 4), 10.0, dtype=np.float32)
    assert cached_comparison_scales(first, None) == ((0.0, 1.0), 0.0)
    assert cached_comparison_scales(first, None) == ((0.0, 1.0), 0.0)

    # Same shape, different content: the stamp changes and the window follows.
    second = np.full((2, 3, 4), 25.0, dtype=np.float32)
    assert cached_comparison_scales(second, None)[0] == (0.0, 1.0)
    second[0, 0, 0] = 5.0
    assert cached_comparison_scales(second, None)[0] == (5.0, 25.0)


def test_row_sinogram_fixes_row_and_swaps_axes():
    """Canonical (proj, row, col) → (col, proj) for one detector row:
    columns go vertical, projections horizontal, and only the chosen row is
    kept. A unique value per voxel makes a wrong axis or row visible."""
    data = np.arange(3 * 4 * 5, dtype=np.float32).reshape(3, 4, 5)

    out = row_sinogram(data, 2)

    assert out.shape == (5, 3)
    np.testing.assert_array_equal(out, data[:, 2, :].T)
    # Sanity: neighbouring rows really are different slices.
    assert not np.array_equal(out, row_sinogram(data, 3))


def test_row_sinogram_keeps_first_and_last_row():
    data = np.arange(2 * 3 * 4, dtype=np.float32).reshape(2, 3, 4)

    np.testing.assert_array_equal(row_sinogram(data, 0), data[:, 0, :].T)
    np.testing.assert_array_equal(row_sinogram(data, 2), data[:, 2, :].T)


def test_comparison_view_height_caps_at_the_largest_projection_side():
    """Both rows use one box height, taken from the largest side of a
    projection frame: a 192 x 512 frame caps the boxes at 512 px."""
    assert comparison_view_height(np.zeros((192, 512), dtype=np.float32)) == 512


def test_comparison_view_height_takes_the_tallest_available_frame():
    assert (
        comparison_view_height(
            np.zeros((64, 256), dtype=np.float32),
            np.zeros((192, 512), dtype=np.float32),
        )
        == 512
    )


def test_comparison_view_height_without_data_uses_the_placeholder():
    assert comparison_view_height(None, np.empty((0, 0))) == PLACEHOLDER_HEIGHT_PX


def test_comparison_view_height_is_clamped_to_the_view_maximum():
    """A wide detector (or a small test frame) must not turn one row into a
    page of its own, and must still reserve a visible box."""
    assert comparison_view_height(np.zeros((64, 4000))) == COMPARISON_VIEW_MAX_HEIGHT_PX
    assert comparison_view_height(np.zeros((4, 5))) == PLACEHOLDER_HEIGHT_PX


def test_png_data_uri_encodes_a_grayscale_png():
    import base64
    from io import BytesIO

    from PIL import Image

    uri = png_data_uri(np.array([[0.0, 0.5], [1.0, 0.25]], dtype=np.float32))

    assert uri.startswith("data:image/png;base64,")
    png = Image.open(BytesIO(base64.b64decode(uri.split(",", 1)[1])))
    assert png.mode == "L"
    assert png.size == (2, 2)
    assert png.getpixel((0, 0)) == 0
    assert png.getpixel((0, 1)) == 255


def test_png_data_uri_downscales_the_long_side():
    import base64
    from io import BytesIO

    from PIL import Image

    uri = png_data_uri(np.zeros((10, 100), dtype=np.float32), max_side=20)

    png = Image.open(BytesIO(base64.b64decode(uri.split(",", 1)[1])))
    assert png.size == (20, 2)


def test_zoomable_html_embeds_the_image_and_the_wheel_zoom():
    uri = "data:image/png;base64,AAAA"

    html = build_zoomable_image_html(uri)

    assert f'src="{uri}"' in html
    assert '"wheel"' in html
    assert "ctrlKey" in html
    assert "dblclick" in html
    assert "<script>" in html
    # The box gets its own dark scrollbar: the iframe does not inherit the
    # app's dark theme, so the default light track stood out.
    assert "::-webkit-scrollbar" in html
    assert "scrollbar-color" in html


def test_build_selection_config_maps_all_axes():
    cfg = build_selection_config(
        proj_mode="downsample",
        proj_downsample=5,
        row_mode="central",
        row_range=(2, 8),
        col_mode="all",
    )

    assert isinstance(cfg, SelectionConfig)
    assert cfg.proj_mode == "downsample"
    assert cfg.proj_downsample == 5
    assert cfg.row_mode == "central"
    assert cfg.row_range == (2, 8)
    assert cfg.col_mode == "all"


def test_resolve_selection_returns_index_lists():
    cfg = build_selection_config(
        proj_mode="range",
        proj_range=(0, 3),
        row_mode="all",
        col_mode="downsample",
        col_downsample=2,
    )

    proj_idx, row_idx, col_idx = resolve_selection(cfg, shape=(10, 4, 6))

    assert proj_idx == [0, 1, 2]
    assert row_idx == [0, 1, 2, 3]
    assert col_idx == [0, 2, 4]


def test_editable_geometry_fields_cover_core_parameters():
    names = {field.name for field in EDITABLE_GEOMETRY_FIELDS}
    for required in (
        "sdd",
        "sid",
        "n_det_cols",
        "n_det_rows",
        "det_col_spacing_mm",
        "det_row_spacing_mm",
        "projections_per_rotation",
    ):
        assert required in names


def test_apply_geometry_updates_returns_new_valid_geometry():
    geometry = ProjectionGeometry()

    updated = apply_geometry_updates(geometry, {"sid": 600.0, "sdd": 1200.0})

    assert updated is not geometry
    assert updated.sid == 600.0
    assert updated.sdd == 1200.0
    # Original untouched.
    assert geometry.sid == 500.0


def test_apply_geometry_updates_rejects_invalid_geometry():
    geometry = ProjectionGeometry()

    with pytest.raises(ValueError):
        apply_geometry_updates(geometry, {"sid": 2000.0, "sdd": 1000.0})


def test_clamp_index_state_above_max():
    import streamlit as st

    st.session_state["panel_index"] = 50
    clamp_index_state("panel_index", 10)
    assert st.session_state["panel_index"] == 10


def test_clamp_index_state_below_zero():
    import streamlit as st

    st.session_state["panel_index"] = -3
    clamp_index_state("panel_index", 10)
    assert st.session_state["panel_index"] == 0


def test_clamp_index_state_missing_defaults_to_zero():
    import streamlit as st

    st.session_state.pop("panel_index", None)
    clamp_index_state("panel_index", 10)
    assert st.session_state["panel_index"] == 0


def test_resolve_view_index_clamps_within_range():
    import streamlit as st

    st.session_state["view_index"] = 99
    assert resolve_view_index("view_index", 5) == 4
    assert st.session_state["view_index"] == 4


def test_resolve_view_index_single_item_returns_zero():
    import streamlit as st

    st.session_state.pop("view_index_single", None)
    assert resolve_view_index("view_index_single", 1) == 0
    assert st.session_state["view_index_single"] == 0


def test_resolve_view_index_non_positive_returns_zero():
    import streamlit as st

    st.session_state.pop("view_index_empty", None)
    assert resolve_view_index("view_index_empty", 0) == 0
    assert "view_index_empty" not in st.session_state


def test_index_slider_single_item_renders_nothing():
    import streamlit as st

    assert index_slider(st, "Projection index", "idx_single", 1) == 0


def test_index_slider_non_positive_renders_nothing():
    import streamlit as st

    assert index_slider(st, "Projection index", "idx_zero", 0) == 0


def test_prepare_projection_volume_converts_hu_to_per_mm():
    """The comparison tab must feed attenuation, not HU, to parallelproj."""
    import numpy as np

    from backend.attenuation import water_mu
    from backend.volume import Volume

    volume = Volume(
        array=np.array([[[-1000, 0, 1000]]], dtype=np.int16),
        spacing=(1.0, 0.5, 0.5),
        origin=(0.0, 0.0, 0.0),
        meta={"unit": "HU"},
    )

    prepared = prepare_projection_volume(volume, 70.0)

    assert prepared.meta["unit"] == "1/mm"
    assert prepared.array.dtype == np.float32
    assert prepared.spacing == volume.spacing
    assert prepared.array[0, 0, 1] == pytest.approx(water_mu(70.0) / 10.0, rel=1e-6)


def test_prepare_projection_volume_handles_already_attenuated_volume():
    """Real data loaded directly in 1/mm is projected as-is, not rejected."""
    import numpy as np

    from backend.volume import Volume

    volume = Volume(
        array=np.full((1, 1, 1), 0.02, dtype=np.float32),
        spacing=(1.0, 1.0, 1.0),
        origin=(0.0, 0.0, 0.0),
        meta={"unit": "1/mm"},
    )

    prepared = prepare_projection_volume(volume, 70.0)

    assert prepared is volume
    np.testing.assert_allclose(prepared.array, 0.02)


def _sinogram(data=None, axis_order=("proj", "row", "col")):
    from backend.loaders.sinogram import SinogramData

    return SinogramData(
        data=data,
        geometry=None,
        selection=SelectionConfig(),
        original_shape=(3, 4, 5),
        source_axis_order=axis_order,
    )


def test_apply_axis_order_change_reorients_loaded_sinogram():
    sinogram = _sinogram(np.zeros((3, 4, 5), dtype=np.float32))

    changed = apply_axis_order_change(sinogram, ("proj", "col", "row"))

    assert changed is True
    assert sinogram.axis_order == ("proj", "col", "row")
    assert sinogram.data.shape == (3, 5, 4)


def test_apply_axis_order_change_is_a_noop_for_the_current_order():
    """Re-rendering on every rerun must not thrash the data or the disk."""
    sinogram = _sinogram(np.zeros((3, 4, 5), dtype=np.float32))
    before = sinogram.data

    changed = apply_axis_order_change(sinogram, ("proj", "row", "col"))

    assert changed is False
    assert sinogram.data is before


def test_apply_axis_order_change_without_sinogram_is_a_noop():
    assert apply_axis_order_change(None, ("proj", "col", "row")) is False
