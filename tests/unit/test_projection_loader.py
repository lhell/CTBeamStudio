"""Tests for projection geometry loader."""

import pytest
from pathlib import Path

from visualization.loaders.projection import load_projection_geometry


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
