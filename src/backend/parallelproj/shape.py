"""Shape conversion helpers between the project volume convention and parallelproj.

This module defines the *only* place where volume / projection tensors change
their axis ordering between the project's internal convention (**World A**) and
the parallelproj convention (**World B**).

World A (project-internal volume)
    - Volume array shape: ``(z, y, x)``  (see :class:`backend.volume.Volume`)
    - Spacing: ``(dz, dy, dx)`` in mm
    - Origin:  ``(ox, oy, oz)`` in mm

World B (parallelproj)
    - Voxel shape: ``(nx, ny, nz)``  (parallelproj ``in_shape``)
    - Spacing: ``(dx, dy, dz)`` in mm
    - Origin: ``(ox, oy, oz)`` in mm

Batch convention (operator layers)
    - Input to :class:`~backend.parallelproj.layers.LinearSingleChannelOperator`
      (and of the ``LinearOperator`` itself in the forward projection path) is
      ``(B, 1, nx, ny, nz)``.
    - Projection output is batch-free ``(n_proj, n_rows, n_cols)`` (see
      :class:`~backend.parallelproj.projector.ConeBeamProjector`).
"""

from typing import Tuple

import numpy as np

#: Canonical shape of a single volume in parallelproj world: (nx, ny, nz).
PARALLELPROJ_VOLUME_SHAPE_INDEX = (2, 1, 0)
"""Maps a project ``(z, y, x)`` tuple onto ``(x, y, z)`` (parallelproj order)."""

#: Canonical batch layout expected by the operator layers.
BATCH_LAYOUT = "B,1,nx,ny,nz"
"""Layout of a batched volume tensor before projection."""


def tuple_to_parallelproj(shape: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """Convert a project volume shape ``(z, y, x)`` to parallelproj ``(x, y, z)``.

    Args:
        shape: Project-internal shape ``(z, y, x)``.

    Returns:
        Tuple ``(x, y, z)`` in parallelproj order.
    """
    z, y, x = shape
    return (x, y, z)


def spacing_to_parallelproj(
    spacing: Tuple[float, float, float],
) -> Tuple[float, float, float]:
    """Convert project spacing ``(dz, dy, dx)`` to parallelproj ``(dx, dy, dz)``.

    Args:
        spacing: Project-internal spacing ``(dz, dy, dx)`` in mm.

    Returns:
        Tuple ``(dx, dy, dz)`` in parallelproj order.
    """
    dz, dy, dx = spacing
    return (dx, dy, dz)


def to_parallelproj_batch(volume_zyx: np.ndarray) -> np.ndarray:
    """Reshape a ``(z, y, x)`` volume into the batched parallelproj layout.

    World A ``(z, y, x)`` -> World B ``(1, 1, nx, ny, nz)``.

    Args:
        volume_zyx: 3-D volume array in project-internal ``(z, y, x)`` order.

    Returns:
        5-D array of shape ``(1, 1, nx, ny, nz)`` (batch=1, channel=1).
    """
    return volume_zyx.transpose(PARALLELPROJ_VOLUME_SHAPE_INDEX)[None, None, ...]


def from_parallelproj_batch(batch: np.ndarray) -> np.ndarray:
    """Inverse of :func:`to_parallelproj_batch`.

    World B ``(1, 1, nx, ny, nz)`` -> World A ``(z, y, x)``.

    Args:
        batch: 5-D array of shape ``(B, C, nx, ny, nz)``.

    Returns:
        3-D array of shape ``(z, y, x)`` (first batch element, first channel).
    """
    return np.asarray(batch)[0, 0].transpose(PARALLELPROJ_VOLUME_SHAPE_INDEX)
