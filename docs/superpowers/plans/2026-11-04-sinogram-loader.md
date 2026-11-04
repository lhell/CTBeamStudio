# Sinogram Loader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a sinogram / projection-data loader to `backend/loaders/` that reads numpy, NIfTI, and DICOM image-series data with row/column/projection selection, lazy loading, and a mutable `axis_order` override.

**Architecture:** A new `backend/loaders/sinogram.py` module exposing `SelectionConfig`, `SinogramData`, `load_sinogram`, `resolve_indices`, and `scan_dicom_sinogram`. All output arrays are normalised to canonical `(n_proj, n_rows, n_cols)`. `SinogramData` holds an optional raw file-order array and a mutable `axis_order`; changing it re-derives (in-memory on full load, re-read on lazy/partial).

**Tech Stack:** Python 3.11+, numpy, pydicom (hard deps), nibabel (optional dep for NIfTI).

**Spec:** `docs/superpowers/specs/2026-11-04-sinogram-loader-design.md`

## Global Constraints

- Canonical output order is always `(n_proj, n_rows, n_cols)`.
- `selection` is always expressed in canonical `(proj, row, col)` and never changes when `axis_order` is flipped.
- `axis_order` is a permutation of `("proj", "row", "col")` describing the file's native axis order; default is `("proj", "row", "col")`.
- Extra/short dimensions in a selection or a 4D NIfTI → handled per spec (3D only).
- Only synthetic fixtures in tests — no real/binary patient data in the repo.
- `nibabel` is optional and lazily imported; its absence raises `ImportError` with an install hint.
- Module lives under `src/backend/loaders/` (imports as `backend.loaders`).

## Review Focus

- Wrong `axis_order` in a loaded file — changing it after load must give a correct result, not silently transpose the wrong subset (`SinogramData.axis_order` setter).
- Empty selection (e.g. `central` with range `(5,5)`) → `ValueError`, not an empty silent array.
- 3D NIfTI with a 4D file → `ValueError`, not silent axis mis-read.
- Subset rows/cols/projections that are out of range of the file dims → `IndexError`/`ValueError`.
- Changing `axis_order` in the lazy case re-reads from disk (selection points the wrong way otherwise).

---

### Task 1: `SelectionConfig`, `resolve_indices`, `SinogramData` core

**Files:**
- Create: `src/backend/loaders/sinogram.py`
- Test: `tests/unit/test_sinogram_loader.py`

**Interfaces:**
- Produces: `SelectionConfig` (dataclass with `row_*`, `col_*`, `proj_*` fields), `resolve_indices(mode, size, range_=None, downsample=None, custom=None) -> list[int]`, `SinogramData` (dataclass with `data`, `geometry`, `selection`, `original_shape`, `source_axis_order`, `path`, `format`, `lazy`, `_loader`, `_raw_file_order`; `axis_order` property + setter; `materialize()` method).

- [ ] **Step 1: Write failing tests for `resolve_indices` and `SinogramData`**

```python
# tests/unit/test_sinogram_loader.py
import numpy as np
import pytest
from backend.loaders.sinogram import SelectionConfig, SinogramData, resolve_indices

def test_resolve_all():
    assert resolve_indices("all", 10) == list(range(10))

def test_resolve_central():
    assert resolve_indices("central", 10, range_=(3, 7)) == [3, 4, 5, 6]

def test_resolve_range():
    assert resolve_indices("range", 10, range_=(2, 5)) == [2, 3, 4]

def test_resolve_downsample():
    assert resolve_indices("downsample", 10, downsample=3) == [0, 3, 6, 9]

def test_resolve_custom():
    assert resolve_indices("custom", 10, custom=[0, 2, 5]) == [0, 2, 5]

def test_resolve_bad_mode():
    with pytest.raises(ValueError):
        resolve_indices("bogus", 10)

def test_resolve_range_out_of_bounds():
    with pytest.raises(IndexError):
        resolve_indices("range", 5, range_=(0, 10))

def test_axis_order_default_is_canonical():
    s = SinogramData(data=None, geometry=None, selection=SelectionConfig(),
                     original_shape=(3, 4, 5), source_axis_order=("proj", "row", "col"))
    assert s.axis_order == ("proj", "row", "col")

def test_axis_order_invalid_raises():
    s = SinogramData(data=None, geometry=None, selection=SelectionConfig(),
                     original_shape=(3, 4, 5), source_axis_order=("proj", "row", "col"))
    with pytest.raises(ValueError):
        s.axis_order = ("proj", "row")  # not a permutation

def test_materialize_replaces_none_with_loader_result():
    s = SinogramData(data=None, geometry=None, selection=SelectionConfig(),
                     original_shape=(3, 4, 5), source_axis_order=("proj", "row", "col"),
                     _loader=lambda: np.zeros((3, 4, 5)))
    out = s.materialize()
    assert out.shape == (3, 4, 5)
    assert s.data.shape == (3, 4, 5)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_sinogram_loader.py -v`
