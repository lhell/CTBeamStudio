# Sinogram Loader — Design Specification

**Date:** 2026-11-04
**Status:** Draft
**Author:** CT-Viewer Team
**Epoch:** Phase 9 (T-64, T-65, T-66)

## 1. Overview

### Goal

Add a sinogram / projection-data loader to the existing `backend/loaders/`
package. It reads measured projection data from multiple formats, supports
row / column / projection selection, and loads lazily so large helical
datasets (DICOM image series, NIfTI) are not fully materialised in memory.

This is the foundation for Phase 10 (Comparison, T-67/68/69) and Phase 11
(Forward-Projection UI, T-70).

### Out of Scope

- DICOM **CT Raw Data Storage** (7FE0,0010, compressed, complex) — documented
  limitation, covered later.
- Reconstruction algorithms.
- Multi-energy / 4D NIfTI sinograms.
- Real-time loading.

## 2. Canonical Axis Convention

All `SinogramData` arrays are normalised to a **canonical order**:

- **Axis 0** = projection / view angle (dimension `n_proj`)
- **Axis 1** = detector rows (dimension `n_rows`)
- **Axis 2** = detector columns (dimension `n_cols`)

`SinogramData.data` always has shape `(n_proj, n_rows, n_cols)`.

The loader normalises to this convention regardless of the file's native
order. `SinogramData.original_shape` and `SinogramData.source_axis_order`
record the file's native shape and ordering for diagnostics.

For NIfTI, spatial orientation (qform/sform) describes mm placement of
rows/cols, not the projection axis. Therefore the projection axis is defined
**by documented convention** (axis 0 = projection), not by header heuristics.
Users must store NIfTI sinograms per this convention (documented in the
loader docstring and this spec).

## 3. Data Model

### SelectionConfig

```python
@dataclass
class SelectionConfig:
    """Which detector rows/columns and projections to load.

    Each axis has a mode plus optional parameters:
      - "all":        use every index
      - "central":    a contiguous central band (uses *_range)
      - "range":      indices [start, end) (uses *_range)
      - "downsample": every Nth index (uses *_downsample)
      - "custom":     an explicit index list (uses *_custom)
    """

    # Detector rows (canonical axis 1)
    row_mode: Literal["all", "central", "range", "downsample", "custom"] = "all"
    row_range: Optional[tuple[int, int]] = None
    row_downsample: Optional[int] = None
    row_custom: Optional[list[int]] = None

    # Detector columns (canonical axis 2)
    col_mode: Literal["all", "central", "range", "downsample", "custom"] = "all"
    col_range: Optional[tuple[int, int]] = None
    col_downsample: Optional[int] = None
    col_custom: Optional[list[int]] = None

    # Projections (canonical axis 0)
    proj_mode: Literal["all", "central", "range", "downsample", "custom"] = "all"
    proj_range: Optional[tuple[int, int]] = None
    proj_downsample: Optional[int] = None
    proj_custom: Optional[list[int]] = None
```

Selection is expressed on **canonical** axes and applied **after**
normalisation.

### SinogramData

```python
@dataclass
class SinogramData:
    """Loaded (or lazily-loadable) sinogram / projection data."""

    data: Optional[np.ndarray]      # shape (n_proj, n_rows, n_cols); None if lazy
    geometry: Optional[ProjectionGeometry]
    selection: SelectionConfig
    original_shape: tuple[int, int, int]
    source_axis_order: tuple[str, str, str]  # e.g. ("proj", "row", "col")
    format: str                     # "numpy" | "nifti" | "dicom"
    path: Optional[Path] = None
    lazy: bool = False              # True when `data` is not yet materialised
    # Lazily materialises `data` from `_loader` when called.
    _loader: Optional[Callable[[], np.ndarray]] = None

    def materialize(self) -> np.ndarray:
        """Load and cache `data`, then return it."""
```

`materialize()` (and a `.data` accessor path) triggers the underlying loader
on first use and caches the result.

## 4. load_sinogram()

```python
def load_sinogram(
    path: Path,
    selection: Optional[SelectionConfig] = None,
    geometry: Optional[ProjectionGeometry] = None,
) -> SinogramData:
    """Load measured projection data with optional selection.

    Args:
        path: Path to a projection file (.npy/.npz/.nii/.nii.gz) or a
            DICOM image series directory.
        selection: Which rows/columns/projections to load (None = all).
        geometry: Optional geometry; stored and used for DICOM validation.

    Returns:
        SinogramData (possibly lazy) with the selected subset.
    """
```

