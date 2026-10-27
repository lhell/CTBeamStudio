"""Shepp-Logan phantom generator for testing."""

from typing import Optional

import numpy as np

from visualization.volume import Volume


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


def create_shepp_logan_3d(size: int = 256, num_slices: int = 256) -> np.ndarray:
    """
    Create a 3D Shepp-Logan head phantom.

    Parameters
    ----------
    size : int
        Size of each slice (size x size)
    num_slices : int
        Number of slices

    Returns
    -------
    np.ndarray
        3D phantom array (num_slices, size, size)
    """
    phantom_2d = create_shepp_logan_phantom(size)

    # Create 3D phantom by repeating 2D slices
    phantom_3d = np.stack([phantom_2d] * num_slices, axis=0)

    return phantom_3d


def create_shepp_logan_hu(
    size: int = 256,
    num_slices: int = 128,
    spacing: tuple[float, float, float] = (3.0, 0.7, 0.7),
) -> Volume:
    """
    Create a 3D Shepp-Logan phantom scaled to Hounsfield Units.

    HU mapping:
    - Background (0): -1000 HU (air)
    - Outer ellipse (0.8): 0 HU (water/soft tissue)
    - Inner ellipses (0.2-0.3): varying soft tissue
    - Bright ellipses (1.0): +800 HU (bone-like)

    Parameters
    ----------
    size : int
        Size of each slice (size x size)
    num_slices : int
        Number of slices
    spacing : tuple
        (z_spacing, row_spacing, col_spacing) in mm
        Default is anisotropic: (3.0, 0.7, 0.7)

    Returns
    -------
    Volume
        Volume with HU values and spacing metadata
    """
    # Create 2D Shepp-Logan
    phantom_2d = create_shepp_logan_phantom(size)

    # Scale to HU: min → -1000 (air), max → +800 (bone)
    # Shepp-Logan ranges from ~-0.2 to 1.0
    # Mapping: HU = (value - min) / (max - min) * 1800 - 1000
    hu_2d = (phantom_2d + 0.2) / 1.2 * 1800 - 1000

    # Create 3D by stacking slices
    hu_3d = np.stack([hu_2d] * num_slices, axis=0)

    # Convert to int16 (typical for CT)
    hu_3d = hu_3d.astype(np.int16)

    return Volume(
        array=hu_3d,
        spacing=spacing,
        origin=(0.0, 0.0, 0.0),
        meta={"unit": "HU", "phantom": "shepp-logan"},
    )


def create_demo_volume(
    size: int = 256,
    num_slices: int = 128,
    spacing: tuple[float, float, float] = (3.0, 0.7, 0.7),
) -> Volume:
    """
    Create a demo Volume for testing without real DICOM data.

    This is an alias for create_shepp_logan_hu().

    Parameters
    ----------
    size : int
        Size of each slice (size x size)
    num_slices : int
        Number of slices
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
    print(f"\nDemo Volume:")
    print(f"  Shape: {vol.shape}")
    print(f"  Spacing: {vol.spacing}")
    print(f"  HU range: [{vol.array.min()}, {vol.array.max()}]")
