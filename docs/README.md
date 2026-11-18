# CTOrientationViewer Documentation

## 📁 Directory Structure

```
AGENTS.md                      ← Agent instructions (env, commands, hard rules)
LINTING.md                     ← Lint order, ignore set
INSTALLATION.md                ← Installation, all platforms
docs/
├── README.md                    ← This file
├── plan.md                      ← Main implementation plan (task ledger, German)
├── data.md                      ← Data documentation (AAPM challenge, etc.)
├── geometry.md                  ← Projection geometry definition
├── local-environment.md        ← This workstation: conda paths, test/lint commands
├── testing-setup-hint.md       ← Testing setup hints
├── versioning.md               ← Git + Docker release versioning
│
├── progress/                    ← Daily protocols and plans
│   ├── plan_day01.md           ← Phase 0 detailed plan (T-01 to T-04)
│   ├── protocol_day01.md       ← Oct 14, 2026
│   ├── protocol_day02.md       ← Oct 15, 2026
│   ├── protocol_day03.md       ← Oct 16, 2026
│   ├── protocol_day04.md       ← Oct 23, 2026
│   ├── protocol_day05.md       ← Oct 26, 2026
│   └── protocol_day06.md       ← Oct 27, 2026
│
├── research/                    ← Research notes and papers
│   └── phantomless-geometry-calibration-helix-cbct.md
│
├── issues/                     ← Issue tracking
│   └── 4-streamlit-progress-bar.md
│
└── superpowers/                ← Superpowers workflow documentation
    ├── specs/
    │   └── 2026-10-26-projection-geometry-design.md
    │
    └── plans/
        ├── 2026-10-15_tag2_volume_windowing.md
        ├── 2026-10-16_tag3_loaders.md
        ├── 2026-10-19_mpr_reslicing.md
        ├── 2026-10-26_projection_geometry_implementation.md
        ├── 2026-10-26_projection_geometry_3d_visualization.md
        ├── 2026-10-26_docker_self_deployment.md
        └── 2026-10-27_parallelproj_forward_projection.md
```

---

## 📋 Main Plans

### 1. Master Plan (`plan.md`)
- **Purpose:** Overall project implementation plan
- **Tasks:** T-01 to T-107, phases 0-12 plus timeline and decision log
- **Structure:** tasks are filed by theme (phase), numbers stay stable — see
  `plan.md#phasen-themen-und-nummernkreise`

---

## 📅 Daily Protocols

| Day | Date | Focus | Key Deliverables |
|-----|------|-------|------------------|
| Day 01 | Oct 14 | Phase 0: License & Hygiene | LICENSE, NOTICE, SECURITY.md, data guards |
| Day 02 | Oct 15 | Phase 1: Core (T-10, T-13) | Volume dataclass, Windowing |
| Day 03 | Oct 16 | Phase 1-2 (T-11, T-12, T-20) | DICOM/NPY loaders, Streamlit app |
| Day 04 | Oct 23 | Phase 2-3 (T-21, T-30, T-33) | Series selection, fixtures, check_aapm.py |
| Day 05 | Oct 26 | Projection Geometry | ProjectionGeometry, loaders, trajectory functions |
| Day 06 | Oct 27 | Trajectory Visualization | Detector planes, direction arrows, helical support |

---

## 🗂️ Documentation Categories

### Core Documentation
| File | Description |
|------|-------------|
| `../AGENTS.md` | Agent instructions: mandatory conda env, commands, hard rules, test bar |
| `../LINTING.md` | Lint tool order (flake8 → black → isort), ignore set |
| `../INSTALLATION.md` | Installation for Docker, pip, and conda (conda required for parallelproj) |
| `local-environment.md` | This workstation: Miniforge/conda paths, activate commands |
| `data.md` | AAPM Challenge data documentation, citation requirements |
| `geometry.md` | Projection geometry parameters, coordinate system |
| `testing-setup-hint.md` | Testing setup hints |
| `versioning.md` | Git and Docker tag conventions, release procedure, registry immutability |

### Superpowers Workflows
| File | Description | Status |
|------|-------------|--------|
| `2026-10-15_tag2_volume_windowing.md` | Windowing implementation | ✅ Done |
| `2026-10-16_tag3_loaders.md` | DICOM/NPY loaders | ✅ Done |
| `2026-10-19_mpr_reslicing.md` | MPR reslicing implementation | ✅ Done |
| `2026-10-26_projection_geometry_implementation.md` | ProjectionGeometry class | ✅ Done |
| `2026-10-26_projection_geometry_3d_visualization.md` | 3D trajectory visualization | ✅ Done |
| `2026-10-26_docker_self_deployment.md` | Docker self-deployment | ⚠️ Deferred |
| `2026-10-27_parallelproj_forward_projection.md` | Forward projection with parallelproj | 🔄 In Progress |

### Issues
| File | Description | Status |
|------|-------------|--------|
| `4-streamlit-progress-bar.md` | Progress bar display issue | ✅ Solved |

### Superpowers Specs
| File | Description |
|------|-------------|
| `2026-10-26_projection_geometry_design.md` | ProjectionGeometry design spec |

---

## ✅ Project Status

Short version; the authoritative overview is
[`plan.md`](plan.md#phasen-themen-und-nummernkreise).

### Open
- **T-73** — verify the Docker targets in CI (no Docker on this machine)
- **T-74** — run the run-scripts against a real Docker daemon
- **T-105** — push job for `main`/PRs (releases already publish)

### Shelved / dropped
- **T-82** (PyVista render mode), **T-87** (fullscreen per view), **T-56a** (dropped)

### Research backlog
- **T-75** (desktop wrapper), **T-76** (FDK reconstruction),
  **T-77** (phantomless geometry calibration)

---

## 🔗 External Links

- [AAPM Low-Dose CT Challenge 2016](https://www.aapm.org/grandchallenge/lowdosect/)
- [pydicom Documentation](https://pydicom.github.io/)
- [Streamlit Documentation](https://docs.streamlit.io/)