### Format detection (`_detect_format`)

| Extension / type | Format |
|------------------|--------|
| `.npy`, `.npz`   | `numpy` |
| `.nii`, `.nii.gz`| `nifti` |
| directory, `.dcm`, `.dicom` | `dicom` |
| anything else    | `unknown` → `ValueError` |

## 5. Per-Format Behaviour

### 5.1 Numpy (.npy / .npz)

- `.npy`: `np.load(path, mmap_mode="r")` is lazy when a subset is requested;
  eager `np.load(path)` for a full `all` selection.
- `.npz`: `np.load(path)["arr_0"]` (or first array). Lazy via mmap when
  subsetting.
- Requires 3D input after any 2D wrapper; normalised to canonical order.

### 5.2 NIfTI (.nii / .nii.gz)

- Uses `nibabel` (optional dependency, lazy import). If missing →
  `ImportError` with an install hint.
- `nibabel.load()` defers array reads; slice `img.dataobj` to the selection
  before `get_fdata()` for lazy subsets.
- Requires a 3D sinogram. A 4D NIfTI raises `ValueError` (out of scope).

### 5.3 DICOM image series (lazy)

- `scan_dicom_sinogram(dir)`: cheap header scan (no pixel data) → returns
  series info: number of projections (`n_proj`), `n_rows`, `n_cols`,
  per-frame geometry, input type.
- `load_sinogram()` on a DICOM directory reads **only** the selected
  projections / rows / cols via `pydicom.pixel_array`, lazily per request —
  never all frames.
- Geometry inferred from the series where present; validated against any
  provided `geometry`.

## 6. Selection Resolution Helper

```python
def resolve_indices(mode, size, range_=None, downsample=None, custom=None) -> list[int]:
    """Resolve a SelectionConfig axis (mode + params) to an index list."""
```

Shared by all three axes. Raises `ValueError` for unknown modes, `IndexError`
for out-of-range indices.

## 7. Error Handling

| Condition | Error |
|-----------|-------|
| Unknown format | `ValueError` |
| Empty selection result | `ValueError` |
| Invalid mode value | `ValueError` |
| Out-of-range index | `IndexError` |
| DICOM folder with no readable series | `ValueError` |
| Inconsistent DICOM geometry across frames | `ValueError` |
| nibabel required but missing | `ImportError` (with hint) |
| 4D NIfTI sinogram | `ValueError` (out of scope) |

## 8. Testing (TDD)

`tests/unit/test_sinogram_loader.py`:

- Format detection for `.npy`, `.npz`, `.nii`, `.nii.gz`, directory, `.dcm`.
- `.npy`: full load + selection (central / range / downsample / custom) on
  each of the three axes; shape is canonical `(n_proj, n_rows, n_cols)`.
- `.npz`: load + selection.
- NIfTI: create a small NIfTI in-memory with `nibabel`; save/load roundtrip;
  axis normalisation; lazy subset.
- DICOM: synthetic projection-series fixture in `conftest`; lazy subset reads;
  geometry inference.
- `resolve_indices`: all modes, bounds, errors.
- Error cases: unknown format, bad mode, out-of-range.

All DICOM / NIfTI fixtures are synthetic and created on the fly — no binary
data added to the repository (consistent with the repo's data policy).

## 9. T-66: Exports

Update `backend/loaders/__init__.py`:

```python
from backend.loaders.sinogram import (
    SelectionConfig,
    SinogramData,
    load_sinogram,
    resolve_indices,
    scan_dicom_sinogram,
)
```

so `from backend.loaders import load_sinogram, SelectionConfig, ...` works.

## 10. Dependencies

- `nibabel`: new **optional** dependency (NIfTI support), added to
  `[project.optional-dependencies]` (e.g. `nifti` extra), not hard
  `dependencies`.
- `pydicom`, `numpy`: already hard dependencies.

## 11. Acceptance Criteria

| Task | Criterion |
|------|-----------|
| T-64 | `load_sinogram()` loads `.npy`/`.npz`/`.nii`/`.nii.gz` with `SelectionConfig`; output is canonical `(n_proj, n_rows, n_cols)` |
| T-65 | DICOM image series directory support with lazy per-request pixel reads; NIfTI lazy subsets |
| T-66 | `from backend.loaders import load_sinogram, SelectionConfig, SinogramData` works |
| — | Full test suite passes (both plain and conda `ct-viewer` env) |
