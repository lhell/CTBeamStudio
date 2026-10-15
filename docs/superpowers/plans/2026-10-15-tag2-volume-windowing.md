# Tag 2 Implementation Plan — Volume & Windowing

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the core data structures for CT volume handling (T-10) and HU-to-grayscale conversion (T-13), which form the foundation for all subsequent tasks.

**Architecture:** 
- T-10 creates a Volume dataclass that serves as the universal exchange format for all loaders
- T-13 provides windowing functions to convert HU values to 8-bit grayscale for display
- Both are foundational: T-13 depends on T-10, and all later phases depend on these

**Tech Stack:** Python ≥3.11, numpy, pydicom

**Spec:** `docs/plan.md` — T-10 and T-13 specifications

---

## Global Constraints

- Python ≥3.11
- No data in repo/image — only phantom + synthetic fixtures
- Use `pydicom` exclusively — no SimpleITK, no ITK
- Data internally in HU — normalization only for display

---

## Review Focus

| Input/Failure Mode | Expected Behavior |
|---|---|
| `spacing` length ≠ array dimensions | ValueError |
| `spacing` ≤ 0 or NaN/Inf | ValueError |
| `array` not int16/uint16/float32 | ValueError |
| `array` 4D or higher | ValueError |
| `array` with negative values | Allowed (e.g., HU for air = -1000) |
| Window width ≤ 0 | ValueError |
| int16 input with clipping | No overflow, clamp to [0, 255] |
| Window center/width at HU extremes | Exact 0 and 255 at edges |

---

## Task 1: T-10 — Volume Dataclass

**Files:**
- Create: `src/visualization/__init__.py`
- Create: `src/visualization/volume.py`

**Interfaces:**
- Produces: `class Volume` with fields `array`, `spacing`, `origin`, `meta`

- [ ] **Step 1: Create directory structure and __init__.py**

```bash
mkdir -p src/visualization/loaders
touch src/visualization/__init__.py
touch src/visualization/loaders/__init__.py
```

- [ ] **Step 2: Write the failing test in `tests/visualization/test_volume.py`**

```python
import numpy as np
import pytest
from visualization.volume import Volume

def test_volume_creation():
    """3D volume with int16."""
    array = np.zeros((10, 512, 512), dtype=np.int16)
    spacing = (3.0, 0.7, 0.7)
    origin = (0.0, 0.0, 0.0)
    volume = Volume(array=array, spacing=spacing, origin=origin)
    assert volume.array.shape == (10, 512, 512)

def test_volume_uint16_allowed():
    """uint16 for other modalities (MR, PET before SUV)."""
    array = np.zeros((10, 512, 512), dtype=np.uint16)
    volume = Volume(array=array, spacing=(3.0, 0.7, 0.7), origin=(0,0,0))
    assert volume.array.dtype == np.uint16

def test_volume_2d_allowed():
    """2D array for single slices."""
    array = np.zeros((512, 512), dtype=np.int16)
    volume = Volume(array=array, spacing=(0.7, 0.7), origin=(0,0))
    assert volume.array.shape == (512, 512)

def test_volume_4d_rejected():
    """4D arrays (e.g., 4D-CT) are not supported."""
    array = np.zeros((5, 10, 512, 512), dtype=np.int16)
    with pytest.raises(ValueError, match="must be 2D or 3D"):
        Volume(array=array, spacing=(3.0, 0.7, 0.7), origin=(0,0,0))

def test_volume_spacing_nan_rejected():
    """NaN spacing values are invalid."""
    array = np.zeros((10, 512, 512), dtype=np.int16)
    spacing = (3.0, np.nan, 0.7)
    with pytest.raises(ValueError, match="spacing values must be finite"):
        Volume(array=array, spacing=spacing, origin=(0,0,0))

def test_volume_spacing_inf_rejected():
    """Inf spacing values are invalid."""
    array = np.zeros((10, 512, 512), dtype=np.int16)
    spacing = (3.0, np.inf, 0.7)
    with pytest.raises(ValueError, match="spacing values must be finite"):
        Volume(array=array, spacing=spacing, origin=(0,0,0))

def test_volume_invalid_spacing_length():
    """Spacing must match array dimensions."""
    array = np.zeros((10, 512, 512), dtype=np.int16)
    spacing = (3.0, 0.7)  # Only 2 values for 3D array
    with pytest.raises(ValueError, match="spacing length must match array dimensions"):
        Volume(array=array, spacing=spacing, origin=(0,0,0))

def test_volume_invalid_spacing_value():
    """Zero or negative spacing is invalid."""
    array = np.zeros((10, 512, 512), dtype=np.int16)
    spacing = (3.0, 0.0, 0.7)  # Zero spacing
    with pytest.raises(ValueError, match="spacing values must be positive"):
        Volume(array=array, spacing=spacing, origin=(0,0,0))

def test_volume_invalid_array_dtype():
    """Only int16, uint16, float32 allowed."""
    array = np.zeros((10, 512, 512), dtype=np.float64)
    with pytest.raises(ValueError, match="array must be int16, uint16, or float32"):
        Volume(array=array, spacing=(3.0, 0.7, 0.7), origin=(0,0,0))

def test_volume_negative_allowed():
    """Negative values are allowed (e.g., HU for air = -1000)."""
    array = np.array([[-1000, 0, 1000]], dtype=np.int16)  # HU values
    volume = Volume(array=array, spacing=(0.7, 0.7), origin=(0,0))
    assert volume.array.min() == -1000
    assert volume.array.max() == 1000

- [ ] **Step 3: Run test to verify it fails**

```bash
cd \\file.imt.uni-luebeck.de\UserData\hellwege\00_Git\CTOrientationViewer
python -m pytest tests/visualization/test_volume.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'visualization'"