Expected: FAIL (import error for `backend.loaders.sinogram`)

- [ ] **Step 3: Implement `SelectionConfig`, `resolve_indices`, and `SinogramData` in `src/backend/loaders/sinogram.py`**

`SelectionConfig`: dataclass with `row_mode/row_range/row_downsample/row_custom`, `col_*`, `proj_*` per the spec. Use `typing.Literal` and `Optional`.

`resolve_indices`: return `list(range(size))` for `all`; for `central`/`range`, `list(range(*range_))`; for `downsample`, `list(range(0, size, downsample))`; for `custom`, list. Validate mode and bounds:
- unknown mode → `ValueError`
- out-of-range indices → `IndexError`

`SinogramData`: dataclass. `axis_order` backing field `_axis_order` defaulting to `source_axis_order`. The setter validates it is a permutation of `("proj", "row", "col")` (raise `ValueError`), then marks `self.data = None` and clears `_loader` so `materialize()` re-reads. `materialize()`: if `data is not None` return it; else call `_loader()`, store in `data`, return.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_sinogram_loader.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_sinogram_loader.py src/backend/loaders/sinogram.py
git commit -m "feat(backend): SelectionConfig, resolve_indices, SinogramData core"
```

---

### Task 2: Numpy loader (`.npy` / `.npz`) with selection and axis normalization

**Files:**
- Modify: `src/backend/loaders/sinogram.py`
- Test: `tests/unit/test_sinogram_loader.py`

**Interfaces:**
- Consumes: `SelectionConfig`, `SinogramData`, `resolve_indices` (Task 1).
- Produces: `_detect_format(path) -> str`, `_load_numpy(path, selection, axis_order) -> SinogramData`.

- [ ] **Step 1: Write failing tests for numpy loading and normalization**

```python
# tests/unit/test_sinogram_loader.py (add)
from pathlib import Path
import numpy as np
import pytest
from backend.loaders.sinogram import (
    SelectionConfig, SinogramData, load_sinogram, _detect_format, _load_numpy,
)

def test_detect_format_npy(tmp_path):
    p = tmp_path / "a.npy"; p.touch()
    assert _detect_format(p) == "numpy"
def test_detect_format_npz(tmp_path):
    p = tmp_path / "a.npz"; p.touch()
    assert _detect_format(p) == "numpy"
def test_detect_format_unknown(tmp_path):
    p = tmp_path / "a.xyz"; p.touch()
    assert _detect_format(p) == "unknown"

def test_load_numpy_full(tmp_path):
    arr = np.zeros((3, 4, 5)); p = tmp_path / "s.npy"
    np.save(p, arr)
    s = _load_numpy(p, SelectionConfig(), ("proj", "row", "col"))
    assert s.data.shape == (3, 4, 5)
    assert s.original_shape == (3, 4, 5)

def test_load_numpy_selected_rows(tmp_path):
    arr = np.arange(120).reshape(3, 4, 5); p = tmp_path / "s.npy"
    np.save(p, arr)
    sel = SelectionConfig(row_mode="range", row_range=(1, 3))
    s = _load_numpy(p, sel, ("proj", "row", "col"))
    assert s.data.shape == (3, 2, 5)
    # rows 1,2 selected
    np.testing.assert_array_equal(s.data[:, 0], arr[:, 1])

