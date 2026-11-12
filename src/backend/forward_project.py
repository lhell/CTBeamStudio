"""Forward projection using parallelproj.

This module provides forward projection functionality to generate synthetic
projections from 3D volumes. It uses parallelproj when available, with a
fallback to a placeholder implementation for testing/development.
"""

import warnings
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

# The projection path needs both: parallelproj supplies the C library, and
# torch supplies the tensors the backend builds on top of it. Missing either
# one means "cannot project", so the UI must fall back to its warned-about
# zeros path instead of raising ModuleNotFoundError mid-run.
#
# torch is imported at module scope (not only inside
# _forward_project_parallelproj) precisely so this check reflects whether the
# projection path can actually run.
try:
    import parallelproj  # noqa: F401
    import torch  # noqa: F401

    PARALLELPROJ_AVAILABLE = True
except ImportError:
    PARALLELPROJ_AVAILABLE = False
    parallelproj = None


from backend.attenuation import ATTENUATION_UNITS
from backend.geometry import ProjectionGeometry
from backend.volume import Volume


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
        volume: 3D volume in linear attenuation units (``meta["unit"]``
            ``"1/mm"`` or ``"1/cm"``). HU is rejected: the projector
            integrates voxel values along the ray path, so the basis must be
            attenuation, not Hounsfield units. Build one with
            :func:`backend.attenuation.volume_for_projection`.
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

    Raises:
        ValueError: If ``volume`` is in HU rather than attenuation units.

    Note:
        If parallelproj is not available, returns zeros and emits a warning.
        This is useful for development and testing without conda environment.
    """
    # Determine detector dimensions
    n_rows = geometry.n_det_rows
    n_cols = geometry.n_det_cols

    unit = (volume.meta or {}).get("unit")
    if unit not in ATTENUATION_UNITS:
        raise ValueError(
            "forward projection requires attenuation values, but the volume "
            f"unit is {unit!r}. Convert it first with "
            "backend.attenuation.volume_for_projection()."
        )

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

    This is used when parallelproj is not available. A warning is emitted the
    first time it is exercised (not at import time), so ``import backend``
    stays silent while callers still learn why they get zeros.

    Args:
        volume: 3D volume to forward project.
        geometry: ProjectionGeometry with scanner parameters.
        row_indices: Which detector rows to project.
        col_indices: Which detector columns to project.
        proj_indices: Which projections to generate.
    """
    if not _placeholder_warned[0]:
        warnings.warn(
            "parallelproj not available. Forward projection will return zeros. "
            "Install with: conda install -c conda-forge parallelproj",
            RuntimeWarning,
            stacklevel=2,
        )
        _placeholder_warned[0] = True

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
    from backend.parallelproj import (
        ConeBeamProjector,
        geometry_from_projection_geometry,
        to_parallelproj_batch,
    )

    n_projs = len(proj_indices)

    # Choose device: CUDA only if available and requested.
    cuda_available = torch.cuda.is_available() and use_cuda
    dev = "cuda" if cuda_available else "cpu"

    # Build the parallelproj cone-beam geometry. ``n_projections`` reflects the
    # number of selected projections; the explicit ``projection_indices`` make
    # sure non-contiguous selections (e.g. a downsampled list) use the correct
    # gantry angles instead of a contiguous sequence starting at 0.
    cb_geometry = geometry_from_projection_geometry(geometry)
    cb_geometry.n_projections = n_projs

    # Volume is (z, y, x); origin is DICOM (x, y, z) -> reorder to (z, y, x).
    spacing_zyx = tuple(float(s) for s in volume.spacing)
    origin_zyx = (
        float(volume.origin[2]),
        float(volume.origin[1]),
        float(volume.origin[0]),
    )
    img_shape_zyx = volume.shape

    # The scan follows the volume's z position: the trajectory is centred on
    # the volume's z centre, so the first rotation intersects the volume even
    # when its DICOM z origin is far from the world origin. The 3D view uses
    # the same placement (see visualization.volume3d.get_trajectory_positions).
    z_center = origin_zyx[0] + 0.5 * (img_shape_zyx[0] - 1) * spacing_zyx[0]

    pos_beam_start, pos_beam_end = cb_geometry.calculate_xray_beam_list(
        dev=dev, projection_indices=proj_indices, z_offset_mm=z_center
    )

    projector = ConeBeamProjector(
        pos_beam_start,
        pos_beam_end,
        img_shape_zyx=img_shape_zyx,
        spacing_zyx=spacing_zyx,
        origin_zyx=origin_zyx,
        n_det_rows=cb_geometry.n_det_rows,
        n_det_cols=cb_geometry.n_det_cols,
        n_projections=n_projs,
    )

    # Volume -> parallelproj (nx, ny, nz) ordering, as float32 numpy.
    volume_array = volume.array.astype(np.float32)
    volume_xyz = to_parallelproj_batch(volume_array)[0, 0]

    full_proj = projector.apply(volume_xyz)

    # The projection axis is already in selection order. Only rows / columns
    # still need to be sliced.
    projections = full_proj[:, np.asarray(row_indices), :]
    projections = projections[:, :, np.asarray(col_indices)]

    return ForwardProjectionResult(
        projections=projections,
        geometry=geometry,
        row_indices=row_indices,
        col_indices=col_indices,
        proj_indices=proj_indices,
    )


# On the first fallback to the zero-placeholder (parallelproj missing), a
# RuntimeWarning is emitted so callers learn why they received zeros. This is
# deliberately lazy so ``import backend`` stays silent when parallelproj is not
# installed; the warning only appears when forward projection is actually used.
_placeholder_warned = [False]
