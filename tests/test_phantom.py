"""Tests for phantom.py"""

import sys
from pathlib import Path

import numpy as np
import pytest

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from visualization.phantom import (
    create_demo_volume,
    create_shepp_logan_3d,
    create_shepp_logan_hu,
    create_shepp_logan_phantom,
)

AIR_HU = -1000
TISSUE_THRESHOLD = -500

# 192 mm FOV in all three directions, 2 mm in-plane, 8 mm slice thickness.
SMALL_GEOMETRY = {"size": 96, "num_slices": 24, "spacing": (8.0, 2.0, 2.0)}


class TestSheppLoganPhantom:
    """Test cases for the 2D Shepp-Logan phantom generator."""

    def test_2d_phantom_shape(self):
        """Test 2D phantom has correct shape."""
        phantom = create_shepp_logan_phantom(256)
        assert phantom.shape == (256, 256)

    def test_2d_phantom_shape_custom_size(self):
        """Test 2D phantom with custom size."""
        phantom = create_shepp_logan_phantom(512)
        assert phantom.shape == (512, 512)

    def test_2d_phantom_values_in_range(self):
        """Test 2D phantom values are within expected range."""
        phantom = create_shepp_logan_phantom(256)
        assert phantom.min() >= -0.25  # Allow some tolerance
        assert phantom.max() <= 1.05

    def test_2d_phantom_is_2d_array(self):
        """Test 2D phantom returns numpy array."""
        phantom = create_shepp_logan_phantom(256)
        assert isinstance(phantom, np.ndarray)
        assert phantom.ndim == 2


class TestSheppLogan3D:
    """Test cases for the true 3D Shepp-Logan phantom."""

    def test_3d_phantom_shape(self):
        """Test 3D phantom has correct shape."""
        phantom = create_shepp_logan_3d(**SMALL_GEOMETRY)
        assert phantom.shape == (24, 96, 96)

    def test_3d_phantom_is_int16_hu(self):
        """Test 3D phantom returns int16 Hounsfield units."""
        phantom = create_shepp_logan_3d(**SMALL_GEOMETRY)
        assert isinstance(phantom, np.ndarray)
        assert phantom.ndim == 3
        assert phantom.dtype == np.int16

    def test_3d_phantom_background_is_air(self):
        """Test voxels outside the head are air (-1000 HU)."""
        phantom = create_shepp_logan_3d(**SMALL_GEOMETRY)
        assert phantom[0, 0, 0] == AIR_HU
        assert phantom[12, 0, 0] == AIR_HU
        assert phantom[-1, -1, -1] == AIR_HU

    def test_3d_phantom_contains_bone(self):
        """Test the skull is represented with bone-like HU values."""
        phantom = create_shepp_logan_3d(**SMALL_GEOMETRY)
        assert phantom.max() >= 900

    def test_3d_phantom_center_voxel_is_brain_tissue(self):
        """Test the centre of the head is soft tissue, not skull."""
        phantom = create_shepp_logan_3d(**SMALL_GEOMETRY)
        center = tuple(size // 2 for size in phantom.shape)
        assert phantom[center] == 40

    def test_3d_phantom_slices_are_not_identical(self):
        """Test slices differ along z (no extruded 2D phantom)."""
        phantom = create_shepp_logan_3d(**SMALL_GEOMETRY)
        center = phantom.shape[0] // 2
        pole = 3  # still inside the head, but near one pole of the z extent
        assert not np.array_equal(phantom[center], phantom[pole])

        center_area = np.count_nonzero(phantom[center] > TISSUE_THRESHOLD)
        pole_area = np.count_nonzero(phantom[pole] > TISSUE_THRESHOLD)
        assert center_area > pole_area * 1.5

    def test_coronal_slice_has_air_above_and_below_head(self):
        """Test a coronal slice has air at the top and bottom rows."""
        phantom = create_shepp_logan_3d(**SMALL_GEOMETRY)
        coronal = phantom[:, :, phantom.shape[2] // 2]
        assert np.all(coronal[0] == AIR_HU)
        assert np.all(coronal[-1] == AIR_HU)
        assert np.any(coronal[coronal.shape[0] // 2] > TISSUE_THRESHOLD)

    def test_sagittal_slice_is_not_a_repeated_stripe(self):
        """Test a sagittal slice shows the head profile, not a constant stripe."""
        phantom = create_shepp_logan_3d(**SMALL_GEOMETRY)
        sagittal = phantom[:, phantom.shape[1] // 2, :]
        row_counts = np.count_nonzero(sagittal > TISSUE_THRESHOLD, axis=1)
        assert row_counts[0] == 0
        assert row_counts[-1] == 0
        assert len(set(row_counts.tolist())) > 3

    def test_hu_volume_metadata(self):
        """Test the Volume wrapper exposes geometry and metadata."""
        volume = create_shepp_logan_hu(**SMALL_GEOMETRY)
        assert volume.shape == (24, 96, 96)
        assert volume.spacing == (8.0, 2.0, 2.0)
        # Centered on the rotation axis: origin = minus half the
        # voxel-centre extent per axis (DICOM order x, y, z).
        assert volume.origin == (-95.0, -95.0, -92.0)
        assert volume.array.dtype == np.int16
        assert volume.meta["unit"] == "HU"
        assert volume.meta["phantom"] == "shepp-logan"

    def test_default_volume_center_sits_on_the_rotation_axis(self):
        """Regression (T-95): the demo phantom's origin must center the
        voxel grid on the world origin — the axis the parallelproj cone
        circles — in every direction."""
        volume = create_shepp_logan_hu()
        nz, ny, nx = volume.shape
        sz, sy, sx = volume.spacing
        center = (
            volume.origin[0] + 0.5 * (nx - 1) * float(sx),
            volume.origin[1] + 0.5 * (ny - 1) * float(sy),
            volume.origin[2] + 0.5 * (nz - 1) * float(sz),
        )
        assert center == pytest.approx((0.0, 0.0, 0.0), abs=1e-6)

    def test_head_dimensions_match_phantom_geometry(self):
        """Test physical head size is anisotropic-spacing correct (in mm).

        Patient frame: x = anterior-posterior, y = left-right, z =
        superior-inferior. The classic phantom vertical (0.92) maps onto the
        superior-inferior axis, the classic horizontal (0.69) onto
        left-right, and the through-plane axis (0.90) onto anterior-posterior.
        """
        volume = create_shepp_logan_hu()
        tissue = volume.array > TISSUE_THRESHOLD
        z_idx, y_idx, x_idx = np.where(tissue)

        x_mm = (x_idx.max() - x_idx.min() + 1) * volume.spacing[2]
        y_mm = (y_idx.max() - y_idx.min() + 1) * volume.spacing[1]
        z_mm = (z_idx.max() - z_idx.min() + 1) * volume.spacing[0]

        assert abs(x_mm - 180) <= 4
        assert abs(y_mm - 138) <= 4
        assert abs(z_mm - 184) <= 4
        # A real head is deeper front-to-back and taller than it is wide.
        assert y_mm < x_mm
        assert y_mm < z_mm

    def test_default_demo_volume(self):
        """Test the demo volume uses the new physical defaults."""
        volume = create_demo_volume()
        assert volume.shape == (64, 256, 256)
        assert volume.spacing == (3.0, 0.75, 0.75)
        assert volume.array.dtype == np.int16


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