- [ ] **Step 4: Implement Volume dataclass in `src/visualization/volume.py`**

```python
"""Volume dataclass for CT data exchange."""

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class Volume:
    """Container for CT volume data in HU or attenuation values.
    
    Supports:
    - 2D (single slice): (y, x)
    - 3D (volume): (z, y, x)
    
    Attributes:
        array: 2D or 3D numpy array with attenuation values (HU or linear).
        spacing: Pixel spacing in mm. Must match array dimensions:
            - 2D: (row_spacing, col_spacing)
            - 3D: (z_spacing, row_spacing, col_spacing)
        origin: DICOM origin coordinates (x, y, z) or (x, y) for 2D.
        meta: Optional metadata dictionary.
    """
    array: np.ndarray
    spacing: tuple[float, ...]
    origin: tuple[float, ...]
    meta: Optional[dict] = None
    
    def __post_init__(self) -> None:
        """Validate volume after initialization."""
        ndim = self.array.ndim
        
        # Validate array dimensions (2D or 3D only)
        if ndim not in (2, 3):
            raise ValueError(f"array must be 2D or 3D, got {ndim}D")
        
        # Validate array dtype (CT attenuation values)
        allowed_dtypes = (np.int16, np.uint16, np.float32)
        if self.array.dtype not in allowed_dtypes:
            raise ValueError(
                f"array must be int16, uint16, or float32, got {self.array.dtype}"
            )
        
        # Note: Volume stores the unit in meta["unit"].
        # Valid units: "HU" (Hounsfield), "1/mm" (attenuation per mm), "1/cm" (attenuation per cm).
        # Loaders are responsible for correct unit conversion and validation.
        
        # Validate spacing matches array dimensions
        if len(self.spacing) != ndim:
            raise ValueError(
                f"spacing length ({len(self.spacing)}) must match array "
                f"dimensions ({ndim})"
            )
        
        # Validate spacing values are positive and finite
        for i, s in enumerate(self.spacing):
            if s <= 0:
                raise ValueError(f"spacing[{i}] must be positive, got {s}")
            if not np.isfinite(s):
                raise ValueError(f"spacing[{i}] must be finite, got {s}")
        
        # Validate origin matches array dimensions
        if len(self.origin) != ndim:
            raise ValueError(
                f"origin length ({len(self.origin)}) must match array "
                f"dimensions ({ndim})"
            )
    
    @property
    def shape(self) -> tuple[int, ...]:
        """Return array shape."""
        return tuple(self.array.shape)
    
    @property
    def ndim(self) -> int:
        """Return number of dimensions."""
        return self.array.ndim
    
    @property
    def n_slices(self) -> int:
        """Return number of axial slices (3D only)."""
        if self.array.ndim == 2:
            return 1
        return self.array.shape[0]
```

- [ ] **Step 5: Run test to verify it passes**

```bash
python -m pytest tests/visualization/test_volume.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/visualization/volume.py src/visualization/__init__.py tests/visualization/test_volume.py
git commit -m "feat: add Volume dataclass (T-10)"
```

---

## Task 2: T-13 — Windowing

**Files:**
- Create: `src/visualization/windowing.py`
- Modify: `src/visualization/__init__.py`
- Create: `tests/visualization/test_windowing.py`

**Interfaces:**
- Consumes: `Volume` from T-10
- Produces: `apply_window(array, center, width) -> np.ndarray`, window presets dict

- [ ] **Step 1: Write the failing test in `tests/visualization/test_windowing.py`**

