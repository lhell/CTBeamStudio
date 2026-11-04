"""Cone-beam forward projection built on parallelproj.

Public surface of the parallelproj integration:

* :class:`~.geometry.ConeBeamGeometry` and
  :func:`~.geometry.geometry_from_projection_geometry` — geometry parameters
  and the LOR (source -> detector) position calculation.
* :class:`~.projector.ConeBeamProjector` — wraps parallelproj's
  ``ListmodePETProjector`` and exposes a ``(n_projections, n_rows, n_cols)``
  projection grid.
* :mod:`~.layers` — PyTorch autograd layers over parallelproj linear operators.
* :mod:`~.shape` — tensor axis-order conversion between the project volume
  convention and parallelproj.
"""

from .geometry import ConeBeamGeometry, geometry_from_projection_geometry
from .projector import ConeBeamProjector
from .shape import (
    PARALLELPROJ_VOLUME_SHAPE_INDEX,
    from_parallelproj_batch,
    spacing_to_parallelproj,
    to_parallelproj_batch,
    tuple_to_parallelproj,
)

__all__ = [
    "ConeBeamGeometry",
    "ConeBeamProjector",
    "PARALLELPROJ_VOLUME_SHAPE_INDEX",
    "from_parallelproj_batch",
    "geometry_from_projection_geometry",
    "spacing_to_parallelproj",
    "to_parallelproj_batch",
    "tuple_to_parallelproj",
]
