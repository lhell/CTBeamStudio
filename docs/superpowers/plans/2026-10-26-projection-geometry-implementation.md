# ProjectionGeometry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create ProjectionGeometry class and loaders for cone-beam CT projection data.

**Architecture:** A dataclass-based geometry model with file loaders for YAML and TXT formats. Supports offsets where source offsets cause detector to follow, while detector offsets are independent.

**Tech Stack:** Python, dataclasses, PyYAML, pathlib

**Spec:** `docs/superpowers/specs/2026-10-26-projection-geometry-design.md`

---

## Global Constraints

- Python 3.10+ (dataclasses)
- PyYAML for YAML loading
- All angles in degrees, distances in mm
- Source angle 0° = anterior, positive = CCW
- Detector default: perpendicular to source ray

---

## Review Focus

- **Offset behavior:** Source offset must cause detector to follow; detector offset must be independent. The class stores both but the behavior is documented.
- **Validation:** Negative distances, sdd <= sid must raise errors
- **File format detection:** Must auto-detect YAML vs TXT from extension
- **Backwards compatibility:** TXT loader must handle the Mayo Clinic format
- **Computed properties:** fan_angle and cone_angle must use sdd (not sid)

---

## File Structure

```
src/visualization/
├── geometry.py          # NEW: ProjectionGeometry class
├── loaders/
│   └── projection.py    # NEW: Geometry loaders (YAML + TXT)
```

```
tests/
├── unit/
│   └── test_geometry.py # NEW: Unit tests for ProjectionGeometry
```

---

## Task 1: ProjectionGeometry Dataclass

**Files:**
- Create: `src/visualization/geometry.py`

**Interfaces:**
- Produces: `ProjectionGeometry` class with all fields from spec

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_geometry.py
import pytest
from src.visualization.geometry import ProjectionGeometry


def test_default_geometry():
    """Test ProjectionGeometry with default values."""
    g = ProjectionGeometry()
    assert g.source_angle == 0.0
    assert g.sdd == 1000.0
    assert g.sid == 500.0
    assert g.detector_shape == "flat"
    assert g.n_det_cols == 512
    assert g.n_det_rows == 64


def test_custom_geometry():
    """Test ProjectionGeometry with custom values."""
    g = ProjectionGeometry(
        source_angle=45.0,
        sdd=1085.6,
        sid=600.0,
        n_det_cols=736,
        n_det_rows=64,
        det_col_spacing_mm=1.2858,
        det_row_spacing_mm=1.0947,
        pitch=0.8
    )
    assert g.source_angle == 45.0
    assert g.sdd == 1085.6
    assert g.sid == 600.0


def test_validation_negative_sdd():
    """Test that negative sdd raises ValueError."""
    with pytest.raises(ValueError, match="sdd must be positive"):
        ProjectionGeometry(sdd=-100)


def test_validation_sid_greater_than_sdd():
    """Test that sid >= sdd raises ValueError."""
    with pytest.raises(ValueError, match="sid must be less than sdd"):
        ProjectionGeometry(sdd=500, sid=600)


def test_validation_invalid_detector_shape():
    """Test that invalid detector_shape raises ValueError."""
    with pytest.raises(ValueError, match="detector_shape must be one of"):
        ProjectionGeometry(detector_shape="invalid")


def test_computed_collimation_width():
    """Test collimation_width computed property."""
    g = ProjectionGeometry(n_det_rows=64, det_row_spacing_mm=1.0947)
    assert g.collimation_width == pytest.approx(70.06, rel=0.01)


def test_computed_fan_angle():
    """Test fan_angle computed property."""
    g = ProjectionGeometry(n_det_cols=736, det_col_spacing_mm=1.2858, sdd=1085.6)
    expected_angle = (736 * 1.2858) / 1085.6 * (180 / 3.14159265)
    assert g.fan_angle == pytest.approx(expected_angle, rel=0.01)


