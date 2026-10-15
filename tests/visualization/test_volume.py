"""Tests for Volume dataclass."""

import numpy as np
import pytest

from src.visualization.volume import Volume


def test_volume_creation():
    """3D volume with int16."""
    array = np.zeros((10, 512, 512), dtype=np.int16)
    spacing = (3.0, 0.7, 0.7)
    origin = (0.0, 0.0, 0.0)
    volume = Volume(array=array, spacing=spacing, origin=origin)
    assert volume.array.shape == (10, 512, 512)


def test_volume_uint16_allowed():
    """uint16 for other modalities (MR, PET before SUV)."""
    array = np.zeros((10, 512, 512), dtype=np.uint16)
    volume = Volume(array=array, spacing=(3.0, 0.7, 0.7), origin=(0, 0, 0))
    assert volume.array.dtype == np.uint16


def test_volume_2d_allowed():
    """2D array for single slices."""
    array = np.zeros((512, 512), dtype=np.int16)
    volume = Volume(array=array, spacing=(0.7, 0.7), origin=(0, 0))
    assert volume.array.shape == (512, 512)


def test_volume_4d_rejected():
    """4D arrays (e.g., 4D-CT) are not supported."""
    array = np.zeros((5, 10, 512, 512), dtype=np.int16)
    with pytest.raises(ValueError, match="must be 2D or 3D"):
        Volume(array=array, spacing=(3.0, 0.7, 0.7), origin=(0, 0, 0))


def test_volume_spacing_nan_rejected():
    """NaN spacing values are invalid."""
    array = np.zeros((10, 512, 512), dtype=np.int16)
    spacing = (3.0, np.nan, 0.7)
    with pytest.raises(ValueError, match=r"spacing\[\d+\] must be finite"):
        Volume(array=array, spacing=spacing, origin=(0, 0, 0))


def test_volume_spacing_inf_rejected():
    """Inf spacing values are invalid."""
    array = np.zeros((10, 512, 512), dtype=np.int16)
    spacing = (3.0, np.inf, 0.7)
    with pytest.raises(ValueError, match=r"spacing\[\d+\] must be finite"):
        Volume(array=array, spacing=spacing, origin=(0, 0, 0))


def test_volume_invalid_spacing_length():
    """Spacing must match array dimensions."""
    array = np.zeros((10, 512, 512), dtype=np.int16)
    spacing = (3.0, 0.7)  # Only 2 values for 3D array
    with pytest.raises(ValueError, match="spacing length .* must match"):
        Volume(array=array, spacing=spacing, origin=(0, 0, 0))


def test_volume_invalid_spacing_value():
    """Zero or negative spacing is invalid."""
    array = np.zeros((10, 512, 512), dtype=np.int16)
    spacing = (3.0, 0.0, 0.7)  # Zero spacing
    with pytest.raises(ValueError, match=r"spacing\[\d+\] must be positive"):
        Volume(array=array, spacing=spacing, origin=(0, 0, 0))


def test_volume_invalid_array_dtype():
    """Only int16, uint16, float32 allowed."""
    array = np.zeros((10, 512, 512), dtype=np.float64)
    with pytest.raises(ValueError, match="array must be int16, uint16, or float32"):
        Volume(array=array, spacing=(3.0, 0.7, 0.7), origin=(0, 0, 0))


def test_volume_negative_allowed():
    """Negative values are allowed (e.g., HU for air = -1000)."""
    array = np.array([[-1000, 0, 1000]], dtype=np.int16)  # HU values
    volume = Volume(array=array, spacing=(0.7, 0.7), origin=(0, 0))
    assert volume.array.min() == -1000
    assert volume.array.max() == 1000
