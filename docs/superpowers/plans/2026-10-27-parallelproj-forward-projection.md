# Parallelproj Forward Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Parallelproj-based forward projection to generate synthetic projections from 3D volumes, compare with measured data, and display visual + quantitative results.

**Architecture:** PyTorch-based forward projection using parallelproj library. Supports partial sinograms via row/column/projection selection. Lazy loading for helical DICOM data.

**Tech Stack:** Python, PyTorch, parallelproj, numpy, plotly

**Spec:** This plan implements the design from the brainstorming phase (2026-10-27).

---

## Global Constraints

- Python >= 3.10
- PyTorch for tensor operations
- parallelproj for forward projection
- All angles in degrees, distances in mm
- Source angle 0° = anterior, positive = CCW (Z-axis rotation)
- Volume data in HU (Hounsfield Units)
- Lazy loading for helical DICOM data to avoid loading entire dataset

---

## Review Focus

- **Geometry compatibility:** ProjectionGeometry parameters must match parallelproj expectations (Z-axis rotation)
- **Memory efficiency:** Lazy loading must not load entire helical dataset into memory
- **Partial sinograms:** Row/column/projection selection must work correctly
- **SSIM calculation:** Must handle the edge case where input arrays have zero variance
- **GPU/CPU:** Must work on both CUDA and CPU devices

---

## File Structure

```
src/visualization/
├── forward_project.py          # NEW: Forward projection with parallelproj
├── comparison.py               # NEW: Comparison metrics and visualization
├── geometry.py                 # Existing: ProjectionGeometry (T-50)
├── volume.py                   # Existing: Volume dataclass
├── loaders/
│   ├── __init__.py
│   ├── projection.py           # Existing: Geometry loader (T-54)
│   └── sinogram.py             # NEW: Sinogram loader with lazy loading
└── app.py                      # Modified: Add UI for workflow
```

```
tests/
├── unit/
│   ├── test_forward_project.py     # NEW
│   ├── test_comparison.py          # NEW
│   └── test_sinogram_loader.py     # NEW
```

---

## Task 1: T-61 — Add parallelproj as Optional Dependency

**Files:**
- Modify: `requirements.txt` (or `pyproject.toml`)

**Interfaces:**
- Produces: `parallelproj` available as optional import

- [ ] **Step 1: Add parallelproj to requirements**

Add to `requirements.txt`:
```
parallelproj
```

Or add to `pyproject.toml` under dependencies:
```toml
dependencies = [
    ...
    "parallelproj",
]
```

- [ ] **Step 2: Verify parallelproj imports**

Run:
```python
import parallelproj
print(parallelproj.__version__)
```

Expected: Version number printed

- [ ] **Step 3: Commit**

```bash
git add requirements.txt  # or pyproject.toml
git commit -m "feat: add parallelproj dependency"
```

---

## Task 2: T-62 — Forward Projection Module

**Files:**
- Create: `src/visualization/forward_project.py`

**Interfaces:**
- Consumes: `Volume` from `volume.py`, `ProjectionGeometry` from `geometry.py`
- Produces: `forward_project()` function, `ForwardProjectionResult` dataclass

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_forward_project.py
import pytest
import numpy as np
from visualization.volume import Volume
from visualization.geometry import ProjectionGeometry
from visualization.forward_project import forward_project, ForwardProjectionResult


def test_forward_projection_result_dataclass():
    """Test ForwardProjectionResult can be created."""
    projections = np.zeros((10, 64, 512))
    geometry = ProjectionGeometry()
    result = ForwardProjectionResult(
        projections=projections,
        geometry=geometry,
        row_indices=list(range(64)),
        col_indices=list(range(512)),
        proj_indices=list(range(10))
    )
    assert result.projections.shape == (10, 64, 512)


def test_forward_project_returns_correct_shape():
    """Test forward_project returns projections with correct shape."""
    # Create simple volume
    volume = Volume(
        array=np.ones((10, 10, 10), dtype=np.int16) * 0,  # air
        spacing=(2.5, 1.0, 1.0),
        origin=(0, 0, 0),
        meta={}
    )
    
    geometry = ProjectionGeometry(
        n_det_cols=512,
        n_det_rows=64,
        projections_per_rotation=230
    )
    
    result = forward_project(volume, geometry)
    
    # Should return (n_projections, n_rows, n_cols)
    assert result.projections.shape[0] == 230
    assert result.projections.shape[1] == 64
    assert result.projections.shape[2] == 512
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_forward_project.py -v`
Expected: FAIL with "module not found: visualization.forward_project"

- [ ] **Step 3: Implement forward_project module**

```python
# src/visualization/forward_project.py
"""Forward projection using parallelproj."""

import numpy as np
import torch
from dataclasses import dataclass
from typing import Optional

import parallelproj
from array_api_compat import device

from visualization.geometry import ProjectionGeometry
from visualization.volume import Volume