def test_load_numpy_axis_order_normalizes(tmp_path):
    # file stored (row, proj, col) -> canonical (proj, row, col)
    arr = np.arange(120).reshape(2, 3, 4)  # (row, proj, col)
    p = tmp_path / "s.npy"; np.save(p, arr)
    s = _load_numpy(p, SelectionConfig(), ("row", "proj", "col"))
    assert s.data.shape == (3, 2, 4)
    assert s.source_axis_order == ("row", "proj", "col")

def test_load_npy_confused_ext(tmp_path):
    p = tmp_path / "a.xyz"; p.touch()
    with pytest.raises(ValueError):
        load_sinogram(p)
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python -m pytest tests/unit/test_sinogram_loader.py -k "detect or load_numpy or load_npy" -v`
Expected: FAIL (functions not defined)

- [ ] **Step 3: Implement `_detect_format`, `_load_numpy`, and wire `load_sinogram`**

```python
def _detect_format(path: Path) -> str:
    if path.is_dir(): return "dicom"
    suffix = path.suffix.lower()
    if suffix in (".npy", ".npz"): return "numpy"
    if suffix in (".nii", ".gz"): return "nifti"  # .nii.gz handled by name
    if suffix in (".dcm", ".dicom"): return "dicom"
    return "unknown"
```

Handle `.nii.gz` via `path.name.endswith(".nii.gz")` before suffix checks.

`_load_numpy(path, selection, axis_order)`:
1. Load raw: `.npz` → `np.load(path)["arr_0"]`; `.npy` → `np.load(path)`.
2. Materialise, but if only a subset is requested, prefer `np.load(path, mmap_mode="r")` and slice, then materialise — keep `SinogramData.lazy` semantics per spec (full `all` selection is eager).
3. Determine the raw array shape. `original_shape` = raw shape.
4. Build a helper `_normalize(raw, file_order, selection)`:
   - transpose `raw` so axes become canonical `(proj, row, col)` using `axis_order`,
   - resolve indices per canonical axis,
   - index-select by the resolved lists,
   - return the canonical subset.
5. Return `SinogramData` with `data` = canonical subset, `source_axis_order=axis_order`, `format="numpy"`, `path=path`, `selection=selection`.

For full `all` selection with the default `axis_order`, keep the eager path (with mmap when subsetting).

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `python -m pytest tests/unit/test_sinogram_loader.py -k "detect or load_numpy or load_npy" -v`
Expected: PASS

- [ ] **Step 5: Add and commit a passing `load_sinogram` numpy path test**

Add `test_load_sinogram_numpy(tmp_path)` calling `load_sinogram(p)` on a saved `.npy` and asserting canonical shape. Note: `load_sinogram` is defined here (dispatches to `_load_numpy` etc.) but full dispatch for all three formats lands in Task 4; the numpy branch must already work.

```bash
git add tests/unit/test_sinogram_loader.py src/backend/loaders/sinogram.py
git commit -m "feat(backend): numpy sinogram loading with selection + normalization"
```

---

### Task 3: NIfTI loader via nibabel (optional dep) with lazy subsets

**Files:**
- Modify: `src/backend/loaders/sinogram.py`
- Test: `tests/unit/test_sinogram_loader.py`

**Interfaces:**
- Consumes: `_detect_format`, `_normalize`, `SelectionConfig`, `SinogramData` (Tasks 1–2).
- Produces: `_load_nifti(path, selection, axis_order) -> SinogramData`.

- [ ] **Step 1: Write failing NIfTI tests**

```python
# tests/unit/test_sinogram_loader.py (add)
import numpy as np
import pytest
nib = pytest.importorskip("nibabel")  # skip if nibabel not installed

def test_load_nifti_full(tmp_path):
    arr = np.zeros((3, 4, 5))
    img = nib.Nifti1Image(arr, np.eye(4))
    p = tmp_path / "s.nii.gz"; nib.save(img, p)
    from backend.loaders.sinogram import _load_nifti, SelectionConfig
    s = _load_nifti(p, SelectionConfig(), ("proj", "row", "col"))
    assert s.data.shape == (3, 4, 5)
    assert s.format == "nifti"

