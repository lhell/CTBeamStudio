# Forward Projection with Parallelproj — Design Specification

**Date:** 2026-10-30  
**Status:** Draft  
**Author:** CTBeamStudio Team

## 1. Overview

### Goals

- Add forward projection capability to generate synthetic projections from 3D volumes
- Compare synthetic projections with measured data
- Provide visual and quantitative comparison results (MAE, RMSE, SSIM, Correlation)
- Support partial sinograms via row/column/projection selection
- Support lazy loading for helical DICOM projection data

### Scope

This specification covers:

- **Phase 8:** Forward Projection with Parallelproj
  - T-61: Add parallelproj dependency
  - T-62: Forward Projection Module
  - T-63: Implement actual parallelproj forward projection

- **Phase 9:** Sinogram Loader with Lazy Loading
  - T-64: Sinogram loader with selection
  - T-65: DICOM lazy loading
  - T-66: Update loaders __init__.py

- **Phase 10:** Comparison
  - T-67: Comparison module with metrics
  - T-68: Comparison visualization

- **Phase 11:** App Integration
  - T-70: Forward projection UI in Streamlit app

## 2. Architecture

### File Structure

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
└── integration/
    └── test_forward_projection_workflow.py  # NEW
```

## 3. Global Constraints

- **Python:** >= 3.11
- **PyTorch:** for tensor operations (must be installed separately, see below)
- **parallelproj:** for forward projection (see installation below)

---

## Installation

**WICHTIG:** parallelproj kann NICHT mit pip installiert werden! Es muss über **conda-forge** installiert werden.

### Option 1: Conda/Mamba (empfohlen)

**CPU-only:**
```bash
# Miniforge herunterladen: https://github.com/conda-forge/miniforge
mamba create -n ct-viewer python=3.12
mamba activate ct-viewer
mamba install -c conda-forge parallelproj "libparallelproj=*=cpu*"
mamba install -c conda-forge pytorch torchvision cpuonly
```

**GPU (CUDA 12.1):**
```bash
mamba create -n ct-viewer python=3.12
mamba activate ct-viewer
mamba install -c conda-forge parallelproj pytorch cuda-toolkit=12.1
```

### Option 2: pip für PyTorch, conda für parallelproj

```bash
# PyTorch zuerst (pip)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# Dann parallelproj via conda (in gleicher Umgebung)
conda install -c conda-forge parallelproj
```

---

**Fallback:** Wenn parallelproj nicht verfügbar ist, gibt das Modul Zeros zurück mit einer Warning. Dies ist nützlich für Testing ohne Conda-Umgebung.
- **All angles:** in degrees
- **All distances:** in mm
- **Source angle:** 0° = anterior (front of patient), positive = CCW (Z-axis rotation)
- **Volume data:** in HU (Hounsfield Units)
- **Lazy loading:** for helical DICOM data to avoid loading entire dataset

## 4. Component Specifications

### 4.1 Forward Projection Module (T-62, T-63)

#### ForwardProjectionResult Dataclass

```python
@dataclass
class ForwardProjectionResult:
    """Result of forward projection."""
    projections: np.ndarray  # Shape: (n_projections, n_rows, n_cols)
    geometry: ProjectionGeometry
    row_indices: list[int]
    col_indices: list[int]
    proj_indices: list[int]
```

#### forward_project() Function

```python
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
```

#### Geometry Setup for Parallelproj

parallelproj uses a specific coordinate system:

- Volume order: (z, y, x) → parallelproj expects (x, y, z)
- Voxel size: `(volume.spacing[2], volume.spacing[1], volume.spacing[0])`
- Origin: `(volume.origin[2], volume.origin[1], volume.origin[0])`
- Source angles: Z-axis rotation, 0° = anterior (+X direction), positive = CCW

### 4.2 Sinogram Loader (T-64, T-65)

#### SelectionConfig Dataclass

```python
@dataclass
class SelectionConfig:
    """Configuration for detector row/column and projection selection."""
    
    # Detector Row Selection
    row_mode: Literal["all", "central", "range", "downsample", "custom"] = "all"
    row_range: Optional[tuple[int, int]] = None
    row_downsample: Optional[int] = None
    row_custom: Optional[list[int]] = None
    
    # Detector Column Selection
    col_mode: Literal["all", "central", "range", "downsample", "custom"] = "all"
    col_range: Optional[tuple[int, int]] = None
    col_downsample: Optional[int] = None
    col_custom: Optional[list[int]] = None
    
    # Projection Selection
    proj_mode: Literal["all", "central", "range", "downsample", "custom"] = "all"
    proj_range: Optional[tuple[int, int]] = None
    proj_downsample: Optional[int] = None
    proj_custom: Optional[list[int]] = None
