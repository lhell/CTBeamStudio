"""Conversion between Hounsfield Units and linear attenuation coefficients.

The conversion uses the water-equivalent approximation

    mu(E) = mu_water(E) * (1 + HU / 1000)

with ``mu_water(E)`` taken from the NIST X-ray mass attenuation coefficients
for liquid water (density 1 g/cm^3, so mu/rho in cm^2/g equals mu in 1/cm).
The model is monoenergetic; beam hardening is not corrected.
"""

from __future__ import annotations

import numpy as np

from backend.volume import Volume

# NIST X-ray mass attenuation coefficients, water (liquid), mu/rho in cm^2/g.
# With rho = 1 g/cm^3 these values are directly mu in 1/cm.
_WATER_ENERGIES_KEV = np.array([30.0, 40.0, 50.0, 60.0, 80.0, 100.0, 150.0])
_WATER_MU_PER_CM = np.array([0.3756, 0.2683, 0.2269, 0.2059, 0.1837, 0.1707, 0.1505])

ENERGY_MIN_KEV = float(_WATER_ENERGIES_KEV[0])
ENERGY_MAX_KEV = float(_WATER_ENERGIES_KEV[-1])

# Factor that converts 1/cm to the requested unit.
_UNIT_SCALE = {"1/cm": 1.0, "1/mm": 0.1}

# Units that represent linear attenuation coefficients. HU is deliberately
# absent: it is a relative scale, not a quantity that can be line-integrated.
ATTENUATION_UNITS = ("1/mm", "1/cm")


def water_mu(energy_kev: float) -> float:
    """Return the linear attenuation coefficient of water in 1/cm.

    Values are log-log interpolated between the NIST table nodes.
    Energies outside 30-150 keV raise ``ValueError`` instead of being
    extrapolated.
    """
    energy = float(energy_kev)
    if not np.isfinite(energy) or not (ENERGY_MIN_KEV <= energy <= ENERGY_MAX_KEV):
        raise ValueError(
            f"energy_kev must be between {ENERGY_MIN_KEV:g} and "
            f"{ENERGY_MAX_KEV:g} keV, got {energy:g}"
        )

    return float(
        np.exp(
            np.interp(
                np.log(energy),
                np.log(_WATER_ENERGIES_KEV),
                np.log(_WATER_MU_PER_CM),
            )
        )
    )


def hu_to_mu(
    hu: np.ndarray | float, energy_kev: float, unit: str = "1/cm"
) -> np.ndarray:
    """Convert HU values to linear attenuation coefficients.

    Args:
        hu: HU value(s); scalars and arrays are accepted.
        energy_kev: Monoenergetic beam energy in keV (30-150).
        unit: ``"1/cm"`` (default) or ``"1/mm"``.

    Returns:
        float64 array in the requested unit. Values below air (-1000 HU) are
        clipped to zero, since negative attenuation is unphysical.

    Raises:
        ValueError: If the unit is unknown or the energy is outside the table.
    """
    if unit not in _UNIT_SCALE:
        raise ValueError(f"unit must be one of {sorted(_UNIT_SCALE)}, got {unit!r}")

    water = water_mu(energy_kev)
    hu_array = np.asarray(hu, dtype=np.float64)
    mu = water * (1.0 + hu_array / 1000.0)
    return np.clip(mu, 0.0, None) * _UNIT_SCALE[unit]


def mu_to_hu(mu: np.ndarray | float, energy_kev: float) -> np.ndarray:
    """Convert linear attenuation coefficients in 1/cm back to HU."""
    water = water_mu(energy_kev)
    mu_array = np.asarray(mu, dtype=np.float64)
    return (mu_array / water - 1.0) * 1000.0


def hu_window_to_mu(
    center_hu: float, width_hu: float, energy_kev: float
) -> tuple[float, float]:
    """Convert an HU window (center, width) to 1/cm at the given energy."""
    water = water_mu(energy_kev)
    center_mu = water * (1.0 + center_hu / 1000.0)
    width_mu = water * width_hu / 1000.0
    return center_mu, width_mu


def volume_to_mu(volume: Volume, energy_kev: float) -> Volume:
    """Return a copy of ``volume`` with values converted to 1/cm."""
    meta = dict(volume.meta or {})
    meta["unit"] = "1/cm"
    return Volume(
        array=hu_to_mu(volume.array, energy_kev).astype(np.float32),
        spacing=volume.spacing,
        origin=volume.origin,
        meta=meta,
    )


def volume_for_projection(volume: Volume, energy_kev: float) -> Volume:
    """Return ``volume`` in 1/mm, ready to be forward projected.

    parallelproj traces each ray through the voxel grid in millimetres and
    integrates the voxel values along that path, so the volume must carry
    attenuation per millimetre for the result to be a dimensionless line
    integral (-ln(I/I0)). See :mod:`backend.parallelproj.projector`, which
    passes the spacings straight through as voxel sizes.

    Args:
        volume: Volume in HU (``meta["unit"]`` unset or ``"HU"``).
        energy_kev: Monoenergetic beam energy in keV (30-150).

    Returns:
        New float32 ``Volume`` in ``"1/mm"`` with geometry unchanged.

    Raises:
        ValueError: If ``volume`` is already in attenuation units.
    """
    unit = (volume.meta or {}).get("unit")
    if unit not in (None, "HU"):
        raise ValueError(
            f"volume is already in {unit!r}; expected HU — converting again "
            "would apply the water scaling twice"
        )

    meta = dict(volume.meta or {})
    meta["unit"] = "1/mm"
    return Volume(
        array=hu_to_mu(volume.array, energy_kev, unit="1/mm").astype(np.float32),
        spacing=volume.spacing,
        origin=volume.origin,
        meta=meta,
    )
