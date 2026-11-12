"""Tests for the dummy measured-sinogram generator (visualization.phantom).

Every test runs the real generator on a tiny phantom and geometry (the
forward projection takes milliseconds), except where the standard-size
default volume is pinned. Disk caches are redirected to ``tmp_path`` so
tests never write into the project's ``data/`` directory.
"""

from dataclasses import replace

import numpy as np
import pytest

from backend.attenuation import volume_for_projection
from backend.forward_project import forward_project
from backend.geometry import ProjectionGeometry
from visualization.phantom import (
    create_dummy_geometry,
    create_dummy_measured_sinogram,
    create_shepp_logan_hu,
)

# 32 x 32 x 32 mm cube: the tiny geometry covers it exactly (FOV and cone),
# and the forward projection runs in milliseconds.
TINY_VOLUME_KWARGS = {"size": 32, "num_slices": 16, "spacing": (2.0, 1.0, 1.0)}

TINY_GEOMETRY_KWARGS = {
    "sdd": 1000.0,
    "sid": 500.0,
    "n_det_cols": 64,
    "n_det_rows": 64,
    "det_col_spacing_mm": 1.0,
    "det_row_spacing_mm": 1.0,
    "projections_per_rotation": 8,
    "source": "dummy-test",
}


def _tiny_measurement(**overrides):
    """Run the real generator on the tiny phantom + geometry."""
    kwargs = {
        "volume": create_shepp_logan_hu(**TINY_VOLUME_KWARGS),
        "geometry": ProjectionGeometry(**TINY_GEOMETRY_KWARGS),
        "use_cache": False,
    }
    kwargs.update(overrides)
    return create_dummy_measured_sinogram(**kwargs)


class TestDummyGeometry:
    def test_geometry_covers_the_standard_head(self):
        """The dummy detector must see the whole ~180 mm tall head, not crop
        it to a slab: the default 64-row detector covers only ~32 mm of z at
        the isocenter."""
        geometry = create_dummy_geometry()

        xy_coverage_mm = (
            geometry.n_det_cols
            * geometry.det_col_spacing_mm
            * geometry.sid
            / geometry.sdd
        )
        z_coverage_mm = (
            geometry.n_det_rows
            * geometry.det_row_spacing_mm
            * geometry.sid
            / geometry.sdd
        )
        assert xy_coverage_mm >= 190
        assert z_coverage_mm >= 190

    def test_geometry_is_a_circular_60_view_scan(self):
        geometry = create_dummy_geometry()
        assert geometry.projections_per_rotation == 60
        assert geometry.pitch == 0.0
        assert geometry.geometry_type == "cone_beam"
        assert geometry.source == "dummy (Shepp-Logan head)"

    def test_geometry_angles_stay_reasonable(self):
        geometry = create_dummy_geometry()
        assert geometry.fan_angle < 35.0
        assert geometry.cone_angle < 30.0


