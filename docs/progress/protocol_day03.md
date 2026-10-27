# Day 03 Protocol — CTOrientationViewer
**Datum:** Fr, 16.10.2026  
**Phase:** Phase 1 — Kern (Tag 3)

---

## 🎯 Goals

| Task | Beschreibung | Status |
|------|--------------|--------|
| T-11 | DICOM-Loader | ✅ |
| T-12 | NPY-Loader | ✅ |
| T-20 | Streamlit-App | ✅ |
| T-22 | Demo-Phantom | ✅ |
| T-31 | Loader-Tests | ✅ |

---

## ✅ Completed Tasks

### T-11 — DICOM-Loader

**Dateien:**
- `src/visualization/loaders/dicom.py`
- `tests/unit/test_dicom_loader.py`

**Features:**
- `scan_series(root)` → gruppiert nach SeriesInstanceUID
- `load_dicom_series(files)` → Volume in HU
- Sortierung über ImagePositionPatient + ImageOrientationPatient
- HU-Konvertierung via RescaleSlope/RescaleIntercept
- Inkonsistentes Spacing (>1%) → ValueError
- Gantry-Tilt → Warning (kein Abbruch)
- `classify_dose()` erkennt full/half/quarter dose
- Auto-Detection: HU vs 1/mm basierend auf dtype und Wertbereich

### T-12 — NPY-Loader

**Dateien:**
- `src/visualization/loaders/npy.py`
- `tests/unit/test_npy_loader.py` (22 Tests)

**Features:**
- `load_npy(path)` — lädt einzelne .npy (2D oder 3D)
- `scan_npy_folder(root)` — findet .npy Dateien, sortiert numerisch
- `load_npy_series(files)` — stackt mehrere 2D/3D Dateien
- Auto-Detection: HU vs 1/mm basierend auf dtype und Wertbereich
- dtype-Erhaltung für HU (slope=1, intercept=-1024) und Identity (slope=1, intercept=0)
- Optionale `unit` und `spacing` Parameter

**Tests:**
- 2D Array Support (wird als single slice behandelt)
- Ordner-Scan mit numerischer Sortierung
- Series-Loading für 2D und 3D Arrays
- Unit-Detection und Force-Unit
- Fehlerbehandlung (falsche Endung, falsche Dimensionen)

### pytest Import-Problem (Fix)

**Problem:** pytest konnte Module nicht importieren (`ModuleNotFoundError: No module named 'visualization.windowing'`)

**Ursache:** pytest fügt automatisch `tests/` zum Python-Path hinzu, was `src/visualization/` shadowed.

**Lösung in `tests/conftest.py`:**
```python
import sys
from pathlib import Path

# Entferne tests/ aus sys.path - es shadowed src/
test_dir = str(Path(__file__).parent.resolve())
if test_dir in sys.path:
    sys.path.remove(test_dir)

# Fuege src/ hinzu
src_path = str((Path(__file__).parent.parent / "src").resolve())
if src_path not in sys.path:
    sys.path.insert(0, src_path)
```

---

## 📋 Plan Updates

| Änderung | Details |
|----------|---------|
| T-11 erweitert | Auto-Detection HU/1/mm hinzugefügt |
| T-12 erstellt | Komplett neuer Loader mit 2D/3D Support |
| T-31 erledigt | Tests für DICOM und NPY vorhanden |
| pytest conftest | Import-Path Fix dokumentiert |

---

## 🚀 Next Steps (Day 04)

1. **T-14** — Reslicing / MPR
2. **T-21** — Serienauswahl
3. **T-23** — 3D-Visualisierung

---

## Notes

- Auto-Detection funktioniert via `_detect_unit()` aus dtype und Wertbereich
- int16 mit Werten > 100 → HU
- float32 mit Werten 0-10 → 1/mm
- NPY-Loader unterstützt jetzt auch Ordner mit mehreren 2D-Slices (wie DICOM)
