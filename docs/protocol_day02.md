# Day 02 Protocol — CTOrientationViewer
**Datum:** Do, 15.10.2026  
**Phase:** Phase 1 — Kern (Tag 2)

---

## 🎯 Goals

| Task | Beschreibung | Status |
|------|--------------|--------|
| T-10 | Volume-Dataclass | ✅ |
| T-13 | Windowing | ✅ |

---

## ✅ Completed Tasks

### T-10 — Volume Dataclass

**Dateien:**
- `src/visualization/volume.py` — Volume dataclass mit Validierung
- `src/visualization/__init__.py` — Exports
- `tests/visualization/test_volume.py` — 10 Tests

**Features:**
- 2D und 3D Arrays unterstützt
- dtype: int16, uint16, float32
- Spacing/Origin Validierung (Länge, positive Werte, finiteness)
- Negative Werte erlaubt (HU für Luft = -1000)
- Unit-agnostic: Volume macht keine Annahmen über Einheiten

**Design-Entscheidungen:**
- Negativ-Clipping entfernt (CT-HU können negativ sein)
- Loaders sind verantwortlich für korrekte Konvertierung
- `meta["unit"]` kann Einheit speichern ("HU", "1/mm", "1/cm")

### T-13 — Windowing

**Dateien:**
- `src/visualization/windowing.py` — Windowing-Funktionen
- `tests/visualization/test_windowing.py` — 7 Tests

**Features:**
- `apply_window(array, center, width)` → uint8 [0, 255]
- `apply_window_with_preset(array, window)` — preset name oder tuple
- Presets: lung (-600/1500), abdomen (40/400), bone (400/1800), brain (40/80)
- Runding für exakte Fenstergrenzen

---

## 🔬 AAPM-Daten Analyse (Nebenbefund)

**Pfad analysiert:** `O:\imageDataCT\Laura\data_lowDose_aapm\1mm B30-selected\full_1mm\L067\full_1mm`

**Ergebnis:**
- 560 IMA-Dateien (GE DICOM)
- 512 × 512 Pixel
- Raw: uint16 (0 bis ~2666)
- HU nach RescaleSlope=1, Intercept=-1024: -1024 bis ~1642

**Wichtig:** Diese Daten sind bereits rekonstruierte Schnittbilder, keine Sinogramme.

---

## 📋 Plan Updates

| Änderung | Details |
|----------|---------|
| T-10 erweitert | 2D erlaubt, uint16 erlaubt, negative Werte erlaubt |
| T-13 erweitert | `apply_window_with_preset` mit preset name oder tuple |

---

## 🚀 Next Steps (Day 03)

1. **T-11** — DICOM-Loader
2. **T-12** — NPY-Loader

---

## Notes

- Volume ist unit-agnostic — die Konvertierung (HU, Attenuation) passiert in den Loadern
- Negativ-Werte sind für CT korrekt (LUft = -1000 HU)
- Windowing rundet Ergebnisse für exakte Grenzen
