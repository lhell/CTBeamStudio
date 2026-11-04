"""Cone-beam projector wrapping parallelproj's joseph3d line tracer.

parallelproj does not ship a dedicated ``ConeBeamProjector``. A cone-beam
projector is built by defining one line of response (LOR) per source-to-
detector-element pair and passing them to the
:class:`parallelproj.projectors.ListmodePETProjector`, which traces every line
with joseph3d. This module wraps that projector so that its flat
``out_shape = (n_projections * n_rows * n_cols,)`` is exposed instead as the
2-D projection grid ``(n_projections, n_rows, n_cols)``.

The LOR start/end points come from
:meth:`~backend.parallelproj.geometry.ConeBeamGeometry.calculate_xray_beam_list`,
ordered ``(proj, col, row)`` (row = fastest axis), which matches the reshaped
output layout.

Volumes enter/leave in the parallelproj ``(x, y, z)`` voxel ordering (World B);
see :mod:`backend.parallelproj.shape`.
"""

from typing import Tuple

import numpy as np
from parallelproj.projectors import ListmodePETProjector

from .shape import spacing_to_parallelproj, tuple_to_parallelproj


def _as_numpy_xyz(positions) -> np.ndarray:
    """Convert LOR positions (numpy / torch, any device) to a C-contiguous
    float32 numpy array of shape ``(n, 3)`` in ``(x, y, z)`` world order.

    parallelproj's joseph3d kernel requires C-contiguous float32 arrays, so
    torch tensors are moved to CPU and have their layout normalised here.
    """
    if hasattr(positions, "detach"):  # torch.Tensor
        positions = positions.detach().cpu().numpy()
    arr = np.asarray(positions).reshape(-1, 3).astype(np.float32)
    return np.ascontiguousarray(arr)


class ConeBeamProjector:
    """Cone-beam linear projector over a 3-D volume (parallelproj-backend).

    Wraps :class:`~parallelproj.projectors.ListmodePETProjector` for a fixed
    LOR set and reshapes its flat event output to a 2-D projection grid,
    so that applying the projector to a volume yields ``(n_projections,
    n_rows, n_cols)``.

    ``in_shape`` and ``out_shape`` follow parallelproj's convention
    (``in_shape = (nx, ny, nz)`` voxel ordering, ``out_shape`` the reshaped
    projection grid). The wrapped operator is available as :attr:`operator`
    for use with the autograd layers in :mod:`backend.parallelproj.layers`.
    """

    def __init__(
        self,
        pos_beam_start,
        pos_beam_end,
        img_shape_zyx: Tuple[int, int, int],
        spacing_zyx: Tuple[float, float, float],
        origin_zyx: Tuple[float, float, float],
        n_det_rows: int,
        n_det_cols: int,
        n_projections: int,
    ):
        """Initialize the cone-beam projector.

        Args:
            pos_beam_start: LOR start (source) positions,
                ``(n_projections * n_rows * n_cols, 3)`` in ``(x, y, z)`` order.
            pos_beam_end: LOR end (detector) positions, same shape/order.
            img_shape_zyx: Volume shape in project order ``(z, y, x)``.
            spacing_zyx: Volume spacing in project order ``(dz, dy, dx)`` (mm).
            origin_zyx: Volume origin in project order ``(oz, oy, ox)`` (mm).
            n_det_rows: Number of detector rows (axial / z).
            n_det_cols: Number of detector columns (in-plane / y).
            n_projections: Number of projection angles.
        """
        voxel_size = spacing_to_parallelproj(spacing_zyx)
        img_origin = tuple_to_parallelproj(origin_zyx)

        self._operator = ListmodePETProjector(
            np.asarray(pos_beam_start),
            np.asarray(pos_beam_end),
            tuple_to_parallelproj(img_shape_zyx),
            voxel_size,
            img_origin,
        )

        self.n_projections = n_projections
        self.n_det_rows = n_det_rows
        self.n_det_cols = n_det_cols

    # -- shape surface -------------------------------------------------------
    @property
    def in_shape(self) -> Tuple[int, int, int]:
        """Parallelproj voxel ordering of the volume: ``(nx, ny, nz)``."""
        return self._operator.in_shape

    @property
    def out_shape(self) -> Tuple[int, int, int]:
        """Reshaped projection grid: ``(n_projections, n_rows, n_cols)``."""
        return (self.n_projections, self.n_det_rows, self.n_det_cols)

    @property
    def flat_out_shape(self) -> Tuple[int]:
        """Flat LOR count, matching the wrapped operator's ``out_shape``."""
        return (self._operator.out_shape[0],)

    @property
    def operator(self):
        """The wrapped parallelproj :class:`ListmodePETProjector`."""
        return self._operator

    # -- application ----------------------------------------------------------
    def apply(self, volume_xyz) -> np.ndarray:
        """Project a volume to a ``(n_projections, n_rows, n_cols)`` grid.

        ``volume_xyz`` is a single volume in parallelproj ``(nx, ny, nz)``
        ordering. Returns a float32 array of shape
        ``(n_projections, n_rows, n_cols)``.

        The flat operator output is ordered ``(proj, col, row)`` (matches the
        LOR layout), so it is reshaped via ``(proj, cols, rows)`` and then the
        ``col``/``row`` axes are swapped to produce the ``(proj, rows, cols)``
        grid.
        """
        flat = np.asarray(
            self._operator(np.ascontiguousarray(volume_xyz, dtype=np.float32))
        )
        return (
            flat.reshape(self.n_projections, self.n_det_cols, self.n_det_rows)
            .swapaxes(1, 2)
            .copy()
        )

    def adjoint(self, proj_zyx) -> np.ndarray:
        """Adjoint of :meth:`apply` (back projection).

        ``proj_zyx`` is a ``(n_projections, n_rows, n_cols)`` array. Returns a
        volume in parallelproj ``(nx, ny, nz)`` ordering. This inverts the
        reshuffling done in :meth:`apply`.
        """
        proj = np.asarray(proj_zyx)
        flat = proj.swapaxes(1, 2).reshape(self.flat_out_shape)
        flat = np.ascontiguousarray(flat, dtype=np.float32)
        return np.asarray(self._operator.adjoint(flat))