def test_computed_cone_angle():
    """Test cone_angle computed property."""
    g = ProjectionGeometry(n_det_rows=64, det_row_spacing_mm=1.0947, sdd=1085.6)
    expected_angle = (64 * 1.0947) / 1085.6 * (180 / 3.14159265)
    assert g.cone_angle == pytest.approx(expected_angle, rel=0.01)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_geometry.py -v`
Expected: FAIL with "module not found: src.visualization.geometry"

- [ ] **Step 3: Implement ProjectionGeometry in `src/visualization/geometry.py`**

```python
"""Projection geometry for cone-beam CT projection data."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class ProjectionGeometry:
    """Geometry parameters for cone-beam CT projection data.
    
    The geometry consists of:
    - Source position (angle + optional offset from central beam)
    - Detector position (defined by central beam + optional independent offset)
    - Detector angles (tilt within/out of plane)
    
    When source has an offset, the detector follows (stays connected by central beam).
    When detector has an offset, it moves independently of the source.
    """
    
    # === Angles (degrees) ===
    
    source_angle: float = 0.0
    """Source position around Z-axis. 0° = anterior, positive = CCW."""
    
    detector_in_plane_angle: float = 0.0
    """Detector rotation within its plane, stays perpendicular to source ray."""
    
    detector_out_of_plane_angle: float = 0.0
    """Detector tilt right/left from perpendicular to central beam."""
    
    detector_tilt_angle: float = 0.0
    """Detector backwards tilt from perpendicular. Positive = tilt backwards."""
    
    # === Distances (mm) ===
    
    sdd: float = 1000.0
    """Source-to-detector distance."""
    
    sid: float = 500.0
    """Source-to-isocenter distance (mm)."""
    
    # === Detector Properties ===
    
    n_det_cols: int = 512
    """Number of detector columns."""
    
    n_det_rows: int = 64
    """Number of detector rows."""
    
    det_col_spacing_mm: float = 1.0
    """Detector column spacing (mm) - center to center distance."""
    
    det_row_spacing_mm: float = 1.0
    """Detector row spacing (mm) - center to center distance."""
    
    detector_shape: str = "flat"
    """Detector shape: 'flat' (planar) or 'curved' (cylindrical)."""
    
    # === Helical Scan Parameters ===
    
    pitch: float = 1.0
    """Table feed per gantry rotation / collimation width."""
    
    # === Source Offsets (detector FOLLOWS when source moves) ===
    
    source_offset_x: float = 0.0
    """Source lateral offset (mm) in X direction."""
    
    source_offset_y: float = 0.0
    """Source longitudinal offset (mm), perpendicular to table."""
    
    source_offset_z: float = 0.0
    """Source Z offset (mm), table feed direction."""
    
    # === Detector Offsets (moves INDEPENDENTLY of source) ===
    
    detector_offset_x: float = 0.0
    """Detector lateral offset (mm), independent of source."""
    
    detector_offset_y: float = 0.0
    """Detector longitudinal offset (mm), independent of source."""
    
    # === Metadata ===
    
    geometry_type: str = "cone_beam"
    """Geometry type: 'cone_beam', 'parallel', 'fan_beam'."""
    
    source: str = "unknown"
    """Scanner source/manufacturer."""
    
    def __post_init__(self) -> None:
        """Validate geometry parameters."""
        # Validate distances
        if self.sdd <= 0:
            raise ValueError("sdd must be positive")
        if self.sid <= 0:
            raise ValueError("sid must be positive")
        if self.sid >= self.sdd:
            raise ValueError("sid must be less than sdd")
        
        # Validate detector properties
        if self.n_det_cols <= 0:
            raise ValueError("n_det_cols must be positive")
        if self.n_det_rows <= 0:
            raise ValueError("n_det_rows must be positive")
        if self.det_col_spacing_mm <= 0:
            raise ValueError("det_col_spacing_mm must be positive")
        if self.det_row_spacing_mm <= 0:
            raise ValueError("det_row_spacing_mm must be positive")
        
        # Validate pitch
        if self.pitch <= 0:
            raise ValueError("pitch must be positive")
        
        # Validate detector shape
        valid_shapes = ("flat", "curved")
        if self.detector_shape not in valid_shapes:
            raise ValueError(f"detector_shape must be one of {valid_shapes}")
    
    @property
    def collimation_width(self) -> float:
        """Total detector collimation width (mm)."""
        return self.n_det_rows * self.det_row_spacing_mm
    
    @property
    def fan_angle(self) -> float:
        """Total fan angle (degrees)."""
        return (self.n_det_cols * self.det_col_spacing_mm) / self.sdd * (180 / 3.14159265)
    
    @property
    def cone_angle(self) -> float:
        """Total cone angle (degrees)."""
        return (self.n_det_rows * self.det_row_spacing_mm) / self.sdd * (180 / 3.14159265)


def load_geometry(path: Path) -> ProjectionGeometry:
    """Load projection geometry from file (auto-detects format).
    
    Args:
        path: Path to geometry file (.yaml, .yml, or .txt)
        
    Returns:
        ProjectionGeometry object with extracted parameters
        
    Raises:
        ValueError: If file format is unsupported
    """
    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        return load_geometry_from_yaml(path)
    elif suffix == ".txt":
        return load_geometry_from_txt(path)
    else:
        raise ValueError(f"Unsupported geometry file format: {suffix}")


def load_geometry_from_yaml(yaml_path: Path) -> ProjectionGeometry:
    """Load projection geometry from YAML file.
    
    Args:
        yaml_path: Path to YAML geometry file
        
    Returns:
        ProjectionGeometry object
    """
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    return ProjectionGeometry(**data)


def load_geometry_from_txt(txt_path: Path) -> ProjectionGeometry:
    """Load projection geometry from Mayo Clinic text format.
    
    Args:
        txt_path: Path to text geometry file
        
    Returns:
        ProjectionGeometry object
    """
    # Parse key-value pairs from file
    params = {}
    with open(txt_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or '-' * 20 in line:
                continue
            # Split on whitespace, handle parentheses in values
            parts = line.split()
            if len(parts) >= 2:
                key = ' '.join(parts[:-1])
                value = parts[-1].strip()
                
                # Map known keys
                if 'Anode-to-detector Distance' in key:
                    params['sdd'] = float(value)
                elif 'Detector Row Width' in key:
                    params['det_row_spacing_mm'] = float(value)
                elif 'Detector Column Width' in key:
                    params['det_col_spacing_mm'] = float(value)
                elif 'Number of Detector Rows' in key:
                    params['n_det_rows'] = int(value)
                elif 'Number of Detector Columns' in key:
                    params['n_det_cols'] = int(value)
                elif 'Pitch' in key:
                    params['pitch'] = float(value)
    
    return ProjectionGeometry(**params)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_geometry.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/visualization/geometry.py tests/unit/test_geometry.py
git commit -m "feat: add ProjectionGeometry dataclass"
```

---

## Task 2: YAML Format Loader Tests

**Files:**
- Create: `tests/unit/test_geometry_yaml.py`

**Interfaces:**
- Consumes: `src/visualization.geometry.load_geometry_from_yaml`, `ProjectionGeometry`
- Produces: Tests for YAML loading

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_geometry_yaml.py
import pytest
import tempfile
from pathlib import Path
from src.visualization.geometry import load_geometry_from_yaml, ProjectionGeometry


def test_load_geometry_from_yaml():
    """Test loading geometry from YAML file."""
    yaml_content = """
