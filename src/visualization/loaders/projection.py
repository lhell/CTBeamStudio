"""Projection data loader for geometry from text files."""

from pathlib import Path

from visualization.geometry import ProjectionGeometry, load_geometry_from_txt


def load_projection_geometry(txt_path: Path) -> ProjectionGeometry:
    """Load projection geometry from text file.

    Args:
        txt_path: Path to geometry text file

    Returns:
        ProjectionGeometry object
    """
    return load_geometry_from_txt(txt_path)