```python
import numpy as np
import pytest
from visualization.windowing import apply_window, apply_window_with_preset, WINDOW_PRESETS

def test_apply_window_basic():
    # HU values from -1000 (air) to 1000 (bone)
    array = np.array([[[-1000, 0, 1000]]], dtype=np.int16)
    
    # Window: center=0, width=2000 -> range [-1000, 1000]
    result = apply_window(array, center=0, width=2000)
    
    assert result.dtype == np.uint8
    assert result[0, 0, 0] == 0   # -1000 -> 0
    assert result[0, 0, 1] == 128 # 0 -> 128
    assert result[0, 0, 2] == 255 # 1000 -> 255

def test_apply_window_presets():
    assert "lung" in WINDOW_PRESETS
    assert "abdomen" in WINDOW_PRESETS
    assert "bone" in WINDOW_PRESETS
    assert "brain" in WINDOW_PRESETS
    
    # Lung preset: (-600, 1500)
    assert WINDOW_PRESETS["lung"] == (-600, 1500)

def test_apply_window_with_preset_by_name():
    """Can use preset name string."""
    array = np.array([[-1000, 0, 500]], dtype=np.int16)
    result = apply_window_with_preset(array, "lung")
    assert result.dtype == np.uint8

def test_apply_window_with_preset_by_tuple():
    """Can use (center, width) tuple."""
    array = np.array([[-1000, 0, 500]], dtype=np.int16)
    result = apply_window_with_preset(array, (0, 2000))
    assert result.dtype == np.uint8

def test_apply_window_with_preset_invalid_name():
    """Invalid preset name raises KeyError."""
    array = np.zeros((10, 10), dtype=np.int16)
    with pytest.raises(KeyError, match="invalid_preset"):
        apply_window_with_preset(array, "invalid_preset")

def test_apply_window_invalid_width():
    array = np.zeros((10, 10), dtype=np.int16)
    with pytest.raises(ValueError, match="width must be positive"):
        apply_window(array, center=0, width=0)

def test_apply_window_int16_no_overflow():
    # Test that int16 values don't overflow during computation
    array = np.array([[-2000]], dtype=np.int16)  # Very low HU
    result = apply_window(array, center=0, width=2000)
    assert result[0, 0] == 0  # Clamped to 0
    
    array = np.array([[2000]], dtype=np.int16)  # Very high HU
    result = apply_window(array, center=0, width=2000)
    assert result[0, 0] == 255  # Clamped to 255
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/visualization/test_windowing.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'visualization.windowing'"

- [ ] **Step 3: Implement windowing in `src/visualization/windowing.py`**

```python
"""Windowing functions for HU to 8-bit grayscale conversion."""

from typing import Union

import numpy as np


# Window presets: (center, width)
WINDOW_PRESETS: dict[str, tuple[float, float]] = {
    "lung": (-600, 1500),
    "abdomen": (40, 400),
    "bone": (400, 1800),
    "brain": (40, 80),
}


def apply_window(array: np.ndarray, center: float, width: float) -> np.ndarray:
    """Apply windowing to convert HU values to 8-bit grayscale.
    
    Args:
        array: Input array in HU (int16 or float32).
        center: Window center (level) in HU.
        width: Window width in HU.
    
    Returns:
        uint8 array with values in [0, 255].
    
    Raises:
        ValueError: If width <= 0.
    """
    if width <= 0:
        raise ValueError("width must be positive")
    
    # Convert to float for calculation (avoid overflow with int16)
    array_float = array.astype(np.float64)
    
    # Calculate window boundaries
    window_min = center - width / 2
    window_max = center + width / 2
    
    # Apply windowing: map [window_min, window_max] to [0, 255]
    result = (array_float - window_min) / (window_max - window_min) * 255
    
    # Clip to [0, 255] and convert to uint8
    result = np.clip(result, 0, 255).astype(np.uint8)
    
    return result


def apply_window_with_preset(
    array: np.ndarray,
    window: Union[str, tuple[float, float]]
) -> np.ndarray:
    """Apply windowing with preset name or (center, width) tuple.
    
    Args:
        array: Input array in HU.
        window: Preset name (e.g., "lung") or (center, width) tuple.
    
    Returns:
        uint8 array with values in [0, 255].
    
    Raises:
        KeyError: If preset name not found.
        ValueError: If width <= 0.
    """
    if isinstance(window, str):
        center, width = WINDOW_PRESETS[window]
    else:
        center, width = window
    
    return apply_window(array, center, width)
```

- [ ] **Step 4: Update `src/visualization/__init__.py`**

```python
"""CT Orientation Viewer — Visualization Module."""

from visualization.volume import Volume
from visualization.windowing import apply_window, apply_window_with_preset, WINDOW_PRESETS

__all__ = ["Volume", "apply_window", "apply_window_with_preset", "WINDOW_PRESETS"]
```

- [ ] **Step 5: Run test to verify it passes**

```bash
python -m pytest tests/visualization/test_windowing.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/visualization/windowing.py src/visualization/__init__.py tests/visualization/test_windowing.py
git commit -m "feat: add windowing module (T-13)"
```

---

## Summary

| Task | Files Created/Modified | Status |
|------|------------------------|--------|
| T-10 | `src/visualization/volume.py`, `src/visualization/__init__.py`, `tests/visualization/test_volume.py` | Pending |
| T-13 | `src/visualization/windowing.py`, `src/visualization/__init__.py` (update), `tests/visualization/test_windowing.py` | Pending |

---

## Next Steps (Day 03)

- T-11: DICOM-Loader
- T-12: NPY-Loader
