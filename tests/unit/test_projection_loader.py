"""Tests for projection geometry loader."""

import pytest

from backend.loaders.projection import load_projection_geometry


def test_load_projection_geometry_from_txt(tmp_path):
    """Test loading geometry from TXT file."""
    # Create a test geometry TXT file
    txt_content = """GANTRY GEOMETRY -------------------------------------------------
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
    txt_file = tmp_path / "geometry.txt"
    txt_file.write_text(txt_content)

    # Load geometry
    geo = load_projection_geometry(txt_file)

    # Verify values
    assert geo.sdd == 1085.6
    assert geo.n_det_rows == 64
    assert geo.n_det_cols == 736
    assert geo.det_row_spacing_mm == 1.0947
    assert geo.det_col_spacing_mm == 1.2858
    assert geo.pitch == 0.8


def test_load_projection_geometry_from_yaml(tmp_path):
    """YAML files are auto-detected and loaded."""
    yaml_file = tmp_path / "geometry.yaml"
    yaml_file.write_text(
        "sdd: 1200.0\n"
        "sid: 600.0\n"
        "n_det_cols: 128\n"
        "n_det_rows: 32\n"
        "det_col_spacing_mm: 0.8\n"
        "det_row_spacing_mm: 0.9\n"
        "geometry_type: cone_beam\n"
        "source: Test Scanner\n"
    )

    geo = load_projection_geometry(yaml_file)

    assert geo.sdd == 1200.0
    assert geo.sid == 600.0
    assert geo.n_det_cols == 128
    assert geo.n_det_rows == 32
    assert geo.det_col_spacing_mm == 0.8
    assert geo.det_row_spacing_mm == 0.9
    assert geo.source == "Test Scanner"


def test_load_projection_geometry_from_yml(tmp_path):
    """The short .yml suffix is supported too."""
    yml_file = tmp_path / "geometry.yml"
    yml_file.write_text("sdd: 900.0\nsid: 450.0\n")

    geo = load_projection_geometry(yml_file)

    assert geo.sdd == 900.0
    assert geo.sid == 450.0


def test_load_projection_geometry_rejects_unsupported_format(tmp_path):
    """Unknown suffixes fail with a clear error."""
    path = tmp_path / "geometry.json"
    path.write_text("{}")

    with pytest.raises(ValueError, match="Unsupported geometry file format"):
        load_projection_geometry(path)