```

#### SinogramData Dataclass

```python
@dataclass
class SinogramData:
    """Loaded sinogram/projection data."""
    data: np.ndarray  # Shape: (n_projections, n_rows, n_cols)
    geometry: ProjectionGeometry
    selection: SelectionConfig
    original_shape: tuple[int, int, int]
    file_path: Optional[Path] = None
```

#### load_sinogram() Function

```python
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
```

### 4.3 Comparison Module (T-67, T-68)

#### ComparisonMetrics Dataclass

```python
@dataclass
class ComparisonMetrics:
    """Quantitative comparison metrics."""
    mae: float       # Mean Absolute Error
    rmse: float      # Root Mean Square Error
    max_error: float
    ssim: float      # Structural Similarity Index
    correlation: float
```

#### ComparisonResult Dataclass

```python
@dataclass
class ComparisonResult:
    """Complete comparison result."""
    metrics: ComparisonMetrics
    synthetic: np.ndarray
    measured: np.ndarray
    difference: np.ndarray  # synthetic - measured
```

#### compare_projections() Function

```python
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
```

#### SSIM Edge Case Handling

When input arrays have zero variance (constant values):
- If arrays are identical: return SSIM = 1.0
- Otherwise: return SSIM = 0.0

#### Visualization Functions

```python
def create_comparison_figure(
    result: ComparisonResult,
    projection_index: int = 0,
    title: str = "Synthetic vs Measured Comparison",
) -> plotly.graph_objects.Figure:
    """Create side-by-side visualization with 3 columns:
    - Synthetic projection
    - Measured projection  
    - Difference heatmap (RdBu colorscale)
    """
```

```python
def create_metrics_table(
    result: ComparisonResult,
) -> plotly.graph_objects.Figure:
    """Create a table showing MAE, RMSE, Max Error, SSIM, Correlation."""
```

## 5. UI Integration (T-70)

The Streamlit app will include a new section for forward projection:

### UI Components

1. **Volume Input** — Use existing volume selection
2. **Measured Data Upload** — File uploader for .npy/.npz
3. **Geometry File (optional)** — Load geometry from .txt/.yaml
4. **Data Selection** — Expanders for row/col/projection selection
5. **Run Button** — Trigger forward projection + comparison
6. **Results Display:**
   - Metrics table
   - 3-column visualization (Synthetic | Measured | Difference)
   - Per-projection navigation

## 6. Review Focus

- **Geometry compatibility:** ProjectionGeometry parameters must match parallelproj expectations (Z-axis rotation)
- **Memory efficiency:** Lazy loading must not load entire helical dataset into memory
- **Partial sinograms:** Row/column/projection selection must work correctly
- **SSIM calculation:** Must handle the edge case where input arrays have zero variance
- **GPU/CPU:** Must work on both CUDA and CPU devices

## 7. Acceptance Criteria

| Task | Criterion |
|------|-----------|
| T-61 | `import parallelproj` works |
| T-62 | `forward_project(volume, geometry)` returns ForwardProjectionResult |
| T-63 | Synthetic projections are generated from volume using parallelproj |
| T-64 | `load_sinogram()` loads .npy/.npz with SelectionConfig |
| T-65 | DICOM folder support with lazy loading framework |
| T-66 | `from visualization.loaders import load_sinogram` works |
| T-67 | MAE, RMSE, SSIM, Correlation computed correctly |
| T-68 | 3-column Plotly visualization displays correctly |
| T-69 | Integration tests pass for full workflow |
| T-70 | App UI allows forward projection + comparison workflow |

## 8. Dependencies Between Tasks

```
T-61 ──┬──> T-62 ──> T-63 ──> T-69 ──> T-70
       │                  ▲
       └──> T-64 ──> T-65 ──> T-66 ──> T-70
                        ▲
T-67 ──> T-68 ─────────┘
```

## 9. Out of Scope

- Actual reconstruction algorithms (separate project)
- Real-time projection visualization during scanning
- Multi-energy CT support
- Metal artifact reduction
- Iterative reconstruction
- Database storage for results
