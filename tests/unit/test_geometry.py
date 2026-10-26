"""Tests for ProjectionGeometry dataclass."""

import pytest
from pathlib import Path

from visualization.geometry import (
    ProjectionGeometry,
    load_geometry,
    load_geometry_from_yaml,
    load_geometry_from_txt,
)


# Test fixtures
@pytest.fixture
def yaml_file(tmp_path):
    """Create a test YAML geometry file."""
    content = """# CT Projection Geometry
geometry_type: cone_beam
detector_shape: flat

# Distances (mm)
sdd: 1085.6
sid: 600.0

# Detector
n_det_cols: 736
n_det_rows: 64
det_col_spacing_mm: 1.2858
det_row_spacing_mm: 1.0947

# Angles (degrees)
source_angle: 0.0
detector_in_plane_angle: 0.0
detector_out_of_plane_angle: 0.0
detector_tilt_angle: 0.0

# Helical
pitch: 0.8

# Offsets (mm)
source_offset_x: 0.0
source_offset_y: 0.0
source_offset_z: 0.0
detector_offset_x: 0.0
detector_offset_y: 0.0
"""
    file_path = tmp_path / "geometry.yaml"
    file_path.write_text(content)
    return file_path


@pytest.fixture
def mayo_txt_file(tmp_path):
    """Create a test Mayo Clinic format text file."""
    content = """GANTRY GEOMETRY -------------------------------------------------
                        Detector Shape       CYLINDRICAL
           Type of Projection Geometry       FANBEAM
       Anode-to-detector Distance (mm)       1085.6
                   Number of Detector Rows   64
                Number of Detector Columns   736
             Detector Row Width (mm)         1.0947
          Detector Column Width (mm)         1.2858
      Detector Central Elements (Col, Row)  (369.625, 32.5)

ACQUISITION -----------------------------------------------------
                                      Pitch  0.8
                         Rotation Time (ms)  500
"""
    file_path = tmp_path / "geometry.txt"
    file_path.write_text(content)
    return file_path


# === Basic Creation Tests ===

def test_default_geometry():
    """Test that default geometry values are correct."""
    geo = ProjectionGeometry()

    # Check default distances
    assert geo.sdd == 1000.0
    assert geo.sid == 500.0

    # Check default detector properties
    assert geo.n_det_cols == 512
    assert geo.n_det_rows == 64
    assert geo.det_col_spacing_mm == 1.0
    assert geo.det_row_spacing_mm == 1.0
    assert geo.detector_shape == "flat"

    # Check default helical
    assert geo.pitch == 1.0

    # Check default metadata
    assert geo.geometry_type == "cone_beam"
    assert geo.source == "unknown"

    # Check angles default to 0
    assert geo.source_angle == 0.0
    assert geo.detector_in_plane_angle == 0.0
    assert geo.detector_out_of_plane_angle == 0.0
    assert geo.detector_tilt_angle == 0.0

    # Check offsets default to 0
    assert geo.source_offset_x == 0.0
    assert geo.source_offset_y == 0.0
    assert geo.source_offset_z == 0.0
    assert geo.detector_offset_x == 0.0
    assert geo.detector_offset_y == 0.0


def test_custom_geometry():
    """Test creating geometry with custom values."""
    geo = ProjectionGeometry(
        source_angle=45.0,
        sdd=1085.6,
        sid=600.0,
        n_det_cols=736,
        n_det_rows=64,
        det_col_spacing_mm=1.2858,
        det_row_spacing_mm=1.0947,
        pitch=0.8,
    )

    assert geo.source_angle == 45.0
    assert geo.sdd == 1085.6
    assert geo.sid == 600.0
    assert geo.n_det_cols == 736
    assert geo.n_det_rows == 64
    assert geo.det_col_spacing_mm == 1.2858
    assert geo.det_row_spacing_mm == 1.0947
    assert geo.pitch == 0.8


# === Validation Tests ===

def test_validation_negative_sdd():
    """Test that negative SDD raises ValueError."""
    with pytest.raises(ValueError, match="sdd must be positive"):
        ProjectionGeometry(sdd=-100.0)


