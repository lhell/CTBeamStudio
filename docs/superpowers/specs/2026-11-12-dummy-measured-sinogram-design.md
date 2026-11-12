# Dummy Measured Sinogram — Design (T-93)

Date: 2026-11-12
Status: implemented

## Goal

A synthetic **"measured" sinogram** for the demo phantom — 3D Shepp-Logan
forward projection + scatter + Poisson noise — behind one button in the
Measurements panel, as a coherent demo trio (volume + geometry + measurement)
so the Sinogram Inspection comparison (measured vs simulated, difference,
per-slice metrics) can be exercised without real scanner data.

## Non-goals

- No reconstruction (FDK, T-76). The dummy is an input for the existing
  comparison workflow.
- No change to the shared demo volume/geometry defaults. The pre-existing
  quirk that `create_shepp_logan_hu()` uses origin `(0, 0, 0)` (which parks
  the head in the +x/+y/+z octant relative to the parallelproj rotation axis)
  is left for its own task; the dummy centers **its** copy instead.
- No committed binary data files (`.npy`/`.npz` are gitignored and the CI
  data-guard fails on them).

## Measurement model

Simulated in three steps (`create_dummy_measured_sinogram()` in
`src/visualization/phantom.py`):

1. **Ideal forward projection.** The standard-size Shepp-Logan head
   (`create_shepp_logan_hu()`: 256 × 256 × 64, spacing (3.0, 0.75, 0.75),
   ~138 × 184 × 180 mm) is converted HU → 1/mm at `energy_kev` (default 70,
   matching the FP slider default) and projected with the dummy geometry.
   Output: line integrals `(n_proj, n_rows, n_cols)`.
2. **Scatter.** A Gaussian-blurred copy of the primary transmittance
   `T = exp(-p)`, added in the intensity domain with scatter-to-primary ratio
   `spr` (default 0.3). The blur width `scatter_sigma_mm` (default 25 mm) is
   given at the detector and converted per axis, so the blur is isotropic in
   mm despite anisotropic detector spacing; no blur along the projection axis
   (scatter is per-frame). Scatter adds counts, so the measured line integral
   is **lower** than the ideal one — the contrast-loss/cupping direction.
3. **Quantum noise.** Poisson-distributed counts with `i0` incident photons
   per ray (default 1e5); rays that would see fewer than one photon floor at
   one count (photon starvation), so the log never returns inf. `seed`
   (default 42) makes the dummy reproducible; `None` gives fresh noise.

## Dummy geometry

`create_dummy_geometry()`: SDD 1000 mm, SID 500 mm, detector 512 × 192 at
1.0 × 2.0 mm, 60 views/rotation, circular (pitch 0). Rationale:

- The default 64-row detector covers only ~32 mm of z at the isocenter
  (64 × 1 mm × SID/SDD) — a head-sized phantom would be cropped to a slab.
- 192 rows × 2 mm cover 192 mm of z at the isocenter: the whole ~180 mm tall
  head plus margin. 512 columns × 1 mm cover 256 mm in-plane (head diagonal
  ~230 mm fits).
- 60 views keep the demo stack small while remaining a plausible scanner.

The phantom is **centered on the rotation axis** (origin ≈
(−95.625, −95.625, −94.5) mm): the parallelproj cone circles the isocenter at
the world origin, and the demo default origin `(0, 0, 0)` was measured to put
the head outside the in-plane FOV and half outside the cone in z.

## Ideal-FP disk cache

The forward projection is the only expensive step (measured, CPU-only, no
CUDA in `ct-viewer`: ~10 s off-axis, ~20 s centered; scatter+noise ~3 s).
The ideal projection is therefore cached:

- File: `data/cache/dummy_fp_standard.npz` (gitignored `data/` directory,
  same pattern as `geometry_cache.py`). Measured size: 4.0 MB compressed
  (23.6 MB raw float32).
- Fingerprint: SHA-256 over cache version + phantom spec + geometry fields +
  energy. Any mismatch regenerates and overwrites.
- Only the standard phantom (`volume=None`) is cached; a custom volume always
  re-projects and never touches the cache.
- Scatter and noise are applied **live** on every call, so changing
  `spr`/`i0`/`seed` never triggers a re-projection.
- First generation ~13–23 s (spinner); every later click/app start ~3.5 s.

## UI wiring

Button "🎲 Generate dummy measurement" at the bottom of the Measurements
expander. On click it seeds session state with the trio — volume,
projection geometry (`geometry_is_default=False`, `geometry_loaded_original`
point at the dummy geometry; the geometry JSON cache is deliberately **not**
written, the trio is session-scoped), sinogram — and presets the FP selection
widgets (`fp_proj_mode`/`fp_row_mode`/`fp_col_mode`) to `"all"`: the dummy
contains the full detector and every projection of its geometry, so one click
on "Run Forward Projection" reproduces the measurement shape exactly and the
difference column + per-slice metrics go live immediately.

The sinogram is an in-memory `SinogramData` with `format="synthetic"`,
`path=None`, canonical axes — the T-90 `axis_order` setter branch for
file-less data transposes it in place, reversibly.

## Tests

`tests/test_dummy_measurement.py` (16 tests, real generator on a tiny
phantom/geometry; caches redirected to `tmp_path`): geometry coverage of the
standard head, trio coherence, standard physical size + centering of the
default volume, seed reproducibility, scatter direction, `spr=0` ≈ pure
Poisson around the ideal FP, starvation floor at `ln(i0)`, in-memory axis
reordering, cache round-trip/invalidation, parameter validation.
`tests/integration/test_ui_smoke.py` (3 tests): button presence, seeded
coherent pair + fp-mode preset, override of previously loaded data (generator
stubbed via monkeypatch — the lazy import inside the handler resolves the
patched module attribute).