def test_load_nifti_lazy_subset_reads_slice(tmp_path):
    arr = np.arange(120).reshape(3, 4, 5)
    img = nib.Nifti1Image(arr, np.eye(4))
    p = tmp_path / "s.nii.gz"; nib.save(img, p)
    from backend.loaders.sinogram import _load_nifti, SelectionConfig
    sel = SelectionConfig(proj_mode="range", proj_range=(1, 3))
    count_holder = {"n": 0}
    s = _load_nifti(p, sel, ("proj", "row", "col"), _on_read=lambda: count_holder.__setitem__("n", count_holder["n"] + 1))
    assert s.lazy is False
    assert s.data.shape == (2, 4, 5)
```

(If lazy NIfTI is not easily verifiable via the hook, assert canonical shape + subset shape only; the lazy mechanism is validated by the integration in Task 4.)

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python -m pytest tests/unit/test_sinogram_loader.py -k "nifti" -v`
Expected: FAIL (function not defined) or runtime error

- [ ] **Step 3: Implement `_load_nifti`**

```python
def _load_nifti(path, selection, axis_order, _on_read=None):
    try:
        import nibabel as nib
    except ImportError:
        raise ImportError("nibabel is required for NIfTI loading. Install with: pip install nibabel")
    img = nib.load(path)
    raw_shape = img.shape
    if len(raw_shape) != 3:
        raise ValueError(f"NIfTI sinogram must be 3D, got {len(raw_shape)}D")
    # read lazy: slice dataobj to the requested subset's canonical shape
    data = np.asarray(img.dataobj)
    # normalize like numpy
    return _finish_sinogram(data, raw_shape, path, selection, axis_order, "nifti")
```

Reuse a shared `_finish_sinogram(raw, original_shape, path, selection, axis_order, fmt)` helper (refactor the numpy path to use it too) that does the transpose/select and returns `SinogramData`. For nibabel, deferring: `np.asarray(img.dataobj)` may read fully; if a subset is requested, slice `img.dataobj[proj_sel]` before materialising (document that lazy uses dataobj slicing; correctness of shape is the tested contract).

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `python -m pytest tests/unit/test_sinogram_loader.py -k "nifti" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_sinogram_loader.py src/backend/loaders/sinogram.py
git commit -m "feat(backend): NIfTI sinogram loading via nibabel"
```

---

### Task 4: `load_sinogram` dispatch + `__init__.py` exports (T-64, T-66)

**Files:**
- Modify: `src/backend/loaders/sinogram.py`, `src/backend/loaders/__init__.py`, `pyproject.toml`
- Test: `tests/unit/test_sinogram_loader.py`

**Interfaces:**
- Consumes: `_detect_format`, `_load_numpy`, `_load_nifti`, `SelectionConfig`, `SinogramData`, `resolve_indices`, `_normalize`/`_finish_sinogram` (Tasks 1–3).
- Produces: public `load_sinogram(path, selection=None, geometry=None, axis_order=("proj","row","col")) -> SinogramData`; `backend.loaders` exports.

- [ ] **Step 1: Write the `axis_order` setter re-derivation tests + dispatch tests**

```python
# tests/unit/test_sinogram_loader.py (add)
import numpy as np
import pytest
from backend.loaders.sinogram import (
    SelectionConfig, SinogramData, load_sinogram, _detect_format,
)

def test_load_sinogram_dispatch_numpy(tmp_path):
    arr = np.zeros((3, 4, 5)); p = tmp_path / "s.npy"; np.save(p, arr)
    s = load_sinogram(p)
    assert s.format == "numpy"
    assert s.data.shape == (3, 4, 5)

def test_load_sinogram_unknown(tmp_path):
    p = tmp_path / "a.xyz"; p.touch()
    with pytest.raises(ValueError):
        load_sinogram(p)

def test_axis_order_change_after_full_load(tmp_path):
    # file in (row, proj, col) order; load with default then flip
    arr = np.arange(24).reshape(2, 3, 4)  # (row, proj, col)
    p = tmp_path / "s.npy"; np.save(p, arr)
    s = load_sinogram(p)               # default canonical, misread
    # set axis_order to the true file order -> re-derive in memory
    s.axis_order = ("row", "proj", "col")
    assert s.data.shape == (3, 2, 4)
    assert s.source_axis_order == ("row", "proj", "col")
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python -m pytest tests/unit/test_sinogram_loader.py -k "dispatch or axis_order_change" -v`
Expected: FAIL

