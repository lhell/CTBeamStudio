# T-14 MPR / Reslicing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Multi-Planar Reconstruction (MPR) to extract axial, coronal, and sagittal slices from a 3D CT volume with correct aspect ratios for anisotropic spacing.

**Architecture:** Pure numpy implementation. Extract orthogonal slices from 3D Volume array. Return slice data plus in-plane spacing for correct aspect ratio calculation in the UI.

**Tech Stack:** Python, numpy

**Spec:** This plan implements the T-14 requirements from `docs/plan.md`:
- `extract_slice(volume, plane, index)` returns image **and** in-plane spacing
- Aspect ratio from spacing, not pixel count
- Test case: Volume with spacing `(3.0, 0.7, 0.7)` → coronal slice aspect ratio ≈ 4.29

---

## Global Constraints

- Volume class from `src/visualization/volume.py` defines the interface
- Array must be 3D (volume) to extract slices
- Spacing is tuple of floats `(z, y, x)` for 3D volumes

---

## Review Focus

1. **2D volume input** — User passes a 2D Volume (single slice). Should raise a clear error.
2. **Index out of bounds** — Negative index or index >= dimension size should raise IndexError.
3. **Invalid plane name** — Non-standard plane string should raise ValueError with allowed values.
4. **Return type correctness** — Must return tuple of (np.ndarray, tuple), not just array.
5. **Aspect ratio precision** — Test case requires ≈4.29, need to verify float precision.

---

## Task 1: Create MPR Module and Tests

**Files:**
- Create: `src/visualization/mpr.py`
- Create: `tests/visualization/test_mpr.py`

**Interfaces:**
- Consumes: `Volume` from `src/visualization/volume.py`
- Produces: `extract_slice(volume: Volume, plane: str, index: int) -> tuple[np.ndarray, tuple[float, float]]`

---

- [ ] **Step 1: Write the failing test**

Create `tests/visualization/test_mpr.py`:

```python
import numpy as np
import pytest
from visualization.volume import Volume
from visualization.mpr import extract_slice


class TestExtractSlice:
    """Test MPR slice extraction."""

    @pytest.fixture
    def sample_volume(self):
        """Create a sample 3D volume with anisotropic spacing."""
        # Shape: (10, 7, 7) — 10 slices, 7x7 pixels
        # Spacing: (3.0, 0.7, 0.7) — anisotropic (z=3.0mm, y=x=0.7mm)
        array = np.arange(490).reshape(10, 7, 7).astype(np.int16)
        volume = Volume(
            array=array,
            spacing=(3.0, 0.7, 0.7),
            origin=(0.0, 0.0, 0.0)
        )
        return volume

    def test_axial_slice(self, sample_volume):
        """Extract axial slice at index 5."""
        slice_img, in_plane_spacing = extract_slice(sample_volume, "axial", 5)
        
        assert slice_img.shape == (7, 7)
        assert in_plane_spacing == (0.7, 0.7)

    def test_coronal_slice(self, sample_volume):
        """Extract coronal slice — should have aspect ratio ~4.29."""
        slice_img, in_plane_spacing = extract_slice(sample_volume, "coronal", 3)
        
        # Coronal: fix y, vary x and z
        # Shape: (10, 7) — z slices, x pixels
        assert slice_img.shape == (10, 7)
        # In-plane spacing: (z_spacing, x_spacing) = (3.0, 0.7)
        assert in_plane_spacing == (3.0, 0.7)
        
        # Aspect ratio = 3.0 / 0.7 ≈ 4.2857...
        aspect_ratio = in_plane_spacing[0] / in_plane_spacing[1]
        assert abs(aspect_ratio - 4.2857) < 0.01

    def test_sagittal_slice(self, sample_volume):
        """Extract sagittal slice."""
        slice_img, in_plane_spacing = extract_slice(sample_volume, "sagittal", 3)
        
        # Sagittal: fix x, vary y and z
        # Shape: (10, 7) — z slices, y pixels
        assert slice_img.shape == (10, 7)
        # In-plane spacing: (z_spacing, y_spacing) = (3.0, 0.7)
        assert in_plane_spacing == (3.0, 0.7)

    def test_invalid_plane_raises(self, sample_volume):
        """Invalid plane name should raise ValueError."""
        with pytest.raises(ValueError, match="plane must be"):
            extract_slice(sample_volume, "diagonal", 0)

    def test_index_out_of_bounds_raises(self, sample_volume):
        """Index out of bounds should raise IndexError."""
        with pytest.raises(IndexError):
            extract_slice(sample_volume, "axial", 100)
        with pytest.raises(IndexError):
            extract_slice(sample_volume, "axial", -1)

    def test_2d_volume_raises(self):
        """2D volume should raise ValueError."""
        array = np.zeros((10, 10), dtype=np.int16)
        volume = Volume(array=array, spacing=(1.0, 1.0), origin=(0.0, 0.0))
        
        with pytest.raises(ValueError, match="3D"):
            extract_slice(volume, "axial", 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/visualization/test_mpr.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'visualization.mpr'"

- [ ] **Step 3: Implement `extract_slice` in `src/visualization/mpr.py`**

```python
"""MPR (Multi-Planar Reconstruction) for CT volumes."""

