# CTOrientationViewer Documentation

## 📁 Directory Structure

```
docs/
├── README.md                    ← This file
├── plan.md                      ← Main implementation plan (T-01 to T-75)
├── data.md                      ← Data documentation (AAPM challenge, etc.)
├── geometry.md                  ← Projection geometry definition
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
- **Tasks:** T-01 to T-75 (Phases 0-8)
- **Status:** ~27 tasks done, 15 open

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

### Completed Phases
- **Phase 0:** License & Hygiene (T-01 to T-04) ✅
- **Phase 1:** Core - Volume, Loaders, Windowing (T-10 to T-14) ✅
- **Phase 2:** App - Streamlit, Series Selection, Phantom (T-20 to T-23) ✅
- **Phase 3:** Tests - Fixtures, Loader tests, Windowing tests (T-30 to T-33) ✅
- **Phase 5:** Projection Geometry (T-50 to T-56) ✅

### Completed Phases
- **Phase 0:** License & Hygiene (T-01 to T-04) ✅
- **Phase 1:** Core - Volume, Loaders, Windowing (T-10 to T-14) ✅
- **Phase 2:** App - Streamlit, Series Selection, Phantom (T-20 to T-23) ✅
- **Phase 3:** Tests - Fixtures, Loader tests, Windowing tests (T-30 to T-33) ✅
- **Phase 4:** Deployment (T-40 to T-44) ✅ (local), Docker deferred
- **Phase 5:** Projection Geometry (T-50 to T-56) ✅

### In Progress
- **Phase 6:** Forward Projection (T-61 to T-70) 🔄

### Deferred (Future)
- **Phase 7:** Docker Self-Deployment (T-71 to T-74) - no Docker available
- **Phase 8:** Forward Projection (T-61 to T-70) 🔄
- **T-76:** FDK / Analytische Rekonstruktion
- **T-77:** Phantomlose Geometrie-Kalibrierung (Research)

---

## 🔗 External Links

- [AAPM Low-Dose CT Challenge 2016](https://www.aapm.org/grandchallenge/lowdosect/)
- [pydicom Documentation](https://pydicom.github.io/)
- [Streamlit Documentation](https://docs.streamlit.io/)
