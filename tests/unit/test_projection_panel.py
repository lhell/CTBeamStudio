"""Tests for the projection panel helpers (no Streamlit / parallelproj needed)."""

import numpy as np
import pytest

from backend.geometry import ProjectionGeometry
from backend.loaders.sinogram import SelectionConfig
from visualization.projection_panel import (
    EDITABLE_GEOMETRY_FIELDS,
    apply_geometry_updates,
    build_selection_config,
    clamp_index_state,
    normalize_difference,
    normalize_projection,
    prepare_projection_volume,
    resolve_selection,
)


def test_normalize_projection_scales_to_unit_range():
    arr = np.array([[0.0, 5.0], [10.0, 2.5]], dtype=np.float32)

    out = normalize_projection(arr)

    assert out.dtype == np.float32
    assert out.min() == pytest.approx(0.0)
    assert out.max() == pytest.approx(1.0)
    np.testing.assert_allclose(out, [[0.0, 0.5], [1.0, 0.25]])


def test_normalize_projection_constant_returns_zeros():
    arr = np.full((3, 3), 42.0, dtype=np.float32)

    out = normalize_projection(arr)

    assert out.shape == arr.shape
    assert out.dtype == np.float32
    np.testing.assert_allclose(out, np.zeros_like(arr))


def test_normalize_difference_maps_zero_to_mid_gray():
    diff = np.array([[-2.0, 0.0], [2.0, 1.0]], dtype=np.float32)

    out = normalize_difference(diff)

    assert out.dtype == np.float32
    assert out.min() == pytest.approx(0.0)
    assert out.max() == pytest.approx(1.0)
    assert out[0, 1] == pytest.approx(0.5)


def test_normalize_difference_constant_returns_mid_gray():
    diff = np.zeros((3, 3), dtype=np.float32)

    out = normalize_difference(diff)

    np.testing.assert_allclose(out, np.full((3, 3), 0.5, dtype=np.float32))


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
