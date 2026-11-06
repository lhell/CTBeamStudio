"""Tests for the display-unit helpers (HU vs attenuation)."""

import numpy as np
import pytest

from backend.attenuation import hu_to_mu, water_mu
from visualization.display_units import (
    DISPLAY_UNIT_HU,
    DISPLAY_UNIT_MU,
    to_display_units,
    unit_label,
    window_in_display_units,
    window_limits,
)


def test_hu_display_keeps_values_unchanged():
    """HU mode is a pass-through."""
    array = np.array([[-1000, 0, 500]], dtype=np.int16)
    result = to_display_units(array, DISPLAY_UNIT_HU, 70.0)
    np.testing.assert_array_equal(result, array)


def test_attenuation_display_converts_hu():
    """Attenuation mode uses the shared HU->mu conversion."""
    array = np.array([[-1000, 0, 500]], dtype=np.int16)
    result = to_display_units(array, DISPLAY_UNIT_MU, 70.0)
    np.testing.assert_allclose(result, hu_to_mu(array, 70.0))


def test_display_units_rejects_unknown_unit():
    """Unknown display units fail loudly."""
    with pytest.raises(ValueError, match="display unit"):
        to_display_units(np.zeros((2, 2)), "keV", 70.0)


def test_window_preset_hu_is_unchanged():
    """HU mode returns the preset values verbatim."""
    assert window_in_display_units("abdomen", DISPLAY_UNIT_HU, 70.0) == (40, 400)


def test_window_preset_attenuation_is_scaled():
    """The abdomen preset is converted through water at the energy."""
    water = water_mu(70.0)
    center, width = window_in_display_units("abdomen", DISPLAY_UNIT_MU, 70.0)
    assert center == pytest.approx(water * 1.04)
    assert width == pytest.approx(water * 0.4)


def test_hu_window_limits_match_existing_sliders():
    """HU limits preserve the previous slider ranges."""
    limits = window_limits(DISPLAY_UNIT_HU, 70.0)
    assert limits["center_min"] == -1000
    assert limits["center_max"] == 3000
    assert limits["width_min"] == 1
    assert limits["width_max"] == 4000
    assert limits["step"] == 1


def test_attenuation_window_limits_are_physical():
    """Attenuation limits start at zero and scale with water."""
    water = water_mu(70.0)
    limits = window_limits(DISPLAY_UNIT_MU, 70.0)
    assert limits["center_min"] == 0.0
    assert limits["center_max"] == pytest.approx(3.0 * water)
    assert limits["width_min"] == pytest.approx(water / 1000.0)
    assert limits["width_min"] > 0
    assert limits["width_max"] == pytest.approx(4.0 * water)
    assert limits["step"] == pytest.approx(water / 1000.0)


def test_unit_label_matches_display_mode():
    """Slider labels use the short physical unit."""
    assert unit_label(DISPLAY_UNIT_HU) == "HU"
    assert unit_label(DISPLAY_UNIT_MU) == "1/cm"