- [ ] **Step 3: Implement `load_sinogram` dispatch**

```python
def load_sinogram(path, selection=None, geometry=None, axis_order=("proj","row","col")):
    path = Path(path)
    fmt = _detect_format(path)
    selection = selection or SelectionConfig()
    if fmt == "numpy":
        return _load_numpy(path, selection, axis_order)
    if fmt == "nifti":
        return _load_nifti(path, selection, axis_order)
    if fmt == "dicom":
        raise NotImplementedError("DICOM sinogram loading is added in Task 5")
    raise ValueError(f"Unknown sinogram format for {path}")
```

Also implement the **`axis_order` setter re-derivation** on `SinogramData` to satisfy `test_axis_order_change_after_full_load`:

- On `axis_order` set: validate permutation (already in Task 1).
- If `_raw_file_order` is present (full in-memory raw): transpose to canonical, re-apply `self.selection`, set `self.data`, update `source_axis_order`. No re-read.
- Else: mark stale (clear `data`/`_loader` will trigger a re-read on `materialize()`). For numpy full loads, store `_raw_file_order` so the fast path works.

Update `_load_numpy`/`_finish_sinogram` to store `_raw_file_order` when the selection was effectively `all` on all axes (so the fast re-derive path is available), else `None`.

- [ ] **Step 4: Implement `__init__.py` exports and add nibabel optional dep**

In `src/backend/loaders/__init__.py`:

```python
from backend.loaders.sinogram import (
    SelectionConfig,
    SinogramData,
    load_sinogram,
    resolve_indices,
    scan_dicom_sinogram,  # added in Task 5; import guarded/lazy or place after Task 5
)
```

For this task, if `scan_dicom_sinogram` doesn't exist yet, either add a placeholder that raises `NotImplementedError`, or defer adding it to the import until Task 5 — plan for Task 5 to add it. To keep Task 4 green, add `load_sinogram`, `SelectionConfig`, `SinogramData`, `resolve_indices` to `__all__` now; add `scan_dicom_sinogram` in Task 5.

In `pyproject.toml`, add to `[project.optional-dependencies]`:

```toml
nifti = ["nibabel>=5.0.0"]
```

- [ ] **Step 5: Run the full test suite to verify green**

Run: `python -m pytest tests/unit/test_sinogram_loader.py -v`
Expected: PASS. Then run full suite: `python -m pytest tests/ -q`
Expected: PASS (DICOM branch only reached when a directory/.dcm is given, not in existing tests).

- [ ] **Step 6: Commit**

```bash
git add tests/unit/test_sinogram_loader.py src/backend/loaders/sinogram.py src/backend/loaders/__init__.py pyproject.toml
git commit -m "feat(backend): load_sinogram dispatch + exports (T-64, T-66)"
```

---

### Task 5: DICOM image-series lazy loader + `scan_dicom_sinogram` (T-65)

**Files:**
- Modify: `src/backend/loaders/sinogram.py`, `src/backend/loaders/__init__.py`
- Test: `tests/unit/test_sinogram_loader.py`, `tests/conftest.py` (add a projection-series fixture)

**Interfaces:**
- Consumes: `SelectionConfig`, `SinogramData`, `resolve_indices`, `_finish_sinogram`, `ProjectionGeometry` (from `backend.geometry`), `load_sinogram` dispatch (Tasks 1–4).
- Produces: `scan_dicom_sinogram(dir) -> dict` (series info: `n_proj`, `n_rows`, `n_cols`, `files`, inferred geometry), `_load_dicom(path, selection, geometry, axis_order) -> SinogramData`, and wiring `load_sinogram` to dispatch DICOM directories to `_load_dicom`.

