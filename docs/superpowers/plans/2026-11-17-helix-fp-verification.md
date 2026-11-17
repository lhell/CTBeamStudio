# Helix Forward-Projection Verification — Plan

**Date:** 2026-11-17
**Task:** T-104 (plan.md)
**Spec:** `docs/superpowers/specs/2026-11-17-helix-fp-verification-design.md`

## Steps

1. **Spec** — done (see link above).
2. **Tests** in `tests/unit/test_forward_project.py` (5 new, per-test
   `requires_projection_backend` skip guard — nibabel pattern, no
   module-level `importorskip`):
   - Helix z-step formula pinned end-to-end through `forward_project`
     (slab volume, `z_step = 3.0 mm`, only the `z = 0` projection hits).
   - `pitch = 0` exactly circular (all four projections equal, positive).
   - Geometry-level exact z positions (`calculate_xray_beam_list`): helix
     formula, `n_projections_total`, original-index selection, detector
     rides on z; `z_step = 0` → constant z (pre-helix path).
   - FP helix ↔ `get_trajectory_positions` (3D) agreement, sources and
     central-pixel detectors, atol 1e-2 mm.
3. **Doc sync**:
   - `docs/geometry.md`: Helix z feed in *Helical Scanning*; rotation-axis
     bullet in *Volume Placement in World Coordinates*.
   - `docs/plan.md`: T-104 → Done; T-94 boundary note closed; "Noch offen"
     resolved.
   - `AGENTS.md`: test-bar numbers.
4. **Verify**: full suite in `ct-viewer` (`python -m pytest -q -rs`),
   flake8 → black → isort (canonical order).

## Acceptance

- Suite green, 0 skipped in `ct-viewer`; 6 new tests run (not skipped).
- `pitch = 0` bit-identical to the pre-helix circular path.
- Helix FP and 3D trajectory agree.
- `docs/geometry.md` describes the implemented helix z feed.
