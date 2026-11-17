# Helix Forward-Projection Verification — Design Specification

**Date:** 2026-11-17
**Status:** Implemented
**Task:** T-104 (plan.md — Release Readiness milestone)
**Depends on:** T-63, T-79

## 1. Overview

The helical table feed landed in the forward projection with `b7b7279`
(z feed per projection) without verification tests, and two documentation
spots still describe the pre-helix state. This task pins the helix behaviour
with tests and syncs the docs. No production code change is expected — the
tests exist to prove the current behaviour and catch regressions; the only
code touched would be `src/backend/forward_project.py` if the tests expose a
gap.

### Goals

- `pitch > 0` measurably shifts projections along z, reproducibly, with the
  documented `z_step` formula pinned through the public API.
- `pitch = 0` stays exactly circular (bit-identical to the pre-helix path).
- The helix forward projection and the 3D trajectory
  (`visualization.volume3d.get_trajectory_positions` with `pitch > 0`) agree.
- `docs/geometry.md` describes the implemented helix z feed.

### Non-goals

- No rekonstruction (T-76), no new UI, no change to the pitch semantics
  (D-12: `pitch = 0.0` default = circular scan).

## 2. Current state (what the tests must pin)

### Forward projection (`src/backend/forward_project.py`)

- `z_center = origin_zyx[0] + 0.5 * (n_z - 1) * spacing_z` — the volume's
  z centre; the scan follows the volume's z position.
- `z_step = pitch * n_rows * row_spacing / ppr` for `pitch > 0`, else `0.0`
  (`ppr` = `projections_per_rotation`, `row_spacing` =
  `det_row_spacing_mm`).
- `calculate_xray_beam_list(..., z_offset_mm=z_center, z_step_mm=z_step,
  n_projections_total=n_projections_total or 0)`.

### Beam positions (`src/backend/parallelproj/geometry.py`)

- Per-projection z:
  `z(i) = z_offset - (N / 2) * z_step + i * z_step` with
  `N = n_projections_total` when given (else the number of *selected*
  projections) and `i` = the **original** angle index (not the selection
  position). `z_step == 0` gives a circular scan (constant z).
- The detector rides on z: the detector-row offsets are added on top of
  `z_pos`, so the whole detector plane translates with the table feed.

### 3D trajectory (`src/visualization/volume3d.py::get_trajectory_positions`)

- `z_step = pitch * collimation_width / ppr` (same formula, `collimation_width
  = n_rows * det_row_spacing_mm`); `total_z = z_step * n`;
  `z(i) = z_offset - total_z / 2 + i * z_step`; source angle
  `= i * 360 / ppr`. For a contiguous projection list with
  `n_projections_total = n` these formulas are identical to the forward
  projection's — the drawn helix must sit exactly where the projector
  computes.

## 3. Test design

All new tests live in `tests/unit/test_forward_project.py` (per T-104).
A per-test skip guard (nibabel pattern, not module-level `importorskip`)
keeps the collection of the whole file alive in environments without the
projection backend (CI installs a subset); in `ct-viewer` every test runs.

### Numbers

- Slab volume for the behavioural test: shape `(11, 5, 5)` `(z, y, x)`,
  spacing `(2.0, 1.0, 1.0)`, DICOM origin `(-2, -2, -10)` → z voxel centres
  `-10 … 10`, `z_center = 0`. Exactly one z plane (index 5, centre z = 0)
  carries attenuation `0.02 1/mm`; all other voxels are 0.
- Helix geometry: `n_det_rows = 1`, `n_det_cols = 1` (single central ray —
  the detector z then equals the source z, so the ray lies entirely in the
  plane `z = z(i)`), `projections_per_rotation = 4`, `pitch = 0.75`,
  `det_row_spacing_mm = 16.0` → `z_step = 0.75 * 1 * 16 / 4 = 3.0 mm`.
