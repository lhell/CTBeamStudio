"""Projection data loader for geometry files."""

from pathlib import Path

from backend.geometry import ProjectionGeometry, load_geometry


def load_projection_geometry(path: Path | str) -> ProjectionGeometry:
    """Load projection geometry from a TXT, YAML, or YML file.

    Args:
        path: Path to a geometry file. The format is detected from the
            file suffix.

    Returns:
        ProjectionGeometry object

    Raises:
        ValueError: If the file format is not supported.
    """
    return load_geometry(Path(path))
