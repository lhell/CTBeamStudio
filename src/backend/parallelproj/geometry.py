"""Cone-beam geometry and X-ray beam position calculation for parallelproj.

The source and detector positions are computed for every detector element of
every projection angle and turned into LOR start/end point pairs
(``pos_beam_start`` = source position, ``pos_beam_end`` = detector pixel
position). These pairs are consumed by a
:class:`~backend.parallelproj.projector.ConeBeamProjector` which wraps
parallelproj's ``ListmodePETProjector``.

The detector / source layout and rotation follow the project convention
(spec-compliant): the source circles the isocenter around the ``z`` axis (the
axial / slice direction), a projection angle of ``0`` puts the source on ``+x``
(anterior), and positive angles rotate the source counter-clockwise when viewed
from ``+z``. The ray direction therefore runs from the front (anterior) through
the volume towards the detector on the back (posterior) at ``0`` degrees.

The implementation follows the IMTCT reference
(``imtct/.../helpers_md/parallelproj_helper.py``) in naming and structure
(``xp = array_api_compat.torch``, ``pos_beam_start/end``, ``pos_source``,
``pos_detector``, ``R_angle``): positions are computed as PyTorch tensors on the
requested device and therefore work identically on CPU and CUDA. Two things are
deliberately different from the reference:

* the rotation is around the ``z`` axis (project spec) instead of the ``y``
  axis (IMTCT), and ``first_angle`` is respected;
* there is no Numba-CUDA kernel and no IMTCT import.
"""

from dataclasses import dataclass
from typing import Tuple

import numpy as np
import torch