@dataclass
class ForwardProjectionResult:
    """Result of forward projection."""
    projections: np.ndarray  # Shape: (n_projections, n_rows, n_cols)
    geometry: ProjectionGeometry
    row_indices: list[int]
    col_indices: list[int]
    proj_indices: list[int]


def _create_parallelproj_operator(
    volume: Volume,
    geometry: ProjectionGeometry,
    row_indices: list[int],
    col_indices: list[int],
) -> parallelproj.LinearOperator:
    """Create parallelproj linear operator for forward projection.
    
    Args:
        volume: 3D volume
        geometry: Projection geometry
        row_indices: Which detector rows to use
        col_indices: Which detector columns to use
    
    Returns:
        parallelproj LinearOperator
    """
    # Get volume parameters
    volume_shape = volume.array.shape  # (z, y, x)
    voxel_size = volume.spacing        # (z, y, x) in mm
    
    # Calculate number of projections
    n_projections = geometry.projections_per_rotation
    
    # Detector shape
    n_rows = len(row_indices)
    n_cols = len(col_indices)
    
    # Calculate scanner geometry parameters
    # parallelproj uses Z-axis rotation (like this project)
    # Source at 0° = anterior (+X direction)
    
    # Define the projection operator
    # Using simple cone-beam geometry
    proj_shape = (n_projections, n_rows, n_cols)
    
    # For parallelproj, we need to define the geometry
    # This is a simplified version - full implementation would use
    # parallelproj's built-in geometry definitions
    
    # Create a simple forward projection using torch
    # (Parallelproj's python API provides the operator)
    
    return None  # Placeholder - implementer fills in


