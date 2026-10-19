"""Tests for MPR (Multi-Planar Reconstruction)."""

import numpy as np
import pytest

from visualization.volume import Volume
from visualization.mpr import extract_slice


class TestExtractSlice:
    """Test MPR slice extraction."""

    @pytest.fixture
    def sample_volume(self):
        """Create a sample 3D volume with anisotropic spacing."""
        # Shape: (10, 7, 7) — 10 slices, 7x7 pixels
        # Spacing: (3.0, 0.7, 0.7) — anisotropic (z=3.0mm, y=x=0.7mm)
        array = np.arange(490).reshape(10, 7, 7).astype(np.int16)
        volume = Volume(array=array, spacing=(3.0, 0.7, 0.7), origin=(0.0, 0.0, 0.0))
        return volume

    def test_axial_slice(self, sample_volume):
        """Extract axial slice at index 5."""
        slice_img, in_plane_spacing = extract_slice(sample_volume, "axial", 5)

        assert slice_img.shape == (7, 7)
        assert in_plane_spacing == (0.7, 0.7)

    def test_coronal_slice(self, sample_volume):
        """Extract coronal slice — should have aspect ratio ~4.29."""
        slice_img, in_plane_spacing = extract_slice(sample_volume, "coronal", 3)

        # Coronal: fix y, vary x and z
        # Shape: (10, 7) — z slices, x pixels
        assert slice_img.shape == (10, 7)
        # In-plane spacing: (z_spacing, x_spacing) = (3.0, 0.7)
        assert in_plane_spacing == (3.0, 0.7)

        # Aspect ratio = 3.0 / 0.7 ≈ 4.2857...
        aspect_ratio = in_plane_spacing[0] / in_plane_spacing[1]
        assert abs(aspect_ratio - 4.2857) < 0.01

    def test_sagittal_slice(self, sample_volume):
        """Extract sagittal slice."""
        slice_img, in_plane_spacing = extract_slice(sample_volume, "sagittal", 3)

        # Sagittal: fix x, vary y and z
        # Shape: (10, 7) — z slices, y pixels
        assert slice_img.shape == (10, 7)
        # In-plane spacing: (z_spacing, y_spacing) = (3.0, 0.7)
        assert in_plane_spacing == (3.0, 0.7)

    def test_invalid_plane_raises(self, sample_volume):
        """Invalid plane name should raise ValueError."""
        with pytest.raises(ValueError, match="plane must be"):
            extract_slice(sample_volume, "diagonal", 0)

    def test_index_out_of_bounds_raises(self, sample_volume):
        """Index out of bounds should raise IndexError."""
        with pytest.raises(IndexError):
            extract_slice(sample_volume, "axial", 100)
        with pytest.raises(IndexError):
            extract_slice(sample_volume, "axial", -1)

    def test_2d_volume_raises(self):
        """2D volume should raise ValueError."""
        array = np.zeros((10, 10), dtype=np.int16)
        volume = Volume(array=array, spacing=(1.0, 1.0), origin=(0.0, 0.0))

        with pytest.raises(ValueError, match="3D"):
            extract_slice(volume, "axial", 0)
