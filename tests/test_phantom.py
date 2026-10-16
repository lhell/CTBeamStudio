"""Tests for phantom.py"""

import sys
from pathlib import Path

import numpy as np
import pytest

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from visualization.phantom import create_shepp_logan_3d, create_shepp_logan_phantom


class TestSheppLoganPhantom:
    """Test cases for Shepp-Logan phantom generator."""

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

    def test_3d_phantom_shape(self):
        """Test 3D phantom has correct shape."""
        phantom = create_shepp_logan_3d(256, 50)
        assert phantom.shape == (50, 256, 256)

    def test_3d_phantom_values_in_range(self):
        """Test 3D phantom values are within expected range."""
        phantom = create_shepp_logan_3d(256, 10)
        assert phantom.min() >= -0.25
        assert phantom.max() <= 1.05

    def test_3d_phantom_is_3d_array(self):
        """Test 3D phantom returns numpy array."""
        phantom = create_shepp_logan_3d(256, 10)
        assert isinstance(phantom, np.ndarray)
        assert phantom.ndim == 3

    def test_3d_slices_are_equal(self):
        """Test all slices in 3D phantom are identical."""
        phantom = create_shepp_logan_3d(256, 10)
        first_slice = phantom[0]
        for i in range(1, 10):
            np.testing.assert_array_almost_equal(first_slice, phantom[i])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
