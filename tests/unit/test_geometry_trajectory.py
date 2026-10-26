"""Tests for geometry trajectory functions."""

import plotly.graph_objects as go
import pytest

from visualization.geometry import ProjectionGeometry
from visualization.volume3d import (
    add_trajectory_to_figure,
    get_detector_position,
    get_source_position,
    get_trajectory_positions,
)


def test_get_source_position():
    """Test source position calculation at angle 0 (anterior = +X)."""
    geo = ProjectionGeometry(sid=600.0)

    # At 0°, source should be at +X (anterior)
    pos = get_source_position(geo, 0.0)
    assert pos[0] == pytest.approx(600.0, rel=0.01)  # X = sid * cos(0) = 600
    assert pos[1] == pytest.approx(0.0, rel=0.01)  # Y = sid * sin(0) = 0
    assert pos[2] == pytest.approx(0.0, rel=0.01)  # Z = 0


def test_get_source_position_90_degrees():
    """Test source position at 90° (left side)."""
    geo = ProjectionGeometry(sid=600.0)

    pos = get_source_position(geo, 90.0)
    assert pos[0] == pytest.approx(0.0, rel=0.01)  # X = sid * cos(90) = 0
    assert pos[1] == pytest.approx(600.0, rel=0.01)  # Y = sid * sin(90) = 600
    assert pos[2] == pytest.approx(0.0, rel=0.01)


def test_get_detector_position():
    """Test detector position calculation - opposite to source."""
    geo = ProjectionGeometry(sid=600.0)

    # At 0°, detector should be at -X (posterior)
    pos = get_detector_position(geo, 0.0)
    assert pos[0] == pytest.approx(-600.0, rel=0.01)  # X = -sid * cos(0) = -600
    assert pos[1] == pytest.approx(0.0, rel=0.01)  # Y = -sid * sin(0) = 0


def test_get_trajectory_positions():
    """Test trajectory generation for multiple projections."""
    geo = ProjectionGeometry(sid=600.0)

    src_positions, det_positions = get_trajectory_positions(geo, n_projections=4)

    # Should have 4 positions each
    assert len(src_positions) == 4
    assert len(det_positions) == 4

    # First and last should be at same angle (full circle)
    # But for 4 projections: 0°, 90°, 180°, 270° -> 0° = 360°
    src0 = src_positions[0]
    src3 = src_positions[3]
    # At 0° and 360°, positions should be same
    assert src0[0] == pytest.approx(src3[0], rel=0.01)


def test_get_source_position_with_offsets():
    """Test source position with offsets."""
    geo = ProjectionGeometry(sid=600.0, source_offset_x=10.0, source_offset_y=20.0)

    pos = get_source_position(geo, 0.0)
    # Base at 0°: (600, 0, 0) + offset (10, 20, 0) = (610, 20, 0)
    assert pos[0] == pytest.approx(610.0, rel=0.01)
    assert pos[1] == pytest.approx(20.0, rel=0.01)


def test_add_trajectory_to_figure():
    """Test adding trajectory to Plotly figure."""
    geo = ProjectionGeometry(sid=600.0)

    # Generate small number of positions
    src_positions, det_positions = get_trajectory_positions(geo, n_projections=4)

    # Create empty figure and add trajectory
    fig = go.Figure()
    fig = add_trajectory_to_figure(fig, src_positions, det_positions, downsample=1)

    # Should have 2 traces: source and detector
    assert len(fig.data) == 2

    # First trace is source (orange)
    assert fig.data[0].marker.color == "orange"
    assert fig.data[0].name == "Source Trajectory"

    # Second trace is detector (turquoise)
    assert fig.data[1].marker.color == "turquoise"
    assert fig.data[1].name == "Detector Trajectory"


def test_add_trajectory_to_figure_with_downsample():
    """Test trajectory downsampling."""
    geo = ProjectionGeometry(sid=600.0)

    src_positions, det_positions = get_trajectory_positions(geo, n_projections=10)

    fig = go.Figure()
    fig = add_trajectory_to_figure(fig, src_positions, det_positions, downsample=5)

    # Should have 10/5 = 2 points per trace
    assert len(fig.data[0].x) == 2  # Source
    assert len(fig.data[1].x) == 2  # Detector
