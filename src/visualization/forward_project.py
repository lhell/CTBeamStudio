"""Forward projection using parallelproj.

This module provides forward projection functionality to generate synthetic
projections from 3D volumes. It uses parallelproj when available, with a
fallback to a placeholder implementation for testing/development.
"""

import warnings
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

# Try to import parallelproj, fallback to None if not available
try:
    import parallelproj

    PARALLELPROJ_AVAILABLE = True
except ImportError:
    PARALLELPROJ_AVAILABLE = False
    parallelproj = None


from visualization.geometry import ProjectionGeometry
from visualization.volume import Volume


@dataclass
class ForwardProjectionResult:
    """Result of forward projection.

    Attributes:
        projections: 3D array of shape (n_projections, n_rows, n_cols)
        geometry: The projection geometry used
        row_indices: List of detector row indices that were projected
        col_indices: List of detector column indices that were projected
        proj_indices: List of projection indices that were computed
    """

    projections: np.ndarray
    geometry: ProjectionGeometry
    row_indices: List[int]
    col_indices: List[int]
    proj_indices: List[int]


def forward_project(
    volume: Volume,
    geometry: ProjectionGeometry,
    row_indices: Optional[List[int]] = None,
    col_indices: Optional[List[int]] = None,
    proj_indices: Optional[List[int]] = None,
    n_projections: Optional[int] = None,
    use_cuda: bool = True,
) -> ForwardProjectionResult:
    """Forward project a volume using parallelproj (or placeholder).

    Args:
        volume: 3D volume with HU values
        geometry: ProjectionGeometry with scanner parameters
        row_indices: Which detector rows to project (None = all)
        col_indices: Which detector columns to project (None = all)
        proj_indices: Which projections to generate (None = all)
        n_projections: Number of projections. None = use
            geometry.projections_per_rotation
        use_cuda: Whether to use CUDA if available
            (ignored if using placeholder)

    Returns:
        ForwardProjectionResult with synthetic projections

    Note:
        If parallelproj is not available, returns zeros and emits a warning.
        This is useful for development and testing without conda environment.
    """
    # Determine detector dimensions
    n_rows = geometry.n_det_rows
    n_cols = geometry.n_det_cols

    # Default indices
    if row_indices is None:
        row_indices = list(range(n_rows))
    if col_indices is None:
        col_indices = list(range(n_cols))
    if proj_indices is None:
        n_proj = n_projections or geometry.projections_per_rotation
        proj_indices = list(range(n_proj))
    if n_projections is None:
        n_projections = len(proj_indices)

    # Call the appropriate implementation
    if PARALLELPROJ_AVAILABLE and parallelproj is not None:
        return _forward_project_parallelproj(
            volume, geometry, row_indices, col_indices, proj_indices, use_cuda
        )
    else:
        return _forward_project_placeholder(
            volume, geometry, row_indices, col_indices, proj_indices
        )


def _forward_project_placeholder(
    volume: Volume,
    geometry: ProjectionGeometry,
    row_indices: List[int],
    col_indices: List[int],
    proj_indices: List[int],
) -> ForwardProjectionResult:
    """Placeholder implementation that returns zeros.

    This is used when parallelproj is not available.
    """
    n_projs = len(proj_indices)
    n_rows = len(row_indices)
    n_cols = len(col_indices)

    # Return zeros - placeholder for actual projection
    projections = np.zeros((n_projs, n_rows, n_cols), dtype=np.float32)

    return ForwardProjectionResult(
        projections=projections,
        geometry=geometry,
        row_indices=row_indices,
        col_indices=col_indices,
        proj_indices=proj_indices,
    )


def _forward_project_parallelproj(
    volume: Volume,
    geometry: ProjectionGeometry,
    row_indices: List[int],
    col_indices: List[int],
    proj_indices: List[int],
    use_cuda: bool,
) -> ForwardProjectionResult:
    """Actual forward projection using parallelproj.

    Args:
        volume: 3D volume with HU values
        geometry: ProjectionGeometry with scanner parameters
        row_indices: Which detector rows to project
        col_indices: Which detector columns to project
        proj_indices: Which projections to generate
        use_cuda: Whether to use CUDA if available

    Returns:
        ForwardProjectionResult with synthetic projections
    """
    import torch

    n_projs = len(proj_indices)
    n_rows = len(row_indices)
    n_cols = len(col_indices)

    # Get volume parameters
    volume_array = volume.array.astype(np.float32)

    # Convert to torch tensor and move to appropriate device
    cuda_available = torch.cuda.is_available() and use_cuda
    dev = torch.device("cuda" if cuda_available else "cpu")
    _ = torch.from_numpy(volume_array).to(dev)

    # Setup geometry for parallelproj
    # parallelproj expects (x, y, z) ordering, our Volume is (z, y, x)
    _voxel_size = (
        volume.spacing[2],  # x
        volume.spacing[1],  # y
        volume.spacing[0],  # z
    )

    _origin = (
        volume.origin[2],  # x
        volume.origin[1],  # y
        volume.origin[0],  # z
    )

    # Source angles (0° = anterior = +X, Z-axis rotation, positive = CCW)
    _angles = np.linspace(0, 2 * np.pi, len(proj_indices), endpoint=False)
    _angles = np.rad2deg(_angles)

    # Scanner radius (distance from source to isocenter)
    _scanner_radius = geometry.sid

    # Get detector pixel spacing
    _col_spacing = geometry.det_col_spacing_mm
    _row_spacing = geometry.det_row_spacing_mm

    # TODO: Implement actual parallelproj operator creation and application
    # This is a placeholder until we have the full implementation

    # For now, return zeros
    projections = np.zeros((n_projs, n_rows, n_cols), dtype=np.float32)

    return ForwardProjectionResult(
        projections=projections,
        geometry=geometry,
        row_indices=row_indices,
        col_indices=col_indices,
        proj_indices=proj_indices,
    )


# Module-level warning on import if parallelproj not available
if not PARALLELPROJ_AVAILABLE:
    warnings.warn(
        "parallelproj not available. Forward projection will return zeros. "
        "Install with: conda install -c conda-forge parallelproj",
        RuntimeWarning,
        stacklevel=2,
    )