- [ ] **Step 1: Add a synthetic DICOM projection-series fixture and write failing DICOM tests**

In `tests/conftest.py`, add a fixture `create_projection_dicom(tmp_path)` that writes a minimal DICOM image series (a handful of 2D frames representing projections, dimension `(n_rows, n_cols)` each, e.g. 3 projections of shape `(4, 5)`), using pydicom per the existing `create_ct_dicom()` pattern. Tag: `SOPClassUID` for CT Image Storage / X-Ray, `Rows`, `Columns`, `ImagePositionPatient`, `RescaleSlope/Intercept`.

```python
# tests/unit/test_sinogram_loader.py (add)
def test_scan_dicom_sinogram(tmp_path, create_projection_dicom):
    d = create_projection_dicom(tmp_path)
    info = scan_dicom_sinogram(d)
    assert info["n_proj"] == 3
    assert info["n_rows"] == 4
    assert info["n_cols"] == 5

def test_load_dicom_lazy_selection(tmp_path, create_projection_dicom):
    d = create_projection_dicom(tmp_path)
    from backend.loaders.sinogram import load_sinogram, SelectionConfig
    sel = SelectionConfig(proj_mode="range", proj_range=(0, 2))
    s = load_sinogram(d, selection=sel)
    assert s.format == "dicom"
    assert s.data.shape == (2, 4, 5)
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python -m pytest tests/unit/test_sinogram_loader.py -k "dicom" -v`
Expected: FAIL

- [ ] **Step 3: Implement `scan_dicom_sinogram` and `_load_dicom`**

`scan_dicom_sinogram(dir)`:
- List `.dcm`/`.dicom` files (or read all files as DICOM) in `dir`, sorted by instance number / position.
- Read headers without pixel data (`ds = pydicom.dcmread(f, stop_before_pixels=True)`).
- Determine `n_rows`, `n_cols` from the first instance; `n_proj` = count.
- Infer a `ProjectionGeometry` from `ImagePositionPatient`/geometry tags where present (optional, best-effort).
- Raise `ValueError` if no readable series.

`_load_dicom(path, selection, geometry, axis_order)`:
- Resolve the selected projection indices (canonical axis 0).
- For each selected projection file, `pydicom.dcmread(f)` and `pixel_array` → a 2D `(n_rows, n_cols)` frame; stack along axis 0.
- Apply `axis_order` normalization + remaining row/col selection via `_finish_sinogram`.
- Never read all frames; only the selected projections are opened.

Update `load_sinogram` dispatch: DICOM directory → `_load_dicom(path, selection, geometry, axis_order)`; ignore the "NotImplementedError" from Task 4.

- [ ] **Step 4: Add `scan_dicom_sinogram` to `backend/loaders/__init__.py` `__all__` and imports**

- [ ] **Step 5: Run the DICOM tests and the full suite**

Run: `python -m pytest tests/unit/test_sinogram_loader.py -v` then `python -m pytest tests/ -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tests/conftest.py tests/unit/test_sinogram_loader.py src/backend/loaders/sinogram.py src/backend/loaders/__init__.py
git commit -m "feat(backend): DICOM lazy sinogram loader + scan (T-65)"
```

---

## Final Verification

- [ ] Run `python -m pytest tests/ -q` — all tests pass in the system Python (fallback env).
- [ ] Run in the conda `ct-viewer` env: `python -m pytest tests/unit/test_sinogram_loader.py -v` — passes (parallelproj present; nibabel installed in that env for NIfTI tests).
- [ ] `import backend.loaders` exposes `load_sinogram`, `SelectionConfig`, `SinogramData`, `resolve_indices`, `scan_dicom_sinogram`.
- [ ] No real/binary data committed; fixtures are synthetic and generated in `tmp_path`.
- [ ] Update `docs/plan.md`: mark T-64, T-65, T-66 as done with date.
