"""Tests for HU <-> linear attenuation conversion."""

import numpy as np
import pytest

from backend.attenuation import (
    hu_to_mu,
    hu_window_to_mu,
    mu_to_hu,
    volume_to_mu,
    water_mu,
)
from backend.volume import Volume


@pytest.mark.parametrize(
    ("energy_kev", "expected_mu_per_cm"),
    [
        (30.0, 0.3756),
        (60.0, 0.2059),
        (100.0, 0.1707),
        (150.0, 0.1505),
    ],
)
def test_water_mu_at_tabulated_energies(energy_kev, expected_mu_per_cm):
    """Tabulated NIST water values are returned at their energies."""
    assert water_mu(energy_kev) == pytest.approx(expected_mu_per_cm, rel=1e-6)


def test_water_mu_interpolates_between_tabulated_energies():
    """70 keV lies between the 60 and 80 keV nodes."""
    assert water_mu(70.0) == pytest.approx(0.1937, rel=0.01)


def test_water_mu_rejects_energy_outside_table():
    """Energies outside 30-150 keV are not silently extrapolated."""
    with pytest.raises(ValueError, match="30"):
        water_mu(20.0)
    with pytest.raises(ValueError, match="150"):
        water_mu(200.0)


def test_hu_to_mu_scales_with_water_at_energy():
    """HU 0 is water, -1000 is air (0), +1000 is twice water."""
    water = water_mu(70.0)
    result = hu_to_mu(np.array([0, -1000, 1000], dtype=np.int16), 70.0)

    assert result.dtype == np.float64
    assert result[0] == pytest.approx(water)
    assert result[1] == pytest.approx(0.0)
    assert result[2] == pytest.approx(2.0 * water)


def test_hu_to_mu_clips_values_below_air():
    """Noise below -1000 HU must not produce negative attenuation."""
    result = hu_to_mu(np.array([-2000.0]), 70.0)
    assert result[0] == 0.0


def test_hu_to_mu_supports_per_mm():
    """1/mm is exactly one tenth of 1/cm."""
    per_cm = hu_to_mu(np.array([0.0]), 70.0)
    per_mm = hu_to_mu(np.array([0.0]), 70.0, unit="1/mm")
    assert per_mm[0] == pytest.approx(per_cm[0] / 10.0)


def test_hu_to_mu_rejects_unknown_unit():
    """Only the documented units are accepted."""
    with pytest.raises(ValueError, match="unit"):
        hu_to_mu(np.array([0.0]), 70.0, unit="HU")


def test_mu_to_hu_is_inverse_of_hu_to_mu():
    """HU -> mu -> HU round-trips."""
    hu = np.array([-800.0, 0.0, 40.0, 1200.0])
    mu = hu_to_mu(hu, 80.0)
    result = mu_to_hu(mu, 80.0)
    assert result == pytest.approx(hu)


def test_hu_window_to_mu_converts_center_and_width():
    """Window center/width follow the affine HU->mu mapping."""
    water = water_mu(70.0)
    center_mu, width_mu = hu_window_to_mu(40.0, 400.0, 70.0)
    assert center_mu == pytest.approx(water * 1.04)
    assert width_mu == pytest.approx(water * 0.4)


def test_volume_to_mu_preserves_geometry_and_marks_unit():
    """Converted volume keeps spacing/origin and becomes float32 in 1/cm."""
    array = np.array([[[-1000, 0, 1000]]], dtype=np.int16)
    volume = Volume(array=array, spacing=(1.0, 0.5, 0.5), origin=(0.0, 1.0, 2.0))

    result = volume_to_mu(volume, 70.0)

    assert result.array.dtype == np.float32
    assert result.spacing == volume.spacing
    assert result.origin == volume.origin
    assert result.meta["unit"] == "1/cm"
    assert result.array[0, 0, 1] == pytest.approx(water_mu(70.0), rel=1e-6)
    assert volume.array.dtype == np.int16