sdd: 1085.6
sid: 600.0
n_det_cols: 736
n_det_rows: 64
det_col_spacing_mm: 1.2858
det_row_spacing_mm: 1.0947
pitch: 0.8
source: Siemens
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        yaml_path = Path(f.name)
    
    try:
        geometry = load_geometry_from_yaml(yaml_path)
        assert geometry.sdd == 1085.6
        assert geometry.sid == 600.0
        assert geometry.n_det_cols == 736
        assert geometry.n_det_rows == 64
        assert geometry.det_col_spacing_mm == 1.2858
        assert geometry.det_row_spacing_mm == 1.0947
        assert geometry.pitch == 0.8
        assert geometry.source == "Siemens"
    finally:
        yaml_path.unlink()


def test_load_geometry_from_yaml_with_angles():
    """Test loading geometry with angle parameters."""
    yaml_content = """
sdd: 1085.6
sid: 600.0
source_angle: 45.0
detector_in_plane_angle: 5.0
detector_out_of_plane_angle: -2.0
detector_tilt_angle: 1.5
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        yaml_path = Path(f.name)
    
    try:
        geometry = load_geometry_from_yaml(yaml_path)
        assert geometry.source_angle == 45.0
        assert geometry.detector_in_plane_angle == 5.0
        assert geometry.detector_out_of_plane_angle == -2.0
        assert geometry.detector_tilt_angle == 1.5
    finally:
        yaml_path.unlink()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_geometry_yaml.py -v`
Expected: PASS (tests are for existing functionality in geometry.py)

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_geometry_yaml.py
git commit -m "test: add YAML loader tests"
```

---

## Task 3: TXT Format Loader Tests

**Files:**
- Create: `tests/unit/test_geometry_txt.py`

**Interfaces:**
- Consumes: `src/visualization.geometry.load_geometry_from_txt`, `ProjectionGeometry`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_geometry_txt.py
import pytest
import tempfile
from pathlib import Path
from src.visualization.geometry import load_geometry_from_txt, ProjectionGeometry


def test_load_geometry_from_mayo_txt():
    """Test loading geometry from Mayo Clinic TXT format."""
    txt_content = """GANTRY GEOMETRY -------------------------------------------------
                       Detector Shape       CYLINDRICAL
          Type of Projection Geometry       FANBEAM
      Anode-to-detector Distance (mm)       1085.6
                  Number of Detector Rows   64
               Number of Detector Columns   736
            Detector Row Width (mm)         1.0947
         Detector Column Width (mm)         1.2858