@dataclass
class ConeBeamGeometry:
    """Cone-beam CT geometry parameters in parallelproj convention.

    Attributes:
        sid: Source-to-isocenter distance (mm).
        sdd: Source-to-detector distance (mm).
        n_projections: Number of projection angles.
        angular_inc_degree: Angular increment between projections (degrees).
        n_det_rows: Number of detector rows.
        n_det_cols: Number of detector columns.
        det_row_spacing_mm: Detector row spacing (mm).
        det_col_spacing_mm: Detector column spacing (mm).
        first_angle: Angle of the first projection (degrees). ``0`` = anterior
            (source on ``+x``), positive = counter-clockwise, rotation around
            the ``z`` axis (the axial / slice direction).
    """

    sid: float
    sdd: float
    n_projections: int
    angular_inc_degree: float
    n_det_rows: int
    n_det_cols: int
    det_row_spacing_mm: float
    det_col_spacing_mm: float
    first_angle: float = 0.0

    def __post_init__(self) -> None:
        """Validate geometry constraints."""
        if self.sid <= 0:
            raise ValueError(f"sid must be positive, got {self.sid}")
        if self.sdd <= self.sid:
            raise ValueError(f"sdd must be greater than sid, got sdd={self.sdd}")
        if self.n_projections <= 0:
            raise ValueError("n_projections must be positive")
        if self.n_det_rows <= 0 or self.n_det_cols <= 0:
            raise ValueError("detector rows/cols must be positive")
        if self.det_row_spacing_mm <= 0 or self.det_col_spacing_mm <= 0:
            raise ValueError("detector spacing must be positive")

    # ------------------------------------------------------------------
    # LOR (source -> detector) calculation
    # ------------------------------------------------------------------
    def calculate_xray_beam_list(
        self,
        detector_offset_rows_mm: float = 0.0,
        detector_offset_cols_mm: float = 0.0,
        dev: str = "cpu",
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Calculate LOR start/end points for all projections.

        Positions are computed as float32 ``torch.Tensor`` objects on the
        device given by ``dev`` (``"cpu"`` or ``"cuda"`` / ``"cuda:0"``), so the
        same code path serves both CPU and CUDA back-ends.

        Returns LORs ordered as ``(proj, col, row)`` — i.e. the flattened
        output has size ``n_projections * n_det_rows * n_det_cols`` with the
        fastest-varying axis being the detector *row*. Both returned tensors
        have shape ``(n_projections * n_det_rows * n_det_cols, 3)``, where the
        last axis is ``(x, y, z)`` world coordinates (parallelproj convention).

        The source starts at ``(sid, 0, 0)`` (anterior, ``+x``) and circles the
        isocenter around the ``z`` axis (CCW seen from ``+z``). The detector is
        placed opposite the source at a distance ``sdd - sid`` from isocenter
        and rotates together with it. The angle of projection ``i`` is
        ``first_angle + i * angular_inc_degree``.

        Args:
            detector_offset_rows_mm: Detector row offset (mm).
            detector_offset_cols_mm: Detector column offset (mm).
            dev: Device string (``"cpu"`` or ``"cuda"`` / ``"cuda:0"``) on which
                the position tensors are allocated.

        Returns:
            Tuple ``(pos_beam_start, pos_beam_end)``, each a float32 tensor of
            shape ``(n_projections * n_det_rows * n_det_cols, 3)``.
        """
        n_projs = self.n_projections
        n_rows = self.n_det_rows
        n_cols = self.n_det_cols
        total = n_projs * n_rows * n_cols

        device = torch.device(dev)

        # Start/end points in voxel-aligned world coordinates.
        pos_beam_start = torch.zeros((total, 3), dtype=torch.float32, device=device)
        pos_beam_end = torch.zeros((total, 3), dtype=torch.float32, device=device)

        # Source-to-isocenter (did = detector isocenter distance). The detector
        # sits opposite the source, i.e. at -did along the detector-plane normal.
        did = self.sdd - self.sid

        # Horizontal (in-plane / transversal) position on the detector, same
        # for every detector row.
        pos_detector_cols = (
            -n_cols / 2 + 0.5 + np.arange(n_cols)
        ) * self.det_col_spacing_mm + detector_offset_cols_mm
        # Vertical (axial) position on the detector, one value per row.
        pos_detector_rows = (
            -n_rows / 2 + 0.5 + np.arange(n_rows)
        ) * self.det_row_spacing_mm + detector_offset_rows_mm

        for idx_angle in range(n_projs):
            # Rotation angle around the z axis (CCW seen from +z).
            angle_radians = (
                (self.first_angle + idx_angle * self.angular_inc_degree) * np.pi / 180.0
            )
            c = torch.cos(torch.tensor(angle_radians, device=device))
            s = torch.sin(torch.tensor(angle_radians, device=device))

            # Rotation matrix around the z axis.
            R_angle = torch.stack(
                [
                    torch.stack([c, -s, torch.zeros_like(c)]),
                    torch.stack([s, c, torch.zeros_like(c)]),
                    torch.stack(
                        [torch.zeros_like(c), torch.zeros_like(c), torch.ones_like(c)]
                    ),
                ]
            )

            # Initial source position: (sid, 0, 0) -> circles in the xy plane.
            pos_source = torch.tensor(
                [self.sid, 0.0, 0.0], dtype=torch.float32, device=device
            )

            for idx_cols in range(n_cols):
                col = pos_detector_cols[idx_cols]

                # Initial detector position for the current column, in the
                # detector-local frame, before the source rotation.
                #   x: -did            (detector plane normal, opposite source)
                #   y: col             (in-plane / transversal column offset)
                #   z: pos_detector_rows (axial row offset, unchanged by z-rotation)
                pos_detector = torch.stack(
                    [
                        torch.full((n_rows,), -did, dtype=torch.float32, device=device),
                        torch.full(
                            (n_rows,), float(col), dtype=torch.float32, device=device
                        ),
                        torch.as_tensor(
                            pos_detector_rows, dtype=torch.float32, device=device
                        ),
                    ],
                    dim=1,
                )

                # Determine indices where to enter the projection beams.
                idx_start = idx_angle * n_rows * n_cols + idx_cols * n_rows
                idx_end = idx_start + n_rows

                # Rotate source and detector positions and store them.
                pos_beam_start[idx_start:idx_end, :] = R_angle @ pos_source
                pos_beam_end[idx_start:idx_end, :] = (R_angle @ pos_detector.T).T

        return pos_beam_start, pos_beam_end


def geometry_from_projection_geometry(geometry) -> ConeBeamGeometry:
    """Build a :class:`ConeBeamGeometry` from a ``ProjectionGeometry``.

    This is the adapter between the project's ``ProjectionGeometry`` (which
    stores rotation-level parameters) and the parallelproj cone-beam geometry
    used by the projector.

    Args:
        geometry: A ``backend.geometry.ProjectionGeometry`` instance.

    Returns:
        A :class:`ConeBeamGeometry` with matching parameters.
    """
    return ConeBeamGeometry(
        sid=geometry.sid,
        sdd=geometry.sdd,
        n_projections=geometry.projections_per_rotation,
        angular_inc_degree=360.0 / geometry.projections_per_rotation,
        n_det_rows=geometry.n_det_rows,
        n_det_cols=geometry.n_det_cols,
        det_row_spacing_mm=geometry.det_row_spacing_mm,
        det_col_spacing_mm=geometry.det_col_spacing_mm,
    )
