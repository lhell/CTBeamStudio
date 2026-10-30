"""Tests for forward projection module."""

import numpy as np

from visualization.geometry import ProjectionGeometry
from visualization.volume import Volume


def test_forward_projection_result_dataclass():
    """Test ForwardProjectionResult can be created."""
    from visualization.forward_project import ForwardProjectionResult

    projections = np.zeros((10, 64, 512))
    geometry = ProjectionGeometry()
    result = ForwardProjectionResult(
        projections=projections,
        geometry=geometry,
        row_indices=list(range(64)),
        col_indices=list(range(512)),
        proj_indices=list(range(10)),
    )
    assert result.projections.shape == (10, 64, 512)
    assert result.geometry is not None
    assert len(result.row_indices) == 64
    assert len(result.col_indices) == 512
    assert len(result.proj_indices) == 10


def test_forward_project_returns_correct_shape():
    """Test forward_project returns projections with correct shape."""
    from visualization.forward_project import forward_project

    # Create simple volume (air = 0 HU)
    volume = Volume(
        array=np.ones((10, 10, 10), dtype=np.int16) * 0,
        spacing=(2.5, 1.0, 1.0),
        origin=(0, 0, 0),
        meta={},
    )

    geometry = ProjectionGeometry(
        n_det_cols=512, n_det_rows=64, projections_per_rotation=230
    )

    result = forward_project(volume, geometry)

    # Should return (n_projections, n_rows, n_cols)
    assert result.projections.shape[0] == 230
    assert result.projections.shape[1] == 64
    assert result.projections.shape[2] == 512


def test_forward_project_with_selection():
    """Test forward_project with row/col/projection selection."""
    from visualization.forward_project import forward_project

    volume = Volume(
        array=np.ones((20, 20, 20), dtype=np.int16) * 0,
        spacing=(2.5, 1.0, 1.0),
        origin=(0, 0, 0),
        meta={},
    )

    geometry = ProjectionGeometry(
        n_det_cols=512, n_det_rows=64, projections_per_rotation=230
    )

    # Select only central row and 10 projections
    result = forward_project(
        volume,
        geometry,
        row_indices=[32],  # central row
        proj_indices=list(range(0, 230, 23)),  # 10 projections
    )

    assert result.projections.shape[0] == 10  # 10 projections
    assert result.projections.shape[1] == 1  # 1 row
    assert result.projections.shape[2] == 512  # all cols


def test_parallelproj_availability():
    """Test that parallelproj availability flag works."""
    from visualization.forward_project import PARALLELPROJ_AVAILABLE

    # Just check the flag exists and is a boolean
    assert isinstance(PARALLELPROJ_AVAILABLE, bool)
