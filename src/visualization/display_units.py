"""Helpers for switching the MPR display between HU and attenuation."""

from __future__ import annotations

import numpy as np

from backend.attenuation import hu_to_mu, hu_window_to_mu, water_mu
from visualization.windowing import WINDOW_PRESETS

DISPLAY_UNIT_HU = "HU"
DISPLAY_UNIT_MU = "Attenuation (1/cm)"
DISPLAY_UNITS = (DISPLAY_UNIT_HU, DISPLAY_UNIT_MU)

_UNIT_LABELS = {
    DISPLAY_UNIT_HU: "HU",
    DISPLAY_UNIT_MU: "1/cm",
}

# Existing HU slider ranges from app.py.
_HU_CENTER_MIN = -1000.0
_HU_CENTER_MAX = 3000.0
_HU_WIDTH_MIN = 1.0
_HU_WIDTH_MAX = 4000.0


def _validate_display_unit(display_unit: str) -> None:
    if display_unit not in DISPLAY_UNITS:
        raise ValueError(
            f"unknown display unit {display_unit!r}; expected one of "
            f"{DISPLAY_UNITS}"
        )


def unit_label(display_unit: str) -> str:
    """Return the short unit shown next to window sliders."""
    _validate_display_unit(display_unit)
    return _UNIT_LABELS[display_unit]


def to_display_units(
    array: np.ndarray, display_unit: str, energy_kev: float = 70.0
) -> np.ndarray:
    """Convert an HU slice to the selected display unit."""
    _validate_display_unit(display_unit)
    if display_unit == DISPLAY_UNIT_HU:
        return array
    return hu_to_mu(array, energy_kev)


def window_in_display_units(
    preset: str, display_unit: str, energy_kev: float = 70.0
) -> tuple[float, float]:
    """Return a window preset (center, width) in the selected display unit."""
    _validate_display_unit(display_unit)
    center_hu, width_hu = WINDOW_PRESETS[preset]
    if display_unit == DISPLAY_UNIT_HU:
        return center_hu, width_hu
    return hu_window_to_mu(center_hu, width_hu, energy_kev)


def window_limits(display_unit: str, energy_kev: float = 70.0) -> dict[str, float]:
    """Return slider bounds and step for the selected display unit."""
    _validate_display_unit(display_unit)
    if display_unit == DISPLAY_UNIT_HU:
        return {
            "center_min": _HU_CENTER_MIN,
            "center_max": _HU_CENTER_MAX,
            "width_min": _HU_WIDTH_MIN,
            "width_max": _HU_WIDTH_MAX,
            "step": 1.0,
        }

    water = water_mu(energy_kev)
    hu_scale = water / 1000.0
    return {
        "center_min": 0.0,
        "center_max": water * (_HU_CENTER_MAX / 1000.0),
        "width_min": hu_scale * _HU_WIDTH_MIN,
        "width_max": water * (_HU_WIDTH_MAX / 1000.0),
        "step": hu_scale,
    }
