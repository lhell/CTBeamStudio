"""Shepp-Logan phantom generators for testing.

The 2D phantom is the classic ellipse-based Shepp-Logan slice. The 3D phantom
is built from true ellipsoids (not by stacking the 2D slice), so coronal and
sagittal reconstructions show a realistic head profile.

The module also synthesizes a dummy *measured* sinogram for the 3D phantom:
forward projection + scatter + Poisson noise (see
create_dummy_measured_sinogram).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import numpy as np

from backend.volume import Volume

if TYPE_CHECKING:
    # Annotations only (strings via ``from __future__ import annotations``);
    # importing these at runtime would pull pydicom into every phantom use.
    from backend.geometry import ProjectionGeometry
    from backend.loaders.sinogram import SinogramData

# 1 phantom unit = 100 mm. This maps the classical Shepp-Logan parameter
# table onto a realistically sized head (~138 x 184 x 180 mm).
PHANTOM_UNIT_MM = 100.0

AIR_HU = -1000

# 3D Shepp-Logan ellipsoids: (x0, y0, z0, a, b, c, theta_deg, hu)
# Geometry follows Kak & Slaney; the classical densities are replaced by
# absolute Hounsfield units. Components are painted outside-in, so inner
# structures overwrite outer ones.
ELLIPSOIDS_3D = (
    (0.0, 0.0, 0.0, 0.69, 0.92, 0.90, 0.0, 1000),  # skull
    (0.0, -0.0184, 0.0, 0.6624, 0.874, 0.88, 0.0, 40),  # brain
    (0.22, 0.0, 0.0, 0.11, 0.31, 0.22, -18.0, 30),  # white matter (right)
    (-0.22, 0.0, 0.0, 0.16, 0.41, 0.21, 18.0, 30),  # white matter (left)
    (0.0, 0.35, -0.15, 0.21, 0.25, 0.35, 0.0, 25),  # large superior structure
    (0.0, 0.1, 0.25, 0.046, 0.046, 0.046, 0.0, 10),  # ventricle (right)
    (0.0, -0.1, 0.25, 0.046, 0.046, 0.046, 0.0, 10),  # ventricle (left)
    (-0.08, -0.605, 0.0, 0.046, 0.023, 0.05, 0.0, 60),  # small lesion
    (0.0, -0.606, 0.0, 0.023, 0.011, 0.05, 0.0, 60),  # small lesion
    (0.06, -0.605, 0.0, 0.023, 0.046, 0.05, 0.0, 60),  # small lesion
)


def create_shepp_logan_phantom(size: int = 256) -> np.ndarray:
    """
    Create a Shepp-Logan head phantom.

    Parameters
    ----------
    size : int
        Size of the phantom (size x size)

    Returns
    -------
    np.ndarray
        2D phantom array with values 0-1
    """
    # Create coordinate grid
    x = np.linspace(-1, 1, size)
    y = np.linspace(-1, 1, size)
    X, Y = np.meshgrid(x, y)

    # Initialize phantom
    phantom = np.zeros((size, size))

    # Shepp-Logan parameters: (x_center, y_center, a, b, theta, intensity)
    # a, b are semi-axes, theta is rotation angle in radians
    ellipses = [
        (0, 0, 0.69, 0.92, 0, 1.0),  # Outer ellipse (skull)
        (0, 0, 0.6624, 0.874, 0, 0.8),  # Inner ellipse
        (-0.22, 0, 0.31, 0.11, 0, -0.2),  # Left ellipse
        (0.22, 0, 0.41, 0.16, 0, -0.2),  # Right ellipse
        (0, 0.35, 0.21, 0.05, 0, 0.3),  # Top ellipse
        (0, -0.1, 0.046, 0.046, 0, 0.3),  # Center ellipse
        (0, -0.1, 0.046, 0.046, np.pi / 2, 0.3),  # Center ellipse rotated
        (-0.08, -0.605, 0.046, 0.023, 0, 0.3),  # Bottom left small
        (0.06, -0.605, 0.023, 0.046, 0, 0.3),  # Bottom right small
        (0, -0.605, 0.023, 0.031, 0, -0.2),  # Bottom center small
    ]

    for xc, yc, a, b, theta, intensity in ellipses:
        # Rotate coordinates
        cos_theta = np.cos(theta)
        sin_theta = np.sin(theta)
        X_rot = (X - xc) * cos_theta + (Y - yc) * sin_theta
        Y_rot = -(X - xc) * sin_theta + (Y - yc) * cos_theta

        # Check if point is inside ellipse
        inside = (X_rot / a) ** 2 + (Y_rot / b) ** 2 <= 1
        phantom[inside] = intensity

    return phantom


def create_shepp_logan_3d(
    size: int = 256,
    num_slices: int = 64,
    spacing: tuple[float, float, float] = (3.0, 0.75, 0.75),
) -> np.ndarray:
    """
    Create a true 3D Shepp-Logan head phantom as ellipsoids.

    Unlike a stacked 2D phantom, the ellipsoids have a finite extent along the
    z-axis, so coronal and sagittal slices show a head profile.

    Parameters
    ----------
    size : int
        Number of rows/columns per slice (size x size)
    num_slices : int
        Number of slices along z
    spacing : tuple
        (z_spacing, row_spacing, col_spacing) in mm. The generated ellipsoids
        are scaled by these spacings so the anatomy keeps its physical
        proportions in every plane.

    Returns
    -------
    np.ndarray
        3D phantom array (num_slices, size, size) in Hounsfield units (int16)
    """
    if size <= 0 or num_slices <= 0:
        raise ValueError("size and num_slices must be positive")
    if len(spacing) != 3 or any(s <= 0 for s in spacing):
        raise ValueError("spacing must contain three positive values")

    phantom = np.full((num_slices, size, size), AIR_HU, dtype=np.int16)

    # In-plane grids in phantom units (1 unit = PHANTOM_UNIT_MM).
    in_plane = (np.arange(size) - (size - 1) / 2.0) / PHANTOM_UNIT_MM
    x = in_plane * spacing[2]
    y = in_plane * spacing[1]
    X, Y = np.meshgrid(x, y)

    # Pre-rotate each ellipsoid once around the z-axis.
    ellipsoids = []
    for x0, y0, z0, a, b, c, theta_deg, hu in ELLIPSOIDS_3D:
        theta = np.deg2rad(theta_deg)
        cos_t = np.cos(theta)
        sin_t = np.sin(theta)
        x_rot = ((X - x0) * cos_t + (Y - y0) * sin_t) / a
        y_rot = (-(X - x0) * sin_t + (Y - y0) * cos_t) / b
        ellipsoids.append((x_rot**2 + y_rot**2, z0, c, hu))

    z_axis = (np.arange(num_slices) - (num_slices - 1) / 2.0) * spacing[0]
    z_axis = z_axis / PHANTOM_UNIT_MM

    for z_index, z in enumerate(z_axis):
        axial_slice = phantom[z_index]
        for radial_sq, z0, c, hu in ellipsoids:
            remaining = 1.0 - ((z - z0) / c) ** 2
            if remaining <= 0.0:
                continue
            axial_slice[radial_sq <= remaining] = hu

    return phantom


def create_shepp_logan_hu(
    size: int = 256,
    num_slices: int = 64,
    spacing: tuple[float, float, float] = (3.0, 0.75, 0.75),
) -> Volume:
    """
    Create a 3D Shepp-Logan phantom scaled to Hounsfield Units.

    HU mapping (painted outside-in):
    - Background: -1000 HU (air)
    - Skull: +1000 HU
    - Brain tissue: 40 HU, white matter 30 HU, superior structure 25 HU
    - Ventricles: 10 HU (CSF-like)
    - Small lesions: 60 HU

    Parameters
    ----------
    size : int
        Number of rows/columns per slice (size x size)
    num_slices : int
        Number of slices along z
    spacing : tuple
        (z_spacing, row_spacing, col_spacing) in mm
        Default is anisotropic: (3.0, 0.75, 0.75), giving a 192 mm FOV that
        fits the ~180 mm tall phantom.

    Returns
    -------
    Volume
        Volume with HU values and spacing metadata
    """
    phantom = create_shepp_logan_3d(size, num_slices, spacing)

    return Volume(
        array=phantom,
        spacing=spacing,
        origin=(0.0, 0.0, 0.0),
        meta={"unit": "HU", "phantom": "shepp-logan"},
    )


def create_demo_volume(
    size: int = 256,
    num_slices: int = 64,
    spacing: tuple[float, float, float] = (3.0, 0.75, 0.75),
) -> Volume:
    """
    Create a demo Volume for testing without real DICOM data.

    This is an alias for create_shepp_logan_hu().

    Parameters
    ----------
    size : int
        Number of rows/columns per slice (size x size)
    num_slices : int
        Number of slices along z
    spacing : tuple
        (z_spacing, row_spacing, col_spacing) in mm

    Returns
    -------
    Volume
        Volume with HU values and spacing metadata
    """
    return create_shepp_logan_hu(size, num_slices, spacing)


# ---------------------------------------------------------------------------
# Dummy measured sinogram: Shepp-Logan forward projection + scatter + noise
# ---------------------------------------------------------------------------

# Disk cache for the ideal (scatter/noise-free) forward projection of the
# standard dummy phantom. The forward projection is the only expensive step
# (~10 s on CPU for the standard-size head), so it is stored in the
# gitignored data/ directory and reused; scatter and noise are applied live,
# so changing spr/i0/seed never triggers a re-projection. Bump
# DUMMY_CACHE_VERSION when the projection path itself changes (v2: the
# phantom is now centered on the rotation axis).
DUMMY_FP_CACHE = Path("data/cache/dummy_fp_standard.npz")
DUMMY_CACHE_VERSION = 2


@dataclass(frozen=True)
class DummyMeasurement:
    """Coherent dummy demo trio: phantom volume, matching geometry, and a
    synthetic 'measured' sinogram, plus the generation parameters.

    Attributes:
        volume: The projected phantom (HU).
        geometry: The geometry the sinogram was projected with.
        sinogram: The simulated measurement as ``SinogramData`` (canonical
            (proj, row, col), format "synthetic", in memory — no file).
        params: Generation parameters (energy_kev, spr, scatter_sigma_mm,
            i0, seed, fp_from_cache).
    """

    volume: Volume
    geometry: ProjectionGeometry
    sinogram: SinogramData
    params: dict


def create_dummy_geometry() -> ProjectionGeometry:
    """Dummy CBCT geometry sized to the standard Shepp-Logan head.

    The default 64-row detector covers only ~32 mm of z at the isocenter
    (64 rows x 1 mm x SID/SDD), which would crop the ~180 mm tall head to
    a slab. This geometry uses 192 rows x 2 mm (collimation 384 mm at the
    detector), covering 192 mm of z at the isocenter — the whole head plus
    margin — while the 512 columns x 1 mm cover the 192 mm wide FOV
    in-plane.

    Returns
    -------
    ProjectionGeometry
        60 views per rotation, circular scan (pitch 0).
    """
    from backend.geometry import ProjectionGeometry

    return ProjectionGeometry(
        sdd=1000.0,
        sid=500.0,
        n_det_cols=512,
        n_det_rows=192,
        det_col_spacing_mm=1.0,
        det_row_spacing_mm=2.0,
        projections_per_rotation=60,
        source="dummy (Shepp-Logan head)",
    )


def _fp_fingerprint(geometry: ProjectionGeometry, energy_kev: float) -> str:
    """Stable hash over everything that changes the ideal projection."""
    payload = {
        "version": DUMMY_CACHE_VERSION,
        "phantom": "shepp-logan-3d-standard",
        "energy_kev": float(energy_kev),
        "geometry": asdict(geometry),
    }
    blob = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _load_cached_fp(
    cache_path: Path, fingerprint: Optional[str]
) -> Optional[np.ndarray]:
    """Return the cached ideal projection, or None on any mismatch."""
    if fingerprint is None or not cache_path.exists():
        return None
    try:
        with np.load(cache_path, allow_pickle=False) as npz:
            if str(npz["fingerprint"]) != fingerprint:
                return None
            return np.asarray(npz["projections"], dtype=np.float32)
    except (OSError, ValueError, KeyError):
        return None


def _save_cached_fp(
    cache_path: Path, projections: np.ndarray, fingerprint: str
) -> None:
    """Write the ideal projection to the cache (best effort)."""
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            cache_path, projections=projections, fingerprint=fingerprint
        )
    except OSError:
        pass  # a read-only data directory must not fail the generation


def _centered_shepp_logan_hu() -> Volume:
    """Standard-size Shepp-Logan head, centered on the rotation axis.

    The parallelproj cone circles the isocenter at the world origin, and the
    demo default origin (0, 0, 0) would park the whole head in the +x/+y/+z
    octant — outside the in-plane FOV and half outside the cone in z. This
    shifts the origin so the volume center sits on the axis; everything else
    (HU values, spacing, size) matches :func:`create_shepp_logan_hu`.
    """
    from dataclasses import replace

    volume = create_shepp_logan_hu()
    nz, ny, nx = volume.shape
    sz, sy, sx = volume.spacing
    origin = (
        -0.5 * (nx - 1) * float(sx),
        -0.5 * (ny - 1) * float(sy),
        -0.5 * (nz - 1) * float(sz),
    )
    return replace(volume, origin=origin, meta={**volume.meta, "origin": "centered"})


def create_dummy_measured_sinogram(
    geometry: Optional[ProjectionGeometry] = None,
    *,
    volume: Optional[Volume] = None,
    energy_kev: float = 70.0,
    spr: float = 0.3,
    scatter_sigma_mm: float = 25.0,
    i0: float = 1e5,
    seed: Optional[int] = 42,
    use_cuda: bool = True,
    use_cache: bool = True,
    cache_path: Optional[Path] = None,
) -> DummyMeasurement:
    """
    Synthesize a dummy 'measured' sinogram for the Shepp-Logan phantom.

    The measurement is simulated in three steps:

    1. Forward projection of the 3D Shepp-Logan phantom (standard physical
       size, ~138 x 184 x 180 mm, centered on the rotation axis so the whole
       head is inside the cone) at ``energy_kev`` -> ideal line integrals.
       This is the only expensive step (~10 s on CPU), so it is cached on
       disk under ``data/cache/`` and reused while phantom, geometry and
       energy are unchanged. Only the standard phantom (``volume=None``) is
       cached; a custom ``volume`` always re-projects.
    2. Scatter: a Gaussian-blurred copy of the primary transmittance, added
       in the intensity domain with scatter-to-primary ratio ``spr``. The
       blur width ``scatter_sigma_mm`` is given at the detector and converted
       per axis, so the blur is isotropic in mm despite anisotropic detector
       spacing. Scatter adds counts, so the measured line integral is LOWER
       than the ideal one (the contrast-loss/cupping direction).
    3. Quantum noise: Poisson-distributed counts with ``i0`` incident photons
       per ray. Rays that would see fewer than one photon floor at one count
       (photon starvation).

    Parameters
    ----------
    geometry : ProjectionGeometry, optional
        None uses :func:`create_dummy_geometry`, sized so the whole standard
        head is inside the cone.
    volume : Volume, optional
        Phantom to project; None uses the standard-size
        :func:`create_shepp_logan_hu` volume.
    energy_kev : float
        Monoenergetic energy for the HU -> 1/mm conversion.
    spr : float
        Scatter-to-primary ratio (0 disables scatter).
    scatter_sigma_mm : float
        Scatter blur width in mm at the detector.
    i0 : float
        Incident photons per ray (dose; sets the noise level).
    seed : int, optional
        RNG seed for reproducibility; None gives fresh noise per call.
    use_cuda : bool
        Whether the forward projection may use CUDA if available.
    use_cache : bool
        Whether the ideal projection may be read from / written to the disk
        cache.
    cache_path : Path, optional
        Cache file override (tests); None uses ``DUMMY_FP_CACHE``.

    Returns
    -------
    DummyMeasurement
        The phantom volume, the geometry used, and the measured sinogram as
        ``SinogramData`` (canonical (proj, row, col), format "synthetic",
        in memory — no file behind it).
    """
    from scipy.ndimage import gaussian_filter

    from backend.attenuation import volume_for_projection
    from backend.forward_project import PARALLELPROJ_AVAILABLE, forward_project
    from backend.loaders.sinogram import CANONICAL, SelectionConfig, SinogramData

    if spr < 0:
        raise ValueError("spr must not be negative")
    if scatter_sigma_mm < 0:
        raise ValueError("scatter_sigma_mm must not be negative")
    if i0 <= 0:
        raise ValueError("i0 must be positive")

    if geometry is None:
        geometry = create_dummy_geometry()

    cache_file = cache_path if cache_path is not None else DUMMY_FP_CACHE
    cacheable = volume is None and use_cache
    if volume is None:
        # Standard physical size: ~138 x 184 x 180 mm head in a 192 mm FOV,
        # centered on the rotation axis so the whole head is inside the cone.
        volume = _centered_shepp_logan_hu()

    fingerprint = _fp_fingerprint(geometry, energy_kev) if cacheable else None
    ideal = _load_cached_fp(cache_file, fingerprint)
    fp_from_cache = ideal is not None
    if ideal is None:
        result = forward_project(
            volume_for_projection(volume, energy_kev),
            geometry,
            use_cuda=use_cuda,
        )
        ideal = np.asarray(result.projections, dtype=np.float32)
        if cacheable and PARALLELPROJ_AVAILABLE:
            _save_cached_fp(cache_file, ideal, fingerprint)

    # Primary transmittance with I0 = 1, then scatter + quantum noise.
    primary = np.exp(-ideal)
    if spr > 0.0 and scatter_sigma_mm > 0.0:
        sigma_px = (
            0.0,  # no blur along the projection axis: scatter is per-frame
            scatter_sigma_mm / float(geometry.det_row_spacing_mm),
            scatter_sigma_mm / float(geometry.det_col_spacing_mm),
        )
        scatter = spr * gaussian_filter(primary, sigma=sigma_px, mode="nearest")
    else:
        scatter = np.zeros_like(primary)

    lam = (primary + scatter).astype(np.float64) * float(i0)
    rng = np.random.default_rng(seed)
    counts = rng.poisson(lam)
    measured = (-np.log(np.maximum(counts, 1) / float(i0))).astype(np.float32)

    sinogram = SinogramData(
        data=measured,
        geometry=geometry,
        selection=SelectionConfig(),
        original_shape=tuple(measured.shape),
        source_axis_order=CANONICAL,
        path=None,
        format="synthetic",
    )
    params = {
        "energy_kev": energy_kev,
        "spr": spr,
        "scatter_sigma_mm": scatter_sigma_mm,
        "i0": i0,
        "seed": seed,
        "fp_from_cache": fp_from_cache,
    }
    return DummyMeasurement(
        volume=volume, geometry=geometry, sinogram=sinogram, params=params
    )


if __name__ == "__main__":
    import matplotlib.pyplot as plt

    # Create phantom
    phantom = create_shepp_logan_phantom(256)

    # Display
    plt.figure(figsize=(6, 6))
    plt.imshow(phantom, cmap="gray")
    plt.title("Shepp-Logan Phantom")
    plt.colorbar(label="Intensity")
    plt.axis("off")
    plt.savefig("shepp_logan_phantom.png", dpi=150, bbox_inches="tight")
    plt.show()

    print(f"Phantom shape: {phantom.shape}")
    print(f"Value range: [{phantom.min():.3f}, {phantom.max():.3f}]")

    # Also show HU version
    vol = create_demo_volume()
    print("\nDemo Volume:")
    print(f"  Shape: {vol.shape}")
    print(f"  Spacing: {vol.spacing}")
    print(f"  HU range: [{vol.array.min()}, {vol.array.max()}]")