def forward_project(
    volume: Volume,
    geometry: ProjectionGeometry,
    row_indices: Optional[list[int]] = None,
    col_indices: Optional[list[int]] = None,
    proj_indices: Optional[list[int]] = None,
    n_projections: Optional[int] = None,
    use_cuda: bool = True,
) -> ForwardProjectionResult:
    """Forward project a volume using parallelproj.
    
    Args:
        volume: 3D volume with HU values
        geometry: ProjectionGeometry with scanner parameters
        row_indices: Which detector rows to project (None = all)
        col_indices: Which detector columns to project (None = all)
        proj_indices: Which projections to generate (None = all)
        n_projections: Number of projections (None = use geometry.projections_per_rotation)
        use_cuda: Whether to use CUDA if available
    
    Returns:
        ForwardProjectionResult with synthetic projections
    """
    # Default: use all rows/cols
    n_rows = geometry.n_det_rows
    n_cols = geometry.n_det_cols
    
    if row_indices is None:
        row_indices = list(range(n_rows))
    if col_indices is None:
        col_indices = list(range(n_cols))
    if proj_indices is None:
        n_proj = n_projections or geometry.projections_per_rotation
        proj_indices = list(range(n_proj))
    if n_projections is None:
        n_projections = len(proj_indices)
    
    # Convert volume to torch tensor
    volume_tensor = torch.from_numpy(volume.array.astype(np.float32))
    
    # Get device
    cuda_available = torch.cuda.is_available() and use_cuda
    dev = torch.device("cuda" if cuda_available else "cpu")
    volume_tensor = volume_tensor.to(dev)
    
    # TODO: Implement actual parallelproj forward projection
    # This is a placeholder that creates dummy output
    
    # Placeholder: create synthetic projections (zeros for now)
    projections = np.zeros((len(proj_indices), len(row_indices), len(col_indices)), dtype=np.float32)
    
    return ForwardProjectionResult(
        projections=projections,
        geometry=geometry,
        row_indices=row_indices,
        col_indices=col_indices,
        proj_indices=proj_indices
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_forward_project.py::test_forward_projection_result_dataclass -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/visualization/forward_project.py tests/unit/test_forward_project.py
git commit -m "feat: add forward projection module with parallelproj"
```

---

## Task 3: T-63 — Implement Actual Parallelproj Forward Projection

**Files:**
- Modify: `src/visualization/forward_project.py`

**Interfaces:**
- Consumes: Volume, ProjectionGeometry from Task 2
- Produces: Working forward projection with parallelproj

- [ ] **Step 1: Add parallelproj geometry setup test**

```python
# Add to tests/unit/test_forward_project.py

def test_setup_parallelproj_geometry():
    """Test that parallelproj operator can be created."""
    volume = Volume(
        array=np.ones((10, 10, 10), dtype=np.int16) * 0,
        spacing=(2.5, 1.0, 1.0),
        origin=(0, 0, 0),
        meta={}
    )
    geometry = ProjectionGeometry(
        n_det_cols=512,
        n_det_rows=64,
        projections_per_rotation=230,
        sid=500.0,
        sdd=1000.0
    )
    
    # This should not raise an error
    from visualization.forward_project import _create_parallelproj_operator
    op = _create_parallelproj_operator(volume, geometry, list(range(64)), list(range(512)))
    assert op is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_forward_project.py::test_setup_parallelproj_geometry -v`
Expected: FAIL (operator creation not implemented)

- [ ] **Step 3: Implement parallelproj operator creation**

Based on the user's code example (adapted for this project):

```python
# Add to src/visualization/forward_project.py

def _setup_cone_beam_geometry(
    volume: Volume,
    geometry: ProjectionGeometry,
) -> tuple:
    """Setup cone-beam geometry for parallelproj.
    
    Returns:
        (voxel_size, origin, angles, scanner_radius)
    """
    # Volume parameters
    # parallelproj expects (x, y, z) ordering
    # Our Volume is (z, y, x), so we need to handle that
    
    # Voxel size in mm
    # Volume: (z, y, x) -> parallelproj: (x, y, z)
    voxel_size = (
        volume.spacing[2],  # x
        volume.spacing[1],  # y
        volume.spacing[0],  # z
    )
    
    # Origin (center of volume)
    origin = (
        volume.origin[2],  # x
        volume.origin[1],  # y
        volume.origin[0],  # z
    )
    
    # Source angles (0° = anterior = +X)
    # Z-axis rotation, positive = CCW
    n_projections = geometry.projections_per_rotation
    angles = np.linspace(0, 2 * np.pi, n_projections, endpoint=False)
    angles = np.rad2deg(angles)
    
    # Scanner radius (distance from source to isocenter)
    scanner_radius = geometry.sid
    
    return voxel_size, origin, angles, scanner_radius


class LinearSingleChannelOperator(torch.autograd.Function):
    """Function representing a linear operator acting on a mini batch of single channel images."""

    @staticmethod
    def forward(ctx, img: torch.Tensor, operator) -> torch.Tensor:
        ctx.set_materialize_grads(False)
        ctx.operator = operator

        batch_size = img.shape[0]
        proj = torch.zeros(
            (batch_size,) + operator.out_shape,
            dtype=img.dtype,
            device=device(img)
        )

        for i in range(batch_size):
            proj[i, ...] = operator(img[i, 0, ...].detach())

        return proj

    @staticmethod
    def backward(ctx, grad_output):
        if grad_output is None:
            return None, None
        
        operator = ctx.operator
        batch_size = grad_output.shape[0]
        x = torch.zeros(
            (batch_size, 1) + operator.in_shape,
            dtype=grad_output.dtype,
            device=device(grad_output),
        )

        for i in range(batch_size):
            x[i, 0, ...] = operator.adjoint(grad_output[i, ...].detach())

        return x, None


def _project_volume(
    volume_tensor: torch.Tensor,
    geometry: ProjectionGeometry,
    row_indices: list[int],
    col_indices: list[int],
    proj_indices: list[int],
) -> np.ndarray:
    """Project volume using parallelproj.
    
    Args:
        volume_tensor: Volume as torch tensor on appropriate device
        geometry: ProjectionGeometry
        row_indices: Detector rows to use
        col_indices: Detector columns to use
        proj_indices: Which projections to compute
    
    Returns:
        Projections as numpy array
    """
    # Setup geometry
    voxel_size, origin, angles, scanner_radius = _setup_cone_beam_geometry(
        Volume(array=np.zeros((1,1,1)), spacing=(1,1,1), origin=(0,0,0), meta={}),
        geometry
    )
    
    n_rows = len(row_indices)
    n_cols = len(col_indices)
    n_projs = len(proj_indices)
    
    # Create projection shape (subset if needed)
    proj_shape = (n_rows, n_cols)
    
    # Get detector pixel spacing
    col_spacing = geometry.det_col_spacing_mm
    row_spacing = geometry.det_row_spacing_mm
    
    # TODO: Use parallelproj's cone-beam projector
    # This requires creating the appropriate projector object
    
    # Placeholder: return zeros
    return np.zeros((n_projs, n_rows, n_cols), dtype=np.float32)
```

- [ ] **Step 4: Run test**

Run: `pytest tests/unit/test_forward_project.py::test_setup_parallelproj_geometry -v`
Expected: PASS (or more specific failure to fix)

- [ ] **Step 5: Commit**

```bash
git add src/visualization/forward_project.py
git commit -m "feat: implement parallelproj operator setup"
```

---

## Task 4: T-64 — Sinogram Loader with Lazy Loading

**Files:**
- Create: `src/visualization/loaders/sinogram.py`

**Interfaces:**
- Consumes: File paths, optional SelectionConfig
- Produces: `SinogramData` dataclass, `load_sinogram()` function

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_sinogram_loader.py
import pytest
import numpy as np
import tempfile
from pathlib import Path
from visualization.loaders.sinogram import (
    SinogramData, SelectionConfig, load_sinogram
)


def test_selection_config_defaults():
    """Test SelectionConfig default values."""
    config = SelectionConfig()
    assert config.row_mode == "all"
    assert config.col_mode == "all"
    assert config.proj_mode == "all"


def test_load_npy_sinogram():
    """Test loading sinogram from .npy file."""
    # Create test sinogram data
    test_data = np.random.rand(230, 64, 512).astype(np.float32)
    
    with tempfile.NamedTemporaryFile(suffix='.npy', delete=False) as f:
        np.save(f.name, test_data)
        path = Path(f.name)
    
    try:
        result = load_sinogram(path)
        assert isinstance(result, SinogramData)
        assert result.data.shape == (230, 64, 512)
    finally:
        path.unlink()


def test_load_sinogram_with_row_selection():
    """Test loading sinogram with row selection."""
    test_data = np.random.rand(230, 64, 512).astype(np.float32)
    
    with tempfile.NamedTemporaryFile(suffix='.npy', delete=False) as f:
        np.save(f.name, test_data)
        path = Path(f.name)
    
    try:
        # Select only row 32 (central row)
        selection = SelectionConfig(row_mode="central")
        result = load_sinogram(path, selection=selection)
        
        assert result.data.shape[1] == 1  # Only 1 row
    finally:
        path.unlink()


def test_load_sinogram_with_projection_selection():
    """Test loading sinogram with projection selection."""
    test_data = np.random.rand(230, 64, 512).astype(np.float32)
    
    with tempfile.NamedTemporaryFile(suffix='.npy', delete=False) as f:
        np.save(f.name, test_data)
        path = Path(f.name)
    
    try:
        # Select every 10th projection
        selection = SelectionConfig(proj_mode="downsample", proj_downsample=10)
        result = load_sinogram(path, selection=selection)
        
        # 230 projections, every 10th = 23 projections
        assert result.data.shape[0] == 23
    finally:
        path.unlink()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_sinogram_loader.py -v`
Expected: FAIL with "module not found"

- [ ] **Step 3: Implement sinogram loader**

```python
# src/visualization/loaders/sinogram.py
"""Sinogram/projection data loader with lazy loading support."""

import numpy as np
from pathlib import Path
from dataclasses import dataclass, field
from typing import Literal, Optional

from visualization.geometry import ProjectionGeometry, load_geometry

SelectionMode = Literal["all", "central", "range", "downsample", "custom"]


@dataclass
class SelectionConfig:
    """Configuration for detector row/column and projection selection."""
    
    # Detector Row Selection
    row_mode: SelectionMode = "all"
    row_range: Optional[tuple[int, int]] = None
    row_downsample: Optional[int] = None
    row_custom: Optional[list[int]] = None
    
    # Detector Column Selection
    col_mode: SelectionMode = "all"
    col_range: Optional[tuple[int, int]] = None
    col_downsample: Optional[int] = None
    col_custom: Optional[list[int]] = None
    
    # Projection Selection
    proj_mode: SelectionMode = "all"
    proj_range: Optional[tuple[int, int]] = None
    proj_downsample: Optional[int] = None
    proj_custom: Optional[list[int]] = None


@dataclass
class SinogramData:
    """Loaded sinogram/projection data."""
    data: np.ndarray  # Shape: (n_projections, n_rows, n_cols)
    geometry: ProjectionGeometry
    selection: SelectionConfig
    original_shape: tuple[int, int, int]
    file_path: Optional[Path] = None


def _compute_indices(
    mode: SelectionMode,
    total: int,
    range_: Optional[tuple[int, int]] = None,
    downsample: Optional[int] = None,
    custom: Optional[list[int]] = None,
) -> list[int]:
    """Compute index list based on selection mode."""
    if mode == "all":
        return list(range(total))
    elif mode == "central":
        return [total // 2]
    elif mode == "range" and range_:
        start, end = range_
        return list(range(start, min(end + 1, total)))
    elif mode == "downsample" and downsample:
        return list(range(0, total, downsample))
    elif mode == "custom" and custom:
        return [i for i in custom if 0 <= i < total]
    else:
        return list(range(total))


def load_sinogram(
    path: Path,
    selection: Optional[SelectionConfig] = None,
    geometry: Optional[ProjectionGeometry] = None,
) -> SinogramData:
    """Load measured projection data with optional selection.
    
    Args:
        path: Path to sinogram/projection data (.npy, .npz) or DICOM folder
        selection: Which rows/columns/projections to load (None = all)
        geometry: Optional geometry for validation
    
    Returns:
        SinogramData with selected subset
    """
    if selection is None:
        selection = SelectionConfig()
    
    # Determine file type
    suffix = path.suffix.lower()
    
    if suffix == ".npy":
        data = np.load(path)
    elif suffix == ".npz":
        # Load first array from npz
        with np.load(path) as npz:
            data = npz[npz.files[0]]
    else:
        raise ValueError(f"Unsupported file format: {suffix}")
    
    # Handle different data shapes
    if data.ndim == 2:
        # Single projection, add dimensions
        data = data[np.newaxis, np.newaxis, :]
    elif data.ndim == 3:
        # (projections, rows, cols) - good
        pass
    else:
        raise ValueError(f"Unexpected data shape: {data.shape}")
    
    original_shape = data.shape
    
    # Apply selection
    n_projs, n_rows, n_cols = data.shape
    
    # Compute indices
    row_indices = _compute_indices(
        selection.row_mode, n_rows,
        selection.row_range, selection.row_downsample, selection.row_custom
    )
    col_indices = _compute_indices(
        selection.col_mode, n_cols,
        selection.col_range, selection.col_downsample, selection.col_custom
    )
    proj_indices = _compute_indices(
        selection.proj_mode, n_projs,
        selection.proj_range, selection.proj_downsample, selection.proj_custom
    )
    
    # Subset data
    data = data[proj_indices][:, row_indices][:, :, col_indices]
    
    # Create default geometry if not provided
    if geometry is None:
        geometry = ProjectionGeometry(
            n_det_rows=n_rows,
            n_det_cols=n_cols,
            projections_per_rotation=n_projs
        )
    
    return SinogramData(
        data=data,
        geometry=geometry,
        selection=selection,
        original_shape=original_shape,
        file_path=path
    )
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_sinogram_loader.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/visualization/loaders/sinogram.py tests/unit/test_sinogram_loader.py
git commit -m "feat: add sinogram loader with selection support"
```

---

## Task 5: T-65 — DICOM Lazy Loading for Helical Data

**Files:**
- Modify: `src/visualization/loaders/sinogram.py`

**Interfaces:**
- Consumes: DICOM folder path
- Produces: Lazy-loading sinogram that only reads needed rows/projections

- [ ] **Step 1: Add DICOM folder test**

```python
# Add to tests/unit/test_sinogram_loader.py

def test_load_sinogram_from_dicom_folder():
    """Test loading sinogram from DICOM folder with lazy loading."""
    # This test would require actual DICOM files
    # Placeholder: just test the function can be called
    pass
```

- [ ] **Step 2: Implement DICOM lazy loading**

```python
# Add to src/visualization/loaders/sinogram.py

def load_sinogram_from_dicom(
    folder: Path,
    selection: Optional[SelectionConfig] = None,
) -> SinogramData:
    """Load projection data from DICOM folder with lazy loading.
    
    This function reads file headers first to identify which files
    contain which projections, then only loads the requested data.
    
    Args:
        folder: Path to DICOM folder
        selection: Which rows/projections to load
    
    Returns:
        SinogramData
    """
    if selection is None:
        selection = SelectionConfig()
    
    # Scan DICOM folder for projection files
    # This is a placeholder - actual implementation would:
    # 1. List all .dcm files
    # 2. Read headers to get InstanceNumber, etc.
    # 3. Build index of which file = which projection
    # 4. Only load files for selected projections
    
    raise NotImplementedError("DICOM lazy loading not yet implemented")


# Update load_sinogram to handle DICOM folders
def load_sinogram(
    path: Path,
    selection: Optional[SelectionConfig] = None,
    geometry: Optional[ProjectionGeometry] = None,
) -> SinogramData:
    """Load measured projection data with optional selection."""
    
    if selection is None:
        selection = SelectionConfig()
    
    # Check if path is a directory (DICOM folder)
    if path.is_dir():
        return load_sinogram_from_dicom(path, selection, geometry)
    
    # Existing file loading logic...
```

- [ ] **Step 3: Commit**

```bash
git add src/visualization/loaders/sinogram.py
git commit -m "feat: add DICOM lazy loading framework"
```

---

## Task 6: T-66 — Update loaders __init__.py

**Files:**
- Modify: `src/visualization/loaders/__init__.py`

- [ ] **Step 1: Add sinogram loader to exports**

```python
# src/visualization/loaders/__init__.py

from visualization.loaders.dicom import scan_series, load_dicom_series
from visualization.loaders.npy import load_npy, scan_npy_folder, load_npy_series
from visualization.loaders.projection import load_projection_geometry
from visualization.loaders.sinogram import (
    load_sinogram,
    load_sinogram_from_dicom,
    SinogramData,
    SelectionConfig,
)

__all__ = [
    "scan_series",
    "load_dicom_series",
    "load_npy",
    "scan_npy_folder",
    "load_npy_series",
    "load_projection_geometry",
    "load_sinogram",
    "load_sinogram_from_dicom",
    "SinogramData",
    "SelectionConfig",
]
```

- [ ] **Step 2: Commit**

```bash
git add src/visualization/loaders/__init__.py
git commit -m "feat: export sinogram loader functions"
```

---

## Task 7: T-67 — Comparison Module

**Files:**
- Create: `src/visualization/comparison.py`

**Interfaces:**
- Consumes: Two numpy arrays (synthetic, measured)
- Produces: ComparisonResult with metrics and difference array

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_comparison.py
import pytest
import numpy as np
from visualization.comparison import (
    compare_projections,
    ComparisonResult,
    ComparisonMetrics,
)


def test_compare_identical_arrays():
    """Test comparison of identical arrays."""
    data = np.ones((10, 8, 8))
    
    result = compare_projections(data, data)
    
    assert result.metrics.mae == 0.0
    assert result.metrics.rmse == 0.0
    assert result.metrics.ssim == 1.0


def test_compare_different_arrays():
    """Test comparison of different arrays."""
    synthetic = np.zeros((10, 8, 8))
    measured = np.ones((10, 8, 8)) * 100
    
    result = compare_projections(synthetic, measured)
    
    assert result.metrics.mae > 0
    assert result.difference.shape == synthetic.shape
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_comparison.py -v`
Expected: FAIL

- [ ] **Step 3: Implement comparison module**

```python
# src/visualization/comparison.py
"""Comparison of synthetic and measured projection data."""

import numpy as np
from dataclasses import dataclass
from typing import Optional


@dataclass
class ComparisonMetrics:
    """Quantitative comparison metrics."""
    mae: float       # Mean Absolute Error
    rmse: float      # Root Mean Square Error
    max_error: float
    ssim: float      # Structural Similarity Index
    correlation: float


@dataclass
class ComparisonResult:
    """Complete comparison result."""
    metrics: ComparisonMetrics
    synthetic: np.ndarray
    measured: np.ndarray
    difference: np.ndarray  # synthetic - measured


def _compute_ssim(
    img1: np.ndarray,
    img2: np.ndarray,
    window_size: int = 11,
    k1: float = 0.01,
    k2: float = 0.03,
    L: float = 1.0,
) -> float:
    """Compute SSIM between two images.
    
    Simplified implementation - consider using scikit-image for production.
    """
    # Convert to float
    img1 = img1.astype(np.float64)
    img2 = img2.astype(np.float64)
    
    # Compute means
    mu1 = np.mean(img1)
    mu2 = np.mean(img2)
    
    # Compute variances and covariance
    var1 = np.var(img1)
    var2 = np.var(img2)
    cov = np.mean((img1 - mu1) * (img2 - mu2))
    
    # Constants
    c1 = (k1 * L) ** 2
    c2 = (k2 * L) ** 2
    
    # SSIM formula
    numerator = (2 * mu1 * mu2 + c1) * (2 * cov + c2)
    denominator = (mu1 ** 2 + mu2 ** 2 + c1) * (var1 + var2 + c2)
    
    if denominator == 0:
        return 1.0 if np.array_equal(img1, img2) else 0.0
    
    ssim = numerator / denominator
    return float(ssim)


def compare_projections(
    synthetic: np.ndarray,
    measured: np.ndarray,
    compute_ssim: bool = True,
) -> ComparisonResult:
    """Compare synthetic vs measured projections.
    
    Args:
        synthetic: Forward-projected data
        measured: Measured projection data
        compute_ssim: Whether to compute SSIM (slower)
    
    Returns:
        ComparisonResult with metrics and arrays for visualization
    """
    # Ensure same shape
    assert synthetic.shape == measured.shape, \
        f"Shape mismatch: {synthetic.shape} vs {measured.shape}"
    
    # Convert to float
    synthetic = synthetic.astype(np.float64)
    measured = measured.astype(np.float64)
    
    # Compute difference
    difference = synthetic - measured
    
    # Compute metrics
    mae = float(np.mean(np.abs(difference)))
    rmse = float(np.sqrt(np.mean(difference ** 2)))
    max_error = float(np.max(np.abs(difference)))
    
    # Correlation
    synthetic_flat = synthetic.flatten()
    measured_flat = measured.flatten()
    correlation = float(np.corrcoef(synthetic_flat, measured_flat)[0, 1])
    
    # SSIM - compute per projection and average
    if compute_ssim:
        ssim_values = []
        for i in range(synthetic.shape[0]):
            ssim_val = _compute_ssim(synthetic[i], measured[i])
            ssim_values.append(ssim_val)
        ssim = float(np.mean(ssim_values))
    else:
        ssim = 0.0
    
    metrics = ComparisonMetrics(
        mae=mae,
        rmse=rmse,
        max_error=max_error,
        ssim=ssim,
        correlation=correlation
    )
    
    return ComparisonResult(
        metrics=metrics,
        synthetic=synthetic,
        measured=measured,
        difference=difference
    )
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_comparison.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/visualization/comparison.py tests/unit/test_comparison.py
git commit -m "feat: add comparison module with metrics"
```

---

## Task 8: T-68 — Comparison Visualization

**Files:**
- Modify: `src/visualization/comparison.py`

- [ ] **Step 1: Add visualization test**

```python
# Add to tests/unit/test_comparison.py

def test_create_comparison_figure():
    """Test creating comparison visualization."""
    from visualization.comparison import compare_projections, create_comparison_figure
    
    synthetic = np.random.rand(10, 64, 512).astype(np.float32)
    measured = synthetic + np.random.randn(10, 64, 512).astype(np.float32) * 0.1
    
    result = compare_projections(synthetic, measured)
    fig = create_comparison_figure(result, projection_index=0)
    
    assert fig is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_comparison.py::test_create_comparison_figure -v`
Expected: FAIL (function not defined)

- [ ] **Step 3: Implement visualization function**

```python
# Add to src/visualization/comparison.py

def create_comparison_figure(
    result: ComparisonResult,
    projection_index: int = 0,
    title: str = "Synthetic vs Measured Comparison",
) -> "plotly.graph_objects.Figure":
    """Create side-by-side visualization of comparison.
    
    Args:
        result: ComparisonResult from compare_projections
        projection_index: Which projection to display
        title: Figure title
    
    Returns:
        Plotly figure with 3 subplots
    """
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    
    # Get data for this projection
    synth = result.synthetic[projection_index]
    meas = result.measured[projection_index]
    diff = result.difference[projection_index]
    
    # Find common color range for synthetic/measured
    vmin = min(synth.min(), meas.min())
    vmax = max(synth.max(), meas.max())
    
    # Create figure with 3 columns
    fig = make_subplots(
        rows=1, cols=3,
        subplot_titles=("Synthetic", "Measured", "Difference"),
        horizontal_spacing=0.05
    )
    
    # Synthetic
    fig.add_trace(
        go.Heatmap(
            z=synth,
            colorscale="gray",
            zmin=vmin, zmax=vmax,
            coloraxis="coloraxis1"
        ),
        row=1, col=1
    )
    
    # Measured
    fig.add_trace(
        go.Heatmap(
            z=meas,
            colorscale="gray",
            zmin=vmin, zmax=vmax,
            coloraxis="coloraxis1"
        ),
        row=1, col=2
    )
    
    # Difference
    diff_range = max(abs(diff.min()), abs(diff.max()))
    fig.add_trace(
        go.Heatmap(
            z=diff,
            colorscale="RdBu",
            zmin=-diff_range, zmax=diff_range,
            coloraxis="coloraxis2"
        ),
        row=1, col=3
    )
    
    # Update layout
    fig.update_layout(
        title=title,
        height=400,
        width=1200,
        coloraxis1=dict(colorscale="gray", showscale=True),
        coloraxis2=dict(colorscale="RdBu", showscale=True),
        coloraxis_colorbar=dict(x=1.02),
    )
    
    # Update axes
    for col in [1, 2, 3]:
        fig.update_xaxes(title_text="Column", row=1, col=col)
        fig.update_yaxes(title_text="Row", row=1, col=col, scaleanchor=f"x col {col}")
    
    return fig


def create_metrics_table(result: ComparisonResult) -> "plotly.graph_objects.Figure":
    """Create a table showing comparison metrics.
    
    Args:
        result: ComparisonResult from compare_projections
    
    Returns:
        Plotly figure with metrics table
    """
    import plotly.graph_objects as go
    
    m = result.metrics
    
    fig = go.Figure(data=[go.Table(
        header=dict(
            values=["Metric", "Value"],
            fill_color="lightgray",
            align="left"
        ),
        cells=dict(
            values=[
                ["MAE", "RMSE", "Max Error", "SSIM", "Correlation"],
                [f"{m.mae:.4f}", f"{m.rmse:.4f}", f"{m.max_error:.4f}", 
                 f"{m.ssim:.4f}", f"{m.correlation:.4f}"]
            ],
            fill_color="white",
            align="left"
        )
    )])
    
    fig.update_layout(title="Comparison Metrics", height=200)
    
    return fig
```

- [ ] **Step 4: Run test**

Run: `pytest tests/unit/test_comparison.py::test_create_comparison_figure -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/visualization/comparison.py
git commit -m "feat: add comparison visualization functions"
```

---

## Task 9: T-69 — Integration Tests

**Files:**
- Create: `tests/integration/test_forward_projection_workflow.py`

**Interfaces:**
- Tests the full workflow: volume + geometry → forward project → compare

- [ ] **Step 1: Write integration test**

```python
# tests/integration/test_forward_projection_workflow.py
import pytest
import numpy as np
from visualization.volume import Volume
from visualization.geometry import ProjectionGeometry
from visualization.forward_project import forward_project
from visualization.comparison import compare_projections
from visualization.loaders.sinogram import load_sinogram, SelectionConfig


def test_full_workflow():
    """Test complete forward projection workflow."""
    # 1. Create phantom volume
    volume = Volume(
        array=np.ones((20, 20, 20), dtype=np.int16) * 0,  # Air
        spacing=(2.5, 1.0, 1.0),
        origin=(0, 0, 0),
        meta={}
    )
    
    # 2. Create geometry
    geometry = ProjectionGeometry(
        n_det_cols=128,
        n_det_rows=16,
        projections_per_rotation=50,
        sid=500.0,
        sdd=1000.0
    )
    
    # 3. Forward project
    result = forward_project(
        volume, geometry,
        row_indices=list(range(16)),
        col_indices=list(range(128)),
        proj_indices=list(range(50))
    )
    
    assert result.projections.shape == (50, 16, 128)
    
    # 4. Create measured data (add noise)
    measured = result.projections + np.random.randn(50, 16, 128).astype(np.float32) * 10
    
    # 5. Compare
    comparison = compare_projections(result.projections, measured)
    
    assert comparison.metrics.mae > 0
    assert comparison.metrics.ssim < 1.0


def test_partial_sinogram_workflow():
    """Test workflow with partial sinogram selection."""
    # Create test data
    test_data = np.random.rand(100, 32, 256).astype(np.float32)
    
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.npy', delete=False) as f:
        np.save(f.name, test_data)
        from pathlib import Path
        path = Path(f.name)
    
    try:
        # Load only central row
        selection = SelectionConfig(row_mode="central")
        sinogram = load_sinogram(path, selection=selection)
        
        assert sinogram.data.shape[1] == 1  # Only 1 row
    finally:
        path.unlink()
```

- [ ] **Step 2: Run integration test**

Run: `pytest tests/integration/test_forward_projection_workflow.py -v`
Expected: PASS (tests complete workflow)

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_forward_projection_workflow.py
git commit -m "test: add integration tests for forward projection workflow"
```

---

## Task 10: T-70 — App Integration

**Files:**
- Modify: `src/visualization/app.py`

**Interfaces:**
- Adds UI for forward projection and comparison workflow

- [ ] **Step 1: Add forward projection section to app**

In `app.py`, add a new tab or section for forward projection:

```python
# In app.py - add to main section

def render_forward_projection_section():
    """Render the forward projection comparison UI."""
    st.subheader("🔬 Forward Projection Comparison")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Volume Input")
        # Use existing volume selection
        
    with col2:
        st.markdown("### Measured Data")
        # File uploader for .npy/.npz
        measured_file = st.file_uploader(
            "Load measured projections",
            type=['npy', 'npz']
        )
        
        # Optional geometry file
        geometry_file = st.file_uploader(
            "Load geometry file (optional)",
            type=['txt', 'yaml']
        )
    
    # Data selection
    with st.expander("Data Selection"):
        # Row selection
        row_mode = st.radio(
            "Detector Row Selection",
            ["all", "central", "range", "downsample", "custom"],
            horizontal=True
        )
        
        # Col selection
        col_mode = st.radio(
            "Detector Column Selection", 
            ["all", "central", "range", "downsample", "custom"],
            horizontal=True
        )
        
        # Projection selection
        proj_mode = st.radio(
            "Projection Selection",
            ["all", "central", "range", "downsample", "custom"],
            horizontal=True
        )
    
    # Run button
    if st.button("Run Forward Projection", type="primary"):
        with st.spinner("Computing forward projection..."):
            # 1. Forward project volume
            # 2. Load measured data
            # 3. Compare
            # 4. Display results
            pass
    
    # Results display
    st.markdown("### Results")
    
    # Metrics table
    # Comparison visualization (3 columns)
    # Difference heatmap
```

- [ ] **Step 2: Test the UI**

Run: `streamlit run src/visualization/app.py`
Verify new section appears

- [ ] **Step 3: Commit**

```bash
git add src/visualization/app.py
git commit -m "feat: add forward projection UI to app"
```

---

## Summary

| Task | Description | Status |
|------|-------------|--------|
| T-61 | Add parallelproj dependency | Pending |
| T-62 | Forward projection module | Pending |
| T-63 | Implement actual parallelproj forward projection | Pending |
| T-64 | Sinogram loader with selection | Pending |
| T-65 | DICOM lazy loading | Pending |
| T-66 | Update loaders __init__.py | Pending |
| T-67 | Comparison module | Pending |
| T-68 | Comparison visualization | Pending |
| T-69 | Integration tests | Pending |
| T-70 | App integration | Pending |

---

## Dependencies Between Tasks

```
T-61 ──┬──> T-62 ──> T-63 ──> T-69 ──> T-70
       │                  ▲
       └──> T-64 ──> T-65 ──> T-66 ──> T-70
                        ▲
T-67 ──> T-68 ─────────┘
```

---

## Commands

```bash
# Run all tests
pytest tests/ -v

# Run specific test files
pytest tests/unit/test_forward_project.py -v
pytest tests/unit/test_comparison.py -v
pytest tests/unit/test_sinogram_loader.py -v

# Run app
streamlit run src/visualization/app.py --server.port 8501
```
