# Backend Restructure — Design Specification

**Date:** 2026-11-04
**Status:** Draft
**Author:** BeamStudio Team

## 1. Overview

### Goal

Restructure the package layout so that the **numerical / data backend** lives
in `src/backend/` and the **UI layer** (`Streamlit` / `Plotly`) lives in
`src/visualization/`, with a clean **one-way dependency**: `visualization`
imports from `backend`; `backend` never imports from `visualization`.

### Motivation

Today `src/backend/` only contains the new `parallelproj/` integration, while
the main numerical code it depends on (`Volume`, `ProjectionGeometry`,
`forward_project`) still lives under `src/visualization/`. This inverts the
natural dependency: `backend/parallelproj` already references
`visualization.geometry.ProjectionGeometry` and `visualization.volume.Volume`,
so the "backend" imports the "viewer". This restructure makes the boundary
explicit and correct.

## 2. Target Layout

```
src/
├── backend/
│   ├── __init__.py          # Public exports (Volume, ProjectionGeometry, forward_project, parallelproj)
│   ├── volume.py            # ← moved from visualization/volume.py      (Volume dataclass)
│   ├── geometry.py          # ← moved from visualization/geometry.py    (ProjectionGeometry + YAML/TXT loaders)
│   ├── forward_project.py   # ← moved from visualization/forward_project.py
│   ├── loaders/
│   │   ├── __init__.py      # ← moved from visualization/loaders/__init__.py
│   │   ├── dicom.py         # ← moved from visualization/loaders/dicom.py
│   │   ├── npy.py           # ← moved from visualization/loaders/npy.py
│   │   └── projection.py    # ← moved from visualization/loaders/projection.py
│   └── parallelproj/        # existing (unchanged code; docstring refs updated)
│
└── visualization/           # UI only
    ├── __init__.py
    ├── app.py
    ├── sidebar.py
    ├── volume3d.py
    ├── mpr.py
    ├── phantom.py
    ├── volume_cache.py
    ├── windowing.py
    └── views/
```

### What moves

| Module | From | To |
|--------|------|----|
| `Volume` dataclass | `visualization/volume.py` | `backend/volume.py` |
| `ProjectionGeometry` + loaders | `visualization/geometry.py` | `backend/geometry.py` |
| forward projection | `visualization/forward_project.py` | `backend/forward_project.py` |
| data loaders (dicom, npy, projection) | `visualization/loaders/` | `backend/loaders/` |

### What stays (UI)

`app.py`, `sidebar.py`, `volume3d.py`, `mpr.py`, `phantom.py`,
`volume_cache.py`, `windowing.py`, `views/` remain under `visualization/` and
import `Volume` / geometry / forward projection from `backend`.

## 3. Dependency Rule

- **One-way:** `visualization` → `backend`. No `backend → visualization`
  imports, in code or docstrings.
- Update the docstring references in `backend/parallelproj/geometry.py` and
  `backend/parallelproj/shape.py` that currently point at
  `visualization.geometry` / `visualization.volume`.

## 4. Key Fixes

### 4.1 Lazy `parallelproj` import (eager-import bug)

Today `import backend` fails outright when `parallelproj` is not installed:
`backend/__init__.py` eagerly does `from . import parallelproj`, and
`parallelproj/__init__.py` eagerly imports `projector` → `parallelproj`.

Once `backend` is the home of `Volume` / `ProjectionGeometry`, `import backend`
**must** succeed in the plain environment (no parallelproj), because the UI and
tests import those types via `backend`. Therefore:

- `backend/__init__.py` imports `Volume`, `ProjectionGeometry`, and
  `forward_project` eagerly (these have no hard third-party deps except numpy),
  and imports `parallelproj` only lazily / guarded, mirroring the existing
  `PARALLELPROJ_AVAILABLE` pattern in `forward_project.py`.

### 4.2 Packaging

`pyproject.toml` `[tool.setuptools.packages.find]` currently only
`include = ["visualization*"]`. Add `backend*` so the package ships.

## 5. Import Updates (by file)

All moved modules change their *own* intra-package imports to the new
`backend.*` paths, and all remaining `visualization` consumers + tests +
scripts change their imports to `backend.*`.

### Backend modules (self-imports)

| File | Old import | New import |
|------|-----------|------------|
| `backend/forward_project.py` | `from visualization.geometry import ProjectionGeometry`<br>`from visualization.volume import Volume` | `from backend.geometry import ProjectionGeometry`<br>`from backend.volume import Volume` |
| `backend/loaders/__init__.py` | `from visualization.loaders.dicom import ...`<br>`from visualization.volume import Volume` | `from backend.loaders.dicom import ...`<br>`from backend.volume import Volume` |
| `backend/loaders/dicom.py` | `from visualization.volume import Volume` | `from backend.volume import Volume` |
| `backend/loaders/npy.py` | `from visualization.volume import Volume` | `from backend.volume import Volume` |
| `backend/loaders/projection.py` | `from visualization.geometry import ...` | `from backend.geometry import ...` |

### Visualization consumers (import from backend)

| File | Change |
|------|--------|
| `visualization/loaders/__init__.py` *(deleted)* | — |
| `visualization/mpr.py` | `from visualization.volume import Volume` → `from backend.volume import Volume` |
| `visualization/phantom.py` | `from visualization.volume import Volume` → `from backend.volume import Volume` |
| `visualization/__init__.py` | re-export `Volume` from `backend.volume` (keeps `from visualization import Volume`) |
| `app.py`, `volume3d.py`, `volume_cache.py`, `sidebar.py`, `views/` | no volume/geometry import changes (they receive instances) — verify |

### Tests

| File | Change |
|------|--------|
| `tests/unit/test_forward_project.py` | `visualization.{volume,geometry,forward_project}` → `backend.*` |
| `tests/unit/test_geometry.py` | `visualization.geometry` → `backend.geometry` |
| `tests/unit/test_geometry_trajectory.py` | `visualization.geometry` → `backend.geometry` (keep `visualization.volume3d`) |
| `tests/unit/test_mpr.py` | `visualization.volume` → `backend.volume` |
| `tests/unit/test_volume.py` | `visualization.volume` → `backend.volume` |
| `tests/unit/test_app_integration.py` | `visualization.volume` → `backend.volume` |
| `tests/unit/test_parallelproj.py` | already `backend.parallelproj` — no change |

### Scripts

| File | Change |
|------|--------|
| `scripts/forward_projection_plot.py` | `visualization.{forward_project,geometry,volume}` → `backend.*` |

## 6. Out of Scope (stays in visualization)

- `phantom.py`, `windowing.py`, `mpr.py`, `volume3d.py`, `volume_cache.py` are
  **not** moved in this restructure. They are UI / demo / display concerns and
  the user's stated intent ("backend is forward projection, geometry" + loaders)
  does not include them. They only receive `Volume` instances and continue to
  import the `Volume` type from `backend`.

## 7. Verification

- `import backend` succeeds **without** `parallelproj` installed (lazy import).
- `import visualization` succeeds in the plain env.
- Full `pytest` suite passes.
- No `backend → visualization` import remains (grep check).
