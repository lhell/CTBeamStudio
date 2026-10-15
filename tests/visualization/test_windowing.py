"""Tests for Windowing functions."""

import numpy as np
import pytest

from src.visualization.windowing import (
    WINDOW_PRESETS,
    apply_window,
    apply_window_with_preset,
)


def test_apply_window_basic():
    """Basic windowing: HU to 8-bit."""
    # HU values from -1000 (air) to 1000 (bone)
    array = np.array([[[-1000, 0, 1000]]], dtype=np.int16)

    # Window: center=0, width=2000 -> range [-1000, 1000]
    result = apply_window(array, center=0, width=2000)

    assert result.dtype == np.uint8
    assert result[0, 0, 0] == 0  # -1000 -> 0
    assert result[0, 0, 1] == 128  # 0 -> 128
    assert result[0, 0, 2] == 255  # 1000 -> 255


def test_apply_window_presets():
    """Window presets are defined."""
    assert "lung" in WINDOW_PRESETS
    assert "abdomen" in WINDOW_PRESETS
    assert "bone" in WINDOW_PRESETS
    assert "brain" in WINDOW_PRESETS

    # Lung preset: (-600, 1500)
    assert WINDOW_PRESETS["lung"] == (-600, 1500)


def test_apply_window_with_preset_by_name():
    """Can use preset name string."""
    array = np.array([[-1000, 0, 500]], dtype=np.int16)
    result = apply_window_with_preset(array, "lung")
    assert result.dtype == np.uint8


def test_apply_window_with_preset_by_tuple():
    """Can use (center, width) tuple."""
    array = np.array([[-1000, 0, 500]], dtype=np.int16)
    result = apply_window_with_preset(array, (0, 2000))
    assert result.dtype == np.uint8


def test_apply_window_with_preset_invalid_name():
    """Invalid preset name raises KeyError."""
    array = np.zeros((10, 10), dtype=np.int16)
    with pytest.raises(KeyError):
        apply_window_with_preset(array, "invalid_preset")


def test_apply_window_invalid_width():
    """Zero or negative width raises ValueError."""
    array = np.zeros((10, 10), dtype=np.int16)
    with pytest.raises(ValueError, match="width must be positive"):
        apply_window(array, center=0, width=0)


def test_apply_window_int16_no_overflow():
    """int16 values don't overflow during computation."""
    array = np.array([[-2000]], dtype=np.int16)  # Very low HU
    result = apply_window(array, center=0, width=2000)
    assert result[0, 0] == 0  # Clamped to 0

    array = np.array([[2000]], dtype=np.int16)  # Very high HU
    result = apply_window(array, center=0, width=2000)
    assert result[0, 0] == 255  # Clamped to 255
