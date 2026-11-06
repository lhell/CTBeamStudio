"""Shepp-Logan phantom generators for testing.

The 2D phantom is the classic ellipse-based Shepp-Logan slice. The 3D phantom
is built from true ellipsoids (not by stacking the 2D slice), so coronal and
sagittal reconstructions show a realistic head profile.
"""

import numpy as np

from backend.volume import Volume

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
