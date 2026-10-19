"""MPR (Multi-Planar Reconstruction) for CT volumes."""

from typing import Tuple

import numpy as np

from visualization.volume import Volume

AXIS = {"axial": 0, "coronal": 1, "sagittal": 2}


def extract_slice(
    volume: Volume, plane: str, index: int
) -> Tuple[np.ndarray, Tuple[float, float]]:
    """Extract an orthogonal slice from a 3D volume.

    Args:
        volume: 3D Volume object containing CT data.
        plane: Plane orientation — "axial", "coronal", or "sagittal".
        index: Slice index along the selected plane.

    Returns:
        A tuple of (slice_array, in_plane_spacing):
        - slice_array: 2D numpy array representing the slice.
        - in_plane_spacing: Tuple of (row_spacing, col_spacing) in mm
          for correct aspect ratio in the UI.

    Raises:
        ValueError: If plane is not valid or volume is not 3D.
        IndexError: If index is out of bounds.
    """
    # Validate volume is 3D
    if volume.array.ndim != 3:
        raise ValueError(f"Volume must be 3D for MPR, got {volume.array.ndim}D")

    # Normalize plane name
    plane = plane.lower().strip()

    if plane not in AXIS:
        raise ValueError(
            f"plane must be 'axial', 'coronal', or 'sagittal', got '{plane}'"
        )

    # Validate index against the source axis in the volume (before slicing)
    axis = AXIS[plane]
    size = volume.array.shape[axis]
    if not 0 <= index < size:
        raise IndexError(f"index {index} out of bounds for {plane} axis (size {size})")

    # Extract slice and determine in-plane spacing based on plane orientation
    if plane == "axial":
        # Axial: slice along z-axis (head-to-feet)
        # Output shape: (rows, cols) = (y, x)
        # Spacing: (y_spacing, x_spacing)
        slice_array = volume.array[index, :, :]
        in_plane_spacing = (volume.spacing[1], volume.spacing[2])

    elif plane == "coronal":
        # Coronal: slice along y-axis (front-to-back)
        # Output shape: (rows, cols) = (z, x)
        # Spacing: (z_spacing, x_spacing)
        slice_array = volume.array[:, index, :]
        in_plane_spacing = (volume.spacing[0], volume.spacing[2])

    elif plane == "sagittal":
        # Sagittal: slice along x-axis (left-to-right)
        # Output shape: (rows, cols) = (z, y)
        # Spacing: (z_spacing, y_spacing)
        slice_array = volume.array[:, :, index]
        in_plane_spacing = (volume.spacing[0], volume.spacing[1])

    return slice_array, in_plane_spacing
