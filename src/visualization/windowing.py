"""Windowing functions for HU to 8-bit grayscale conversion."""

from typing import Union

import numpy as np


# Window presets: (center, width)
WINDOW_PRESETS: dict[str, tuple[float, float]] = {
    "lung": (-600, 1500),
    "abdomen": (40, 400),
    "bone": (400, 1800),
    "brain": (40, 80),
}


def apply_window(array: np.ndarray, center: float, width: float) -> np.ndarray:
    """Apply windowing to convert HU values to 8-bit grayscale.

    Args:
        array: Input array in HU (int16 or float32).
        center: Window center (level) in HU.
        width: Window width in HU.

    Returns:
        uint8 array with values in [0, 255].

    Raises:
        ValueError: If width <= 0.
    """
    if width <= 0:
        raise ValueError("width must be positive")

    # Convert to float for calculation (avoid overflow with int16)
    array_float = array.astype(np.float64)

    # Calculate window boundaries
    window_min = center - width / 2
    window_max = center + width / 2

    # Apply windowing: map [window_min, window_max] to [0, 255]
    result = (array_float - window_min) / (window_max - window_min) * 255

    # Clip to [0, 255], round, and convert to uint8
    result = np.clip(np.round(result), 0, 255).astype(np.uint8)

    return result


def apply_window_with_preset(
    array: np.ndarray,
    window: Union[str, tuple[float, float]]
) -> np.ndarray:
    """Apply windowing with preset name or (center, width) tuple.

    Args:
        array: Input array in HU.
        window: Preset name (e.g., "lung") or (center, width) tuple.

    Returns:
        uint8 array with values in [0, 255].

    Raises:
        KeyError: If preset name not found.
        ValueError: If width <= 0.
    """
    if isinstance(window, str):
        center, width = WINDOW_PRESETS[window]
    else:
        center, width = window

    return apply_window(array, center, width)
