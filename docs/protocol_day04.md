# Day 04 Protocol — CTOrientationViewer
**Datum:** Fr, 23.10.2026  
**Phase:** Phase 2 — App (Tag 6)

---

## 🎯 Goals

| Task | Beschreibung | Status |
|------|--------------|--------|
| T-21 | Serienauswahl | ✅ |
| T-30 | Synthetische Fixtures | ✅ |
| T-33 | Datenvalidierungsskript | ✅ |
| T-23 | 3D-Visualisierung (Planung) | 📋 |

---

## ✅ Completed Tasks

### T-21 — Serienauswahl

**Dateien:**
- `src/visualization/app.py`

**Features:**
- Sidebar listet gefundene Serien mit Patient, Beschreibung, Slice-Anzahl
- Format: `{patient_id} - {series_description} - {n_slices} slices`
- Keine Dosisklasse, kein Localizer-Flag

---

### T-30 — Synthetische Fixtures

**Dateien:**
- `tests/conftest.py`

**Features:**
- `create_ct_dicom()` fixture erstellt synthetische CT-DICOM-Dateien
- Alle benötigten DICOM-Tags: ImagePositionPatient, ImageOrientationPatient, RescaleSlope/Intercept, SeriesDescription, etc.
- Keine Binärdaten im Repo

---

### T-33 — Datenvalidierungsskript

**Dateien:**
- `scripts/check_aapm.py`

**Features:**
- Scannt Verzeichnis nach DICOM-Serien
- Tabellarische Ausgabe: Patient ID, Series Description, Slices, Dose Class
- Exit 2 bei fehlendem Verzeichnis oder null Serien
- Warnung, wenn alle Serien `unknown` sind

---

## 📋 T-23 Planung — 3D-Visualisierung

### Detailplan

| Subtask | Beschreibung | Abhängigkeit |
|---------|--------------|--------------|
| T-23.1 | Bibliotheks-Auswahl: PyVista vs Plotly | — |
| T-23.2 | `Volume3D` dataclass erstellen | T-10 |
| T-23.3 | 3D-Volumen-Rendering (Iso-Surface oder Volume-Render, wählbar) | T-23.1 |
| T-23.4 | DICOM-Koordinatensystem-Transformation | T-11 |
| T-23.5 | Röntgenquelle & Detektor visualisieren | T-23.4 |
| T-23.6 | Interaktion: Rotation/Zoom | T-23.3 |
| T-23.7 | Integration in Streamlit-App | T-20 |
| T-23.8 | Tests für volume3d.py | T-30 |

### Technische Entscheidungen

| Entscheidung | Optionen | Favorit |
|--------------|----------|---------|
| 3D-Bibliothek | PyVista, Plotly | PyVista (bessere VTK-Integration für Volumen) |
| Volumen-Darstellung | Dropdown-Menu: "Iso-Surface" (default), "Volume Rendering" | **Beide wählbar, Standard: Iso-Surface** |
| Koordinatensystem | Patient, Slice, Scanner | Patient (DICOM-Standard) |
| Detektor-Positionierung | Fixed SID, berechnet aus Gantry | Fixed SID (1000mm default) |

---

## 📋 Plan Updates

| Änderung | Details |
|----------|---------|
| T-21 erledigt | Serienauswahl in Sidebar |
| T-30 erledigt | Synthetische DICOM-Fixtures |
| T-33 erledigt | check_aapm.py Skript |
| T-23 Detailplan | 8 Subtasks mit Abhängigkeiten dokumentiert |

---

## 🚀 Next Steps

1. **T-23.1** — Bibliotheks-Auswahl treffen (PyVista vs Plotly)
2. **T-40** — Dockerfile
3. **T-41** — CI/CD Pipeline
4. **T-42** — README aktualisieren

---

## Notes

- Heute wurden alle offenen Phase-2 Tasks abgeschlossen
- T-23 ist optional aber Detailplan liegt vor
- Projekt ist nun funktionsfähig mit MPR-Views, Windowing, DICOM/NPY-Loadern