class TestDummyMeasurement:
    def test_returns_coherent_trio(self):
        dummy = _tiny_measurement()

        geometry = dummy.geometry
        assert dummy.sinogram.data.shape == (
            geometry.projections_per_rotation,
            geometry.n_det_rows,
            geometry.n_det_cols,
        )
        assert dummy.sinogram.data.dtype == np.float32
        assert np.all(np.isfinite(dummy.sinogram.data))
        assert dummy.sinogram.format == "synthetic"
        assert dummy.sinogram.path is None
        assert dummy.sinogram.geometry is geometry
        assert dummy.sinogram.axis_order == ("proj", "row", "col")
        assert dummy.volume.meta["unit"] == "HU"
        assert dummy.params["energy_kev"] == 70.0

    def test_default_volume_is_standard_physical_size(self, tmp_path):
        """The generator must use the standard-size Shepp-Logan head
        (~138 x 184 x 180 mm in a 192 mm FOV), not a shrunken toy cube, and
        center it on the rotation axis."""
        dummy = create_dummy_measured_sinogram(
            geometry=ProjectionGeometry(**TINY_GEOMETRY_KWARGS),
            use_cache=False,
        )
        assert dummy.volume.shape == (64, 256, 256)
        assert dummy.volume.spacing == (3.0, 0.75, 0.75)
        assert dummy.volume.origin == pytest.approx((-95.625, -95.625, -94.5))
        assert dummy.volume.meta["unit"] == "HU"
        assert dummy.volume.meta["phantom"] == "shepp-logan"

    def test_reproducible_with_same_seed(self):
        first = _tiny_measurement(seed=123)
        second = _tiny_measurement(seed=123)
        assert np.array_equal(first.sinogram.data, second.sinogram.data)

    def test_different_seed_changes_noise(self):
        first = _tiny_measurement(seed=1)
        second = _tiny_measurement(seed=2)
        data = first.sinogram.data
        assert not np.array_equal(data, second.sinogram.data)
        # Same measurement plus independent noise: the mean barely moves.
        assert abs(float(np.mean(data - second.sinogram.data))) < 0.05

    def test_scatter_lowers_measured_line_integrals(self):
        """Scatter adds counts, so the measured line integral is lower than
        the scatter-free one (contrast-loss/cupping direction)."""
        without = _tiny_measurement(spr=0.0, seed=5)
        with_scatter = _tiny_measurement(spr=0.3, seed=5)
        shift = float(np.mean(with_scatter.sinogram.data - without.sinogram.data))
        assert shift < -0.05

    def test_spr_zero_is_pure_poisson_around_the_ideal(self):
        volume = create_shepp_logan_hu(**TINY_VOLUME_KWARGS)
        geometry = ProjectionGeometry(**TINY_GEOMETRY_KWARGS)
        ideal = forward_project(
            volume_for_projection(volume, 70.0), geometry
        ).projections

        measured = _tiny_measurement(spr=0.0, i0=1e5).sinogram.data
        residual = measured - ideal
        # Poisson noise averages out to (numerically) zero mean.
        assert abs(float(np.mean(residual))) < 0.01
        assert float(np.std(residual)) > 0.0

    def test_photon_starvation_floors_at_one_count(self):
        """With a tiny dose, some rays see fewer than one photon; the log
        must floor at ln(i0) instead of returning inf."""
        measured = _tiny_measurement(i0=10.0, seed=7).sinogram.data
        assert np.isclose(float(measured.max()), np.log(10.0))
        assert np.all(np.isfinite(measured))

    def test_axis_order_change_transposes_in_memory(self):
        """The dummy has no file behind it: the T-90 setter branch must
        transpose the canonical array in place, reversibly."""
        dummy = _tiny_measurement()
        original = dummy.sinogram.data.copy()

        dummy.sinogram.axis_order = ("col", "row", "proj")
        assert dummy.sinogram.data.shape == (
            TINY_GEOMETRY_KWARGS["n_det_cols"],
            TINY_GEOMETRY_KWARGS["n_det_rows"],
            TINY_GEOMETRY_KWARGS["projections_per_rotation"],
        )
        dummy.sinogram.axis_order = ("proj", "row", "col")
        assert np.array_equal(dummy.sinogram.data, original)

    def test_invalid_parameters_raise(self):
        with pytest.raises(ValueError):
            _tiny_measurement(spr=-0.1)
        with pytest.raises(ValueError):
            _tiny_measurement(scatter_sigma_mm=-1.0)
        with pytest.raises(ValueError):
            _tiny_measurement(i0=0.0)


class TestDummyMeasurementCache:
    """The ideal forward projection (~10 s on CPU) is cached on disk; scatter
    and noise are applied live."""

    def test_first_call_writes_cache_second_call_reuses_it(self, tmp_path):
        cache_path = tmp_path / "dummy_fp.npz"

        first = create_dummy_measured_sinogram(
            geometry=ProjectionGeometry(**TINY_GEOMETRY_KWARGS),
            cache_path=cache_path,
        )
        assert first.params["fp_from_cache"] is False
        assert cache_path.exists()

        second = create_dummy_measured_sinogram(
            geometry=ProjectionGeometry(**TINY_GEOMETRY_KWARGS),
            cache_path=cache_path,
        )
        assert second.params["fp_from_cache"] is True
        # Same seed + same ideal projection: bit-identical measurement.
        assert np.array_equal(first.sinogram.data, second.sinogram.data)

    def test_cache_is_invalidated_by_energy_change(self, tmp_path):
        cache_path = tmp_path / "dummy_fp.npz"
        create_dummy_measured_sinogram(
            geometry=ProjectionGeometry(**TINY_GEOMETRY_KWARGS),
            cache_path=cache_path,
        )
        changed = create_dummy_measured_sinogram(
            geometry=ProjectionGeometry(**TINY_GEOMETRY_KWARGS),
            energy_kev=80.0,
            cache_path=cache_path,
        )
        assert changed.params["fp_from_cache"] is False

    def test_cache_is_invalidated_by_geometry_change(self, tmp_path):
        cache_path = tmp_path / "dummy_fp.npz"
        create_dummy_measured_sinogram(
            geometry=ProjectionGeometry(**TINY_GEOMETRY_KWARGS),
            cache_path=cache_path,
        )
        changed = create_dummy_measured_sinogram(
            geometry=replace(ProjectionGeometry(**TINY_GEOMETRY_KWARGS), n_det_rows=32),
            cache_path=cache_path,
        )
        assert changed.params["fp_from_cache"] is False

    def test_custom_volume_is_never_cached(self, tmp_path):
        """Only the standard phantom is cacheable: a custom volume must not
        write to (or read from) the cache file."""
        cache_path = tmp_path / "dummy_fp.npz"
        dummy = create_dummy_measured_sinogram(
            volume=create_shepp_logan_hu(**TINY_VOLUME_KWARGS),
            geometry=ProjectionGeometry(**TINY_GEOMETRY_KWARGS),
            cache_path=cache_path,
        )
        assert dummy.params["fp_from_cache"] is False
        assert not cache_path.exists()
