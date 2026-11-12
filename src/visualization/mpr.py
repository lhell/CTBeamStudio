"""MPR (Multi-Planar Reconstruction) for CT volumes."""

from typing import Tuple

import numpy as np

from backend.volume import Volume

AXIS = {"axial": 0, "coronal": 2, "sagittal": 1}


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
    # Patient frame: +x = anterior/posterior, +y = left/right, +z = superior.
    # Display convention (user-set): posterior on top in axial, anterior on
    # the left in coronal, patient left on the left in sagittal — see the
    # per-plane notes below.
    if plane == "axial":
        # Axial: slice at fixed z (longitudinal). LR runs horizontally with
        # patient right on the right edge; posterior on the top row.
        # Output shape: (rows, cols) = (x, y) — posterior (-x) top,
        # patient left (+y) left.
        slice_array = volume.array[index].T[:, ::-1]
        in_plane_spacing = (volume.spacing[2], volume.spacing[1])

    elif plane == "coronal":
        # Coronal: slice at fixed x (anterior-posterior) — the plane that
        # divides front from back; spans y (left-right) and z (superior-
        # inferior). Superior on the top row, patient left on the left edge.
        # Output shape: (rows, cols) = (z, y) — superior (+z) top,
        # patient left (+y) left.
        slice_array = volume.array[::-1, ::-1, index]
        in_plane_spacing = (volume.spacing[0], volume.spacing[1])

    elif plane == "sagittal":
        # Sagittal: slice at fixed y (left-right) — the plane that divides
        # left from right; spans x (anterior-posterior) and z (superior-
        # inferior). Superior on the top row, anterior on the left edge.
        # Output shape: (rows, cols) = (z, x) — superior (+z) top,
        # anterior (+x) left.
        slice_array = volume.array[::-1, index, ::-1]
        in_plane_spacing = (volume.spacing[0], volume.spacing[2])

    return slice_array, in_plane_spacing