def test_validation_sid_greater_than_sdd():
    """Test that sid >= sdd raises ValueError."""
    with pytest.raises(ValueError, match="sid must be less than sdd"):
        ProjectionGeometry(sdd=500.0, sid=600.0)


def test_validation_invalid_detector_shape():
    """Test that invalid detector_shape raises ValueError."""
    with pytest.raises(ValueError, match="detector_shape must be one of"):
        ProjectionGeometry(detector_shape="invalid")


def test_validation_negative_sid():
    """Test that negative SID raises ValueError."""
    with pytest.raises(ValueError, match="sid must be positive"):
        ProjectionGeometry(sid=-100.0)


def test_validation_zero_detector_cols():
    """Test that zero detector columns raises ValueError."""
    with pytest.raises(ValueError, match="n_det_cols must be positive"):
        ProjectionGeometry(n_det_cols=0)


def test_validation_negative_pitch():
    """Test that negative pitch raises ValueError."""
    with pytest.raises(ValueError, match="pitch must be positive"):
        ProjectionGeometry(pitch=-0.5)


# === Computed Properties Tests ===

def test_computed_collimation_width():
    """Test collimation_width computation."""
    geo = ProjectionGeometry(
        n_det_rows=64,
        det_row_spacing_mm=1.0947,
    )
    # Expected: 64 * 1.0947 = 70.0608
    assert geo.collimation_width == pytest.approx(70.0608, rel=1e-3)


def test_computed_fan_angle():
    """Test fan_angle computation."""
    geo = ProjectionGeometry(
        n_det_cols=512,
        det_col_spacing_mm=1.0,
        sdd=1000.0,
    )
    # fan_angle = (512 * 1.0) / 1000 * (180 / pi)
    #            = 0.512 * 57.2958
    #            = 29.335
    expected = (512 * 1.0) / 1000.0 * (180 / 3.14159265)
    assert geo.fan_angle == pytest.approx(expected, rel=1e-3)


def test_computed_cone_angle():
    """Test cone_angle computation."""
    geo = ProjectionGeometry(
        n_det_rows=64,
        det_row_spacing_mm=1.0,
        sdd=1000.0,
    )
    # cone_angle = (64 * 1.0) / 1000 * (180 / pi)
    #             = 0.064 * 57.2958
    #             = 3.6669
    expected = (64 * 1.0) / 1000.0 * (180 / 3.14159265)
    assert geo.cone_angle == pytest.approx(expected, rel=1e-3)


# === Loader Tests ===

def test_load_geometry_from_yaml(yaml_file):
    """Test loading geometry from YAML file."""
    geo = load_geometry_from_yaml(yaml_file)

    assert geo.sdd == 1085.6
    assert geo.sid == 600.0
    assert geo.n_det_cols == 736
    assert geo.n_det_rows == 64
    assert geo.det_col_spacing_mm == 1.2858
    assert geo.det_row_spacing_mm == 1.0947
    assert geo.pitch == 0.8
    assert geo.geometry_type == "cone_beam"


def test_load_geometry_from_mayo_txt(mayo_txt_file):
    """Test loading geometry from Mayo Clinic format text file."""
    geo = load_geometry_from_txt(mayo_txt_file)

    assert geo.sdd == 1085.6
    assert geo.n_det_cols == 736
    assert geo.n_det_rows == 64
    assert geo.det_col_spacing_mm == 1.2858
    assert geo.det_row_spacing_mm == 1.0947
    assert geo.pitch == 0.8
    assert geo.detector_shape == "curved"
    assert geo.geometry_type == "fan_beam"


def test_load_geometry_auto_detect(yaml_file, mayo_txt_file):
    """Test auto-detecting file format."""
    # YAML detection
    geo_yaml = load_geometry(yaml_file)
    assert geo_yaml.sdd == 1085.6

    # TXT detection
    geo_txt = load_geometry(mayo_txt_file)
    assert geo_txt.sdd == 1085.6


def test_load_geometry_unsupported_format(tmp_path):
    """Test that unsupported format raises ValueError."""
    # Create a file with unsupported extension
    unsupported_file = tmp_path / "geometry.json"
    unsupported_file.write_text("{}")

    with pytest.raises(ValueError, match="Unsupported geometry file format"):
        load_geometry(unsupported_file)
