"""Computational backend for the CT orientation viewer.

Holds the non-UI, numerical / data-processing code: volume handling, cone-beam
projection geometry, forward projection, and the parallelproj integration.
The Streamlit / Plotly UI lives in :mod:`visualization` and imports from here.
"""

from backend.geometry import (
    ProjectionGeometry,
    load_geometry,
    load_geometry_from_txt,
    load_geometry_from_yaml,
)
from backend.volume import Volume

# `parallelproj` is an optional third-party dependency (installed via
# conda-forge, not pip). It is deliberately imported lazily so that
# ``import backend`` — and the UI / tests that import the types above —
# works even when parallelproj is not installed. The forward projection
# entry point guards on ``backend.forward_project.PARALLELPROJ_AVAILABLE``.
try:
    from . import parallelproj

    PARALLELPROJ_AVAILABLE = True
except Exception:  # pragma: no cover - depends on environment
    parallelproj = None  # type: ignore[assignment]
    PARALLELPROJ_AVAILABLE = False

from backend import forward_project  # noqa: E402
from backend import loaders  # noqa: E402

__all__ = [
    "ProjectionGeometry",
    "Volume",
    "PARALLELPROJ_AVAILABLE",
    "forward_project",
    "load_geometry",
    "load_geometry_from_txt",
    "load_geometry_from_yaml",
    "loaders",
    "parallelproj",
]