ACQUISITION -----------------------------------------------------
                                      Pitch  0.8
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(txt_content)
        txt_path = Path(f.name)
    
    try:
        geometry = load_geometry_from_txt(txt_path)
        assert geometry.sdd == 1085.6
        assert geometry.n_det_rows == 64
        assert geometry.n_det_cols == 736
        assert geometry.det_row_spacing_mm == 1.0947
        assert geometry.det_col_spacing_mm == 1.2858
        assert geometry.pitch == 0.8
    finally:
        txt_path.unlink()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_geometry_txt.py -v`
Expected: PASS (TXT loader already in geometry.py)

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_geometry_txt.py
git commit -m "test: add TXT loader tests"
```

---

## Task 4: Auto-detect Format Tests

**Files:**
- Modify: Add tests to existing test file

**Interfaces:**
- Consumes: `src/visualization.geometry.load_geometry`

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/unit/test_geometry.py
def test_load_geometry_auto_detect_yaml():
    """Test auto-detect loads YAML file."""
    yaml_content = "sdd: 1000\nsid: 500"
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        path = Path(f.name)
    try:
        from src.visualization.geometry import load_geometry
        g = load_geometry(path)
        assert g.sdd == 1000
    finally:
        path.unlink()


def test_load_geometry_auto_detect_txt():
    """Test auto-detect loads TXT file."""
    txt_content = "Anode-to-detector Distance (mm) 1000"
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(txt_content)
        path = Path(f.name)
    try:
        from src.visualization.geometry import load_geometry
        g = load_geometry(path)
        assert g.sdd == 1000
    finally:
        path.unlink()


def test_load_geometry_unsupported_format():
    """Test unsupported format raises ValueError."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write("{}")
        path = Path(f.name)
    try:
        from src.visualization.geometry import load_geometry
        with pytest.raises(ValueError, match="Unsupported geometry file format"):
            load_geometry(path)
    finally:
        path.unlink()
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/unit/test_geometry.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_geometry.py
git commit -m "test: add auto-detect format tests"
```

---

## Task 5: Update Existing Code (Optional)

**Files:**
- Modify: `src/visualization/volume3d.py`

**Interfaces:**
- Consumes: `ProjectionGeometry` from Task 1

- [ ] **Step 1: Update get_dicom_geometry to return ProjectionGeometry**

Review `src/visualization/volume3d.py` line 527 and update `get_dicom_geometry` to optionally return a `ProjectionGeometry` object for backwards compatibility with existing code.

- [ ] **Step 2: Run existing tests**

Run: `pytest tests/ -v --tb=short`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add src/visualization/volume3d.py
git commit -m "refactor: update get_dicom_geometry for ProjectionGeometry"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | ProjectionGeometry dataclass | geometry.py, test_geometry.py |
| 2 | YAML loader tests | test_geometry_yaml.py |
| 3 | TXT loader tests | test_geometry_txt.py |
| 4 | Auto-detect format tests | test_geometry.py (additions) |
| 5 | Update existing code (optional) | volume3d.py |
