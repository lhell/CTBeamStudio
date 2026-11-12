# Sinogram Lazy Subset Reads — Design

Date: 2026-11-12
Status: Implemented (T-92)

## Goal

Loading a sinogram subset (row/col/proj selection) from a large `.npy` or
NIfTI file currently reads the **whole file into RAM** and slices afterwards
(`_load_numpy`, `_load_nifti`). This follows the intent already recorded in
`docs/superpowers/plans/2026-11-04-sinogram-loader.md` (mmap for `.npy`
subsets, `dataobj` slicing for NIfTI subsets) but never implemented.

DICOM is out of scope: `_load_dicom` already reads only the selected
projections' pixel files (T-65), chunked per frame.

## Verified platform behavior (probed on this machine, nibabel 5.5.0)

- `np.load(path, mmap_mode="r")` returns a `memmap`; fancy indexing via
  `np.ix_` on it works and returns a plain `ndarray` copy — only the pages
  covering the selected subset are read from disk.
- `img.dataobj[basic_slice_tuple]` reads only the sliced region in one call;
  correct values. **Fancy indexing is NOT supported** by `ArrayProxy` or
  `img.slicer` (both raise `ValueError/IndexError: Cannot handle fancy
  indexing`).

## Design

New helper `_is_full_selection(selection)`: True iff all three axis modes are
`"all"`. Also reused by `_finish_sinogram`'s `is_full` computation (same
condition, no behavior change).

### `.npy` (`_load_numpy`)

- Full selection → `np.load(path)` (unchanged eager path; `_raw_file_order`
  keeps the in-memory raw array for in-memory `axis_order` re-derivation).
- Subset → `np.load(path, mmap_mode="r")`; the existing
  `_apply_selection` (transpose + `np.ix_`) materializes only the subset.
  `_raw_file_order` stays `None` (not full), so an `axis_order` change
  re-reads from disk through the same lazy path. The memmap is not retained,
  so no Windows file lock persists.
- `.npz` → unchanged eager read (zip containers cannot be memory-mapped).

### NIfTI (`_load_nifti`)

Per file axis `f` with canonical label `axis_order[f]`:

- Mode `central`/`range` with a valid in-bounds non-empty `range_` → pre-slice
  `slice(start, stop)` on disk.
- Mode `downsample` → pre-slice `slice(0, size, step)` (identical index list
  to `resolve_indices`).
- Mode `all` or `custom` → no pre-slice (`custom` needs fancy indexing, which
  the proxy cannot do; it reads fully as before).

Pre-sliced axes are marked `"all"` in an `applied_selection` (the same
pattern the DICOM loader uses), so `_finish_sinogram` applies only the
remaining axes. The full-selection case stays byte-identical to the old
eager `np.asarray(img.dataobj)` path.

Validation is preserved by *falling back* on invalid parameters: an
out-of-bounds or empty `range_` is not pre-sliced, so `_apply_selection`'s
`resolve_indices` raises the same `IndexError`/`ValueError` as before.
`slice()` would otherwise silently clamp out-of-bounds bounds.

`SinogramData.lazy` stays `False` throughout: the selected subset is
materialized after load; laziness is at read time (never read more than the
subset), not at access time.

### Out of scope

- Chunk-wise processing/streaming through forward projection (`SinogramData`
  materializes the selected subset densely; the UI calls `materialize()`).
- DICOM stack preallocation (halves peak memory for full DICOM loads).
- `.npz` partial decompression.

## Tests

`tests/unit/test_sinogram_loader.py`:

- npy subset load passes `mmap_mode="r"` (spied on `np.load`), full load
  passes none; both produce correct subset data.
- NIfTI subset load pre-slices the proxy (spied on
  `ArrayProxy.__getitem__` recording a basic-slice tuple, never a full read);
  range/downsample/transposed-order variants produce data equal to the
  eager slice of the full array.
- NIfTI `custom` selection still loads correctly (full-read fallback).
- NIfTI out-of-bounds range raises `IndexError`, empty range raises
  `ValueError` (fallback preserves the error contract).
