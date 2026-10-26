# CTOrientationViewer Documentation

## 📁 Directory Structure

```
docs/
├── README.md                    ← This file
├── plan.md                      ← Main implementation plan (T-01 to T-44)
├── plan_day01.md               ← Phase 0 detailed plan (T-01 to T-04)
├── data.md                      ← Data documentation (AAPM challenge, etc.)
├── geometry.md                  ← Projection geometry definition
├── testing-setup-hint.md       ← Testing setup hints
│
├── protocol_*.md               ← Daily work protocols
│   ├── protocol_day01.md       ← Oct 14, 2026
│   ├── protocol_day02.md       ← Oct 15, 2026
│   ├── protocol_day03.md       ← Oct 16, 2026
│   ├── protocol_day04.md       ← Oct 23, 2026
│   └── protocol_day05.md       ← Oct 26, 2026 (Projection Geometry)
│
├── progress/                   ← Progress reports
│   └── 2026-10-16-streamlit-app.md
│
├── issues/                     ← Issue tracking
│   └── 4-streamlit-progress-bar.md
│
└── superpowers/                ← Superpowers workflow documentation
    ├── specs/
    │   └── 2026-10-26-projection-geometry-design.md
    │
    └── plans/
        ├── 2026-10-15-tag2-volume-windowing.md
        ├── 2026-10-16-tag3-loaders.md
        ├── 2026-10-19-mpr-reslicing.md
        ├── 2026-10-26-projection-geometry-implementation.md
        ├── 2026-10-26-projection-geometry-3d-visualization.md
        └── 2026-10-26-docker-self-deployment.md
```

---

## 📋 Main Plans

### 1. Master Plan (`plan.md`)
- **Purpose:** Overall project implementation plan
- **Tasks:** T-01 to T-44 (Phase 0 to Phase 4)
- **Status:** Phase 1-3 complete, Phase 4 pending

### 2. Day 01 Plan (`plan_day01.md`)
- **Purpose:** Phase 0 detailed tasks (License, Hygiene, Data Guards)
- **Tasks:** T-01, T-02, T-03, T-04
- **Status:** ✅ Complete (Oct 14, 2026)

---

## 📅 Daily Protocols

| Day | Date | Focus | Key Deliverables |
|-----|------|-------|------------------|
| Day 01 | Oct 14 | Phase 0: License & Hygiene | LICENSE, NOTICE, SECURITY.md, data guards |
| Day 02 | Oct 15 | Phase 1: Core (T-10, T-13) | Volume dataclass, Windowing |
| Day 03 | Oct 16 | Phase 1-2 (T-11, T-12, T-20) | DICOM/NPY loaders, Streamlit app |
| Day 04 | Oct 23 | Phase 2-3 (T-21, T-30, T-33) | Series selection, fixtures, check_aapm.py |
| Day 05 | Oct 26 | Projection Geometry | ProjectionGeometry, loaders, trajectory functions |

---

## 🗂️ Documentation Categories

### Core Documentation
| File | Description |
|------|-------------|
| `data.md` | AAPM Challenge data documentation, citation requirements |
| `geometry.md` | Projection geometry parameters, coordinate system |
| `testing-setup-hint.md` | Testing setup hints |

### Superpowers Workflows
| File | Description | Status |
|------|-------------|--------|
| `2026-10-15-tag2-volume-windowing.md` | Windowing implementation | ✅ Done |
| `2026-10-16-tag3-loaders.md` | DICOM/NPY loaders | ✅ Done |
| `2026-10-19-mpr-reslicing.md` | MPR reslicing implementation | ✅ Done |
| `2026-10-26-projection-geometry-implementation.md` | ProjectionGeometry class | ✅ Done |
| `2026-10-26-projection-geometry-3d-visualization.md` | 3D trajectory visualization | 🔄 In Progress |
| `2026-10-26-docker-self-deployment.md` | Docker self-deployment | ❌ Pending |

### Issues
| File | Description | Status |
|------|-------------|--------|
| `4-streamlit-progress-bar.md` | Progress bar display issue | ✅ Solved |

### Superpowers Specs
| File | Description |
|------|-------------|
| `2026-10-26-projection-geometry-design.md` | ProjectionGeometry design spec |

---

## ✅ Project Status

### Completed Phases
- **Phase 0:** License & Hygiene (T-01 to T-04) ✅
- **Phase 1:** Core - Volume, Loaders, Windowing (T-10 to T-14) ✅
- **Phase 2:** App - Streamlit, Series Selection, Phantom (T-20 to T-23) ✅
- **Phase 3:** Tests - Fixtures, Loader tests, Windowing tests (T-30 to T-33) ✅

### Pending Phases
- **Phase 4:** Deployment (T-40 to T-44)
  - T-40: Dockerfile ❌
  - T-41: CI ❌
  - T-42: README ❌
  - T-43: Requirements ❌
  - T-44: Deployment ❌

### In Progress
- Projection Geometry 3D Visualization (superpowers plan)
- Docker Self-Deployment (superpowers plan)

---

## 🔗 External Links

- [AAPM Low-Dose CT Challenge 2016](https://www.aapm.org/grandchallenge/lowdosect/)
- [pydicom Documentation](https://pydicom.github.io/)
- [Streamlit Documentation](https://docs.streamlit.io/)
