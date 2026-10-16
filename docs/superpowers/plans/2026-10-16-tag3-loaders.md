# Tag 3 Implementation Plan — DICOM & NPY Loader

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Implement loaders for DICOM (T-11) and NumPy (T-12) formats that produce Volume objects in HU.

**Architecture:** 
- T-11 creates a DICOM loader that reads CT series, groups by SeriesInstanceUID, validates spacing, and converts to HU
- T-12 creates a NumPy loader that validates HU ranges and rejects normalized data
- Both produce Volume objects for consumption by windowing and MPR

**Tech Stack:** Python >=3.11, numpy, pydicom

**Spec:** docs/plan.md — T-11 and T-12 specifications

---

## Global Constraints

- Python >=3.11
- No data in repo/image — only phantom + synthetic fixtures
- Use pydicom exclusively — no SimpleITK, no ITK
- Data internally in HU — normalization only for display

### DICOM Coordinate System (Patient, left-handed)

| Axis | Direction | Description |
|------|-----------|-------------|
| X | Right → Left | Lateral (patient's right to left) |
| Y | Anterior → Posterior | Vorne → Hinten (Bauch → Rücken) |
| Z | Foot → Head | Longitudinal (feet to head) |

Note: parallelproj uses Z-axis rotation (unlike RTK which uses Y-axis)

---

## Review Focus

| Input/Failure Mode | Expected Behavior |
|---|---|
| DICOM with inconsistent slice spacing (>1%) | ValueError with position info |
| Gantry-tilt (non-axial ImageOrientationPatient) | Warning, continue processing |
| NPY with normalized values [0,1] or [-1,1] | ValueError with HU validation message |
| DICOM missing required tags | ValueError with tag name |
| Empty DICOM directory | ValueError no DICOM files found |

---

## Task 1: T-11 — DICOM Loader

**Files:**
- Create: src/visualization/loaders/dicom.py
- Create: tests/visualization/test_dicom_loader.py

**Interfaces:**
- Consumes: Volume from T-10
- Produces: scan_series(root: Path) -> list[SeriesInfo], load_dicom_series(files: list[Path]) -> Volume

```python
@dataclass
class SeriesInfo:
    series_instance_uid: str
    patient_id: str
    series_description: str
    n_slices: int
    dose_class: str  # full, quarter, half, unknown
```

- [ ] **Step 1: Create loader directory and __init__.py**

```bash
touch src/visualization/loaders/__init__.py
```

- [ ] **Step 2: Write the failing test in tests/visualization/test_dicom_loader.py**

```python
import numpy as np
import pytest
from pathlib import Path
from visualization.loaders.dicom import scan_series, load_dicom_series, SeriesInfo

def test_scan_series_groups_by_uid(tmp_path):
    result = scan_series(tmp_path)
    assert len(result) >= 1
    assert all(isinstance(s, SeriesInfo) for s in result)

def test_load_dicom_series_converts_to_hu():
    volume = load_dicom_series(files)
    assert volume.array.min() < 0  # Air should be negative HU

def test_scan_series_empty_directory_raises(tmp_path):
    with pytest.raises(ValueError, match="no DICOM files"):
        scan_series(tmp_path)
```

- [ ] **Step 3: Run test to verify it fails**

```bash
python -m pytest tests/visualization/test_dicom_loader.py -v
```

Expected: FAIL with ModuleNotFoundError

- [ ] **Step 4: Implement DICOM loader in src/visualization/loaders/dicom.py**

Key functions:
- scan_series(root: Path) -> list[SeriesInfo]
- load_dicom_series(files: list[Path]) -> Volume
- classify_dose(series_description: str) -> str

Implementation notes:
- Use pydicom.dcmread() to read files
- Group by SeriesInstanceUID
- Sort slices by ImagePositionPatient projected onto normal from ImageOrientationPatient
- HU = pixel_value * RescaleSlope + RescaleIntercept (default slope=1, intercept=-1024)
- Check spacing consistency: abs(spacing_i - spacing_mean) / spacing_mean > 0.01 -> raise ValueError
- Warn on gantry-tilt: 
  - Check `GantryDetectorTilt` (0018,1120) != 0
    - Positive = head tilts backward, Negative = head tilts forward
  - OR check if `ImageOrientationPatient` (0020,0032) deviates from [1,0,0,0,1,0] (axial)
  - Issue warning via `warnings.warn()`, do not abort
  - Document in docstring as v1 limitation
  - Note: parallelproj uses Z-axis rotation (unlike RTK which uses Y-axis)

- [ ] **Step 5: Run test to verify it passes**

```bash
python -m pytest tests/visualization/test_dicom_loader.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/visualization/loaders/dicom.py src/visualization/loaders/__init__.py tests/visualization/test_dicom_loader.py
git commit -m "feat: add DICOM loader (T-11)"
```

---

## Task 2: T-12 — NPY Loader

**Files:**
- Create: src/visualization/loaders/npy.py
- Create: tests/visualization/test_npy_loader.py

- [ ] **Step 1: Write the failing test in tests/visualization/test_npy_loader.py**

```python
import numpy as np
import pytest
from pathlib import Path
from visualization.loaders.npy import load_npy

def test_load_npy_basic(tmp_path):
    array = np.zeros((10, 512, 512), dtype=np.int16)
    npy_path = tmp_path / "volume.npy"
    np.save(npy_path, array)
    volume = load_npy(npy_path)
    assert volume.array.shape == (10, 512, 512)

def test_load_npy_rejects_normalized(tmp_path):
    array = np.random.rand(10, 100, 100).astype(np.float32)
    npy_path = tmp_path / "normalized.npy"
    np.save(npy_path, array)
    with pytest.raises(ValueError, match="looks like normalized"):
        load_npy(npy_path)

def test_load_npy_requires_int16_float32(tmp_path):
    array = np.zeros((10, 100, 100), dtype=np.uint8)
    npy_path = tmp_path / "uint8.npy"
    np.save(npy_path, array)
    with pytest.raises(ValueError, match="int16 or float32"):
        load_npy(npy_path)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/visualization/test_npy_loader.py -v
```

Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Implement NPY loader in src/visualization/loaders/npy.py**

```python
HU_AIR_MAX = -500.0   # Real CT air is ~-1000
HU_RANGE_MIN = 300.0  # Plausible range air..bone

def assert_hu(array, source):
    lo, hi = float(array.min()), float(array.max())
    if lo > HU_AIR_MAX or (hi - lo) < HU_RANGE_MIN:
        raise ValueError(f"{source}: Value range [{lo:.1f}, {hi:.1f}] does not look like HU")

def load_npy(path, spacing=None):
    array = np.load(path)
    if array.dtype not in (np.int16, np.float32):
        raise ValueError(f"array must be int16 or float32, got {array.dtype}")
    assert_hu(array, str(path))
    ndim = array.ndim
    if spacing is None:
        spacing = tuple(1.0 for _ in range(ndim))
    return Volume(array=array, spacing=spacing, origin=(0.0,) * ndim)
```

- [ ] **Step 4: Update src/visualization/loaders/__init__.py**

```python
from visualization.loaders.dicom import scan_series, load_dicom_series, SeriesInfo
from visualization.loaders.npy import load_npy
__all__ = ["scan_series", "load_dicom_series", "SeriesInfo", "load_npy"]
```

- [ ] **Step 5: Run test to verify it passes**

```bash
python -m pytest tests/visualization/test_npy_loader.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/visualization/loaders/npy.py src/visualization/loaders/__init__.py tests/visualization/test_npy_loader.py
git commit -m "feat: add NPY loader (T-12)"
```

---

## Summary

| Task | Files | Status |
|------|-------|--------|
| T-11 | dicom.py, test_dicom_loader.py | ✅ COMPLETED |
| T-12 | npy.py, test_npy_loader.py | Pending |

---

## Next Steps (Day 04)

- T-14: Reslicing / MPR
- T-20: Streamlit-App