import numpy as np
from typing import Tuple

from visualization.volume import Volume


def extract_slice(volume: Volume, plane: str, index: int) -> Tuple[np.ndarray, Tuple[float, float]]:
    """Extract an orthogonal slice from a 3D volume.

    Args:
        volume: 3D Volume object containing CT data.
        plane: Plane orientation — "axial", "coronal", or "sagittal".
        index: Slice index along the selected plane.

    Returns:
        A tuple of (slice_array, in_plane_spacing):
        - slice_array: 2D numpy array representing the slice.
        - in_plane_spacing: Tuple of (row_spacing, col_spacing) in mm
          for correct aspect ratio in the UI.

    Raises:
        ValueError: If plane is not valid or volume is not 3D.
        IndexError: If index is out of bounds.
    """
    # Validate volume is 3D
    if volume.array.ndim != 3:
        raise ValueError(f"Volume must be 3D for MPR, got {volume.array.ndim}D")

    # Normalize plane name
    plane = plane.lower().strip()
    
    # Extract slice and determine in-plane spacing based on plane orientation
    if plane == "axial":
        # Axial: slice along z-axis (head-to-feet)
        # Output shape: (rows, cols) = (y, x)
        # Spacing: (y_spacing, x_spacing)
        slice_array = volume.array[index, :, :]
        in_plane_spacing = (volume.spacing[1], volume.spacing[2])
        
    elif plane == "coronal":
        # Coronal: slice along y-axis (front-to-back)
        # Output shape: (rows, cols) = (z, x)
        # Spacing: (z_spacing, x_spacing)
        slice_array = volume.array[:, index, :]
        in_plane_spacing = (volume.spacing[0], volume.spacing[2])
        
    elif plane == "sagittal":
        # Sagittal: slice along x-axis (left-to-right)
        # Output shape: (rows, cols) = (z, y)
        # Spacing: (z_spacing, y_spacing)
        slice_array = volume.array[:, :, index]
        in_plane_spacing = (volume.spacing[0], volume.spacing[1])
        
    else:
        raise ValueError(f"plane must be 'axial', 'coronal', or 'sagittal', got '{plane}'")

    # Validate index bounds
    max_index = slice_array.shape[0] - 1
    if index < 0 or index > max_index:
        raise IndexError(f"index {index} out of bounds for dimension size {slice_array.shape[0]}")

    return slice_array, in_plane_spacing
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/visualization/test_mpr.py -v`
Expected: PASS (all 7 tests)

- [ ] **Step 5: Commit**

```bash
git add src/visualization/mpr.py tests/visualization/test_mpr.py
git commit -m "feat: add MPR slice extraction (T-14)"
```

---

## Summary

| Task | Files | Status |
|------|-------|--------|
| T-14 | `src/visualization/mpr.py`, `tests/visualization/test_mpr.py` | Ready to implement |

---

**Plan complete.** Please review and let me know which execution approach you prefer:

- **Subagent-driven** — Fresh subagent implements, fresh reviewer checks each task
- **Native** — I implement everything, one review at the end

Which would you like?