- Helix z positions over 4 projections centred on `z_center = 0`:
  `z(0..3) = -6, -3, 0, +3`. Only `z = 0` touches the slab; the miss rays
  are ≥ 2 mm from any non-zero voxel centre, so linear interpolation in the
  non-dominant axes cannot pick up slab weight → clean zeros.

### Tests

1. **`test_forward_project_helix_shifts_projections_along_z`**
   (`requires_projection_backend`) — full `forward_project` with the slab
   volume and the helix geometry: projection 2 (`z = 0`) is strictly
   positive; projections 0/1/3 (`z = -6/-3/+3`) are < 1 % of the hit. Run
   twice → `np.array_equal` (reproducible). Pins the `z_step` formula
   end-to-end: any deviation from `z_step = pitch * n_rows * row_spacing /
   ppr` moves a ray onto (or off) the slab.
2. **`test_forward_project_pitch_zero_is_exactly_circular`**
   (`requires_projection_backend`) — same volume, default geometry
   (`pitch = 0`): all four projections (0°/90°/180°/270°) pass through the
   slab at `z = 0` → all positive and equal within 1 % (the ray through the
   isocenter integrates the same slab from four angles).
3. **`test_calculate_xray_beam_list_helix_z_positions_pinned`**
   (`requires_projection_backend`) — geometry-level, exact values. Tiny
   `ConeBeamGeometry` (4 projections, 1 row, 1 col): source z
   `= [4, 7, 10, 13]` for `z_offset = 10`, `z_step = 3`; detector z follows
   (rides on the table feed). With `n_projections_total = 8`:
   `[-2, 1, 4, 7]`. With `projection_indices = [1, 3]` and
   `n_projections_total = 4`: `[7, 13]` — the original angle index drives
   z, not the selection position.
4. **`test_calculate_xray_beam_list_circular_when_z_step_zero`**
   (`requires_projection_backend`) — `z_step_mm = 0.0`: every source and
   detector z equals `z_offset` for any projection index. This is the
   bit-identical pin of the pre-helix path (`forward_project` passes
   `z_step_mm = 0.0` when `pitch = 0`).
5. **`test_forward_project_helix_matches_3d_trajectory`**
   (`requires_projection_backend`) — FP beam starts vs
   `get_trajectory_positions`: geometry `sid = 600, sdd = 1000, 5 × 5
   detector, row spacing 2.0, ppr = 8, pitch = 0.5` → `z_step = 0.625`,
   `z_offset = 25.0`, contiguous 8 projections, `n_projections_total = 8`.
   Source positions (first LOR start per projection) and central-pixel
   detector positions (row 2, col 2 → no pixel offset) must match the 3D
   trajectory within 1e-2 mm (float32 torch tensors vs float64 `math` —
   expected residual ~1e-4 mm at 1000 mm magnitude).

### Acceptance criteria

- All five tests green in `ct-viewer`; zero skips in the env run.
- `pitch = 0` proven identical to the pre-helix circular path (tests 2 + 4).
- Helix FP and 3D trajectory agree (test 5).
- No production code change needed (if a test exposes a gap, the fix lands
  in `src/backend/forward_project.py` and this spec is updated).

## 4. Documentation sync

- `docs/geometry.md`, section *Helical Scanning*: add the implemented
  per-projection z feed (`z_step` formula, helix centred on the volume's
  z centre over the total scan, original-index z, detector rides on z,
  `pitch = 0` → circular) and note that the FP and the 3D trajectory share
  these formulas.
- `docs/geometry.md`, section *Volume Placement in World Coordinates*:
  extend the rotation-axis bullet — with a helix the *scan* is centred on
  the volume's z centre and feeds `z_step` per projection.
- `docs/plan.md`: T-104 status → Done; T-94 "Bekannte Grenze" note closes
  (verification + doc sync done); "Noch offen" entry resolved.
- `AGENTS.md` test bar: baseline updated for the new tests.
