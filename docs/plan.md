

# CT-Viewer — Implementierungsplan

**Projekt:** `Res_Indep_CTO` / `src/visualization/`
**Stand:** 2026-10-14
**Start:** Mi, 2026-10-14

## Leitprinzipien

| Prinzip | Konsequenz |
|---|---|
| Keine Daten im Repo oder Image | nur Phantom + synthetische Fixtures |
| `pydicom` ausschließlich | kein SimpleITK, kein ITK |
| Viewer ohne Torch | separate Dependency-Gruppen |
| Datenintern HU | Normalisierung nur in der Darstellung |

## Phase 0 — Lizenz & Hygiene (Tag 1–2)

### `[x]` T-01 — Lizenzdateien
- **Ziel:** Projekt ist rechtlich veröffentlichbar.
- **Dateien:** `LICENSE` (MIT), `NOTICE`, `../SECURITY.md`
- **Abhängig von:** –
- **Akzeptanz:** Alle drei Dateien im Root; `NOTICE` nennt Fremdlizenzen von `pydicom`, `numpy`, `streamlit`, `pylibjpeg`.

### `[x]` T-02 — Git-Historie prüfen
- **Ziel:** Keine Patientendaten oder Secrets in der Historie.
- **Dateien:** –
- **Abhängig von:** –
- **Akzeptanz:** `git log --all --diff-filter=A --name-only` enthält keine `.dcm`, `.ima`, `.npy`, `.ckpt`, `.env`. Bei Fund: History-Rewrite **vor** dem ersten Push.

### `[x]` T-03 — Daten-Guards
- **Ziel:** Daten können nicht versehentlich veröffentlicht werden.
- **Dateien:** `../.gitignore`, `.dockerignore`, `Dockerfile`, `.github/workflows/ci.yml`
- **Abhängig von:** T-02
- **Akzeptanz:** CI-Job schlägt fehl, wenn eine Testdatei `test.dcm` getrackt wird (lokal einmal verifizieren, dann zurücknehmen).

### `[x]` T-04 — Datendokumentation
- **Ziel:** Zugang und Zitierpflicht dokumentiert.
- **Dateien:** `docs/data.md`, `CITATION.cff`, `configs/datasets/aapm_ldct2016.yaml`
- **Abhängig von:** –
- **Akzeptanz:** `docs/data.md` beschreibt Registrierungsweg der AAPM-Challenge 2016, enthält die wörtlichen Pflichtzitate und den Satz, dass das Repo keine Daten verteilt.

## Phase 1 — Kern (Tag 2–4)

### `[x]` T-10 — `Volume`-Dataclass
- **Ziel:** Gemeinsames Austauschformat aller Loader.
- **Dateien:** `src/visualization/volume.py`
- **Abhängig von:** –
- **Akzeptanz:** Felder `array` (`np.int16`/`float32`, HU, Achsen `(z, y, x)`), `spacing` (mm, `(z, y, x)`), `origin`, `meta: dict`. `__post_init__` validiert Shape- und Spacing-Länge und wirft `ValueError` bei Spacing ≤ 0.

### `[x]` T-11 — DICOM-Loader
- **Ziel:** DICOM-Serie → `Volume` in HU.
- **Dateien:** `src/visualization/loaders/dicom.py`
- **Abhängig von:** T-10
- **Akzeptanz:**
  - `scan_series(root)` gruppiert nach `SeriesInstanceUID`, liefert Patient, `SeriesDescription`, Slice-Anzahl, Dosisklasse.
  - Sortierung über Projektion von `ImagePositionPatient` auf die Schichtnormale aus `ImageOrientationPatient`.
  - HU über `RescaleSlope`/`RescaleIntercept`.
  - Inkonsistentes Slice-Spacing (> 1 % Abweichung) → `ValueError` mit Positionsangabe.
  - Gantry-Tilt (`ImageOrientationPatient` nicht achsparallel) → Warnung, kein Abbruch; in Docstring als v1-Limitation vermerkt.

### `[x]` T-12 — NPY-Loader
- **Ziel:** Vorhandene AAPM-`.npy` laden.
- **Dateien:** `src/visualization/loaders/npy.py`
- **Abhängig von:** T-10
- **Entscheidung:** `preprocess_aapm.py` schreibt **rohe HU** → keine Rückskalierung, nur Plausibilitätsprüfung.
- **Akzeptanz:** 
  - `load_npy(path)` lädt einzelne .npy Datei (2D oder 3D)
  - `scan_npy_folder(root)` findet .npy Dateien, sortiert numerisch
  - `load_npy_series(files)` stackt mehrere 2D/3D Dateien
  - Auto-Detection von HU vs 1/mm basierend auf dtype und Wertbereich
  - Optionale `unit` und `spacing` Parameter

### `[x]` T-13 — Windowing
- **Ziel:** HU → 8-bit Grauwerte.
- **Dateien:** `src/visualization/windowing.py`
- **Abhängig von:** T-10
- **Akzeptanz:** `apply_window(array, center, width)` liefert `uint8`; Presets `lung (-600/1500)`, `abdomen (40/400)`, `bone (400/1800)`, `brain (40/80)`; `width <= 0` → `ValueError`; Clipping ohne Überlauf bei `int16`-Eingang.

### `[x]` T-14 — Reslicing / MPR
- **Ziel:** Axial, koronal, sagittal bei anisotropem Spacing.
- **Dateien:** `src/visualization/mpr.py`
- **Abhängig von:** T-10
- **Akzeptanz:** `extract_slice(volume, plane, index)` gibt Bild **und** In-plane-Spacing zurück; Seitenverhältnis wird aus dem Spacing berechnet, nicht aus der Pixelanzahl. Testfall: Volume mit Spacing `(3.0, 0.7, 0.7)` ergibt im koronalen Schnitt ein Aspect-Ratio von ≈ 4,29.
- **Status:** ✅ Done (Oct 19, 2026)
- **Implementierung:**
  - 3-column MPR layout (axial, coronal, sagittal)
  - Slice sliders + jump buttons (⏮/⏭)
  - Isotropic resampling for correct aspect ratio
  - Hover coordinates via JavaScript
  - Click-to-focus + keyboard navigation (arrows, Home/End, Tab)

## Phase 2 — App (Tag 4–5)

### `[x]` T-20 — Streamlit-App
- **Dateien:** `src/visualization/app.py`, `configs/viewer.yaml`
- **Abhängig von:** T-11, T-13, T-14
- **Akzeptanz:** Ebenenauswahl, Slice-Slider, Window-Presets + manuelle Center/Width-Eingabe; HU-Wert unter dem Cursor oder zumindest Min/Max der aktuellen Schicht sichtbar.
- **Status:** ✅ Done (Oct 19, 2026)
- **Implementierung:**
  - MPR views with sliders
  - Window presets (lung, abdomen, bone, brain) + manual controls
  - Hover coordinates (x,y tooltip on images)
  - Click-to-focus for keyboard navigation
  - Jump buttons (⏮/⏭) for first/last slice
  - Session state persistence

### `[x]` T-21 — Serienauswahl
- **Dateien:** `src/visualization/app.py`
- **Abhängig von:** T-11, T-20
- **Akzeptanz:** Sidebar listet gefundene Serien mit Patient, Beschreibung, Slice-Anzahl (keine Dosisklasse, kein Localizer-Flag).
- **Status:** ✅ Done (Oct 23, 2026)
- **Implementierung:** Format "{patient_id} - {series_description} - {n_slices} slices"

### `[x]` T-22 — Demo-Phantom
- **Dateien:** `src/visualization/phantom.py`
- **Abhängig von:** T-10
- **Akzeptanz:** Start ohne `CT_VIEWER_DATA_ROOT` lädt synthetisches Phantom in plausiblen HU (Luft −1000, Wasser 0, Knocheneinschlüsse ~+800) mit anisotropem Spacing; Banner weist auf Demo-Modus hin.

### `[x]` T-23 — 3D-Visualisierung mit Quelle/Detektor
- **Ziel:** Volumen in 3D anzeigen mit Röntgenquelle und Detektor im DICOM-Koordinatensystem.
- **Dateien:** `src/visualization/volume3d.py`
- **Abhängig von:** T-10, T-11
- **Akzeptanz:**
  - 3D-Volumen-Visualisierung (Plotly)
  - Röntgenquelle (Isocenter) und Detektorflügel positioniert gemäß DICOM Patient Coordinate System
  - Rotation/Zoom der 3D-Ansicht
  - Optional: Strahlengang eingezeichnet
- **Status:** ✅ Done (Oct 24, 2026)

#### T-23 Detailplan

| Subtask | Beschreibung | Abhängigkeit | Status |
|---------|--------------|--------------|--------|
| T-23.1 | Bibliotheks-Auswahl: PyVista vs Plotly | — | ✅ Done (Plotly, VTK compatibility issues on Windows) |
| T-23.2 | `Volume3D` dataclass erstellen | T-10 | ✅ Done |
| T-23.3 | 3D-Volumen-Rendering (Iso-Surface oder Volume-Render, wählbar) | T-23.1 | ✅ Done |
| T-23.4 | DICOM-Koordinatensystem-Transformation | T-11 | ✅ Done |
| T-23.5 | Röntgenquelle & Detektor visualisieren | T-23.4 | ✅ Done |
| T-23.6 | Interaktion: Rotation/Zoom | T-23.3 | ✅ Done |
| T-23.7 | Integration in Streamlit-App | T-20 | ✅ Done |
| T-23.8 | Tests für volume3d.py | T-30 | ⚠️ Open |

#### Technische Entscheidungen

| Entscheidung | Optionen | Favorit |
|--------------|----------|---------|
| 3D-Bibliothek | PyVista, Plotly | **Plotly** (keine VTK-Kompatibilitätsprobleme auf Windows) |
| Volumen-Darstellung | Dropdown-Menu: "Iso-Surface" (default), "Volume Rendering" | Beide wählbar, **Standard: Iso-Surface** |
| Koordinatensystem | Patient, Slice, Scanner | Patient (DICOM-Standard) |
| Detektor-Positionierung | Fixed SID, berechnet aus Gantry | Fixed SID (1000mm default) |
| Volumen-Positionierung | Isocenter im Ursprung (0,0,0) | Volumen zentriert am Ursprung |

## Phase 3 — Tests (Tag 5–6) — Teilweise erledigt

### `[x]` T-30 — Synthetische Fixtures
- **Dateien:** `tests/conftest.py`
- **Abhängig von:** T-10
- **Akzeptanz:** Fixture erzeugt per `pydicom` eine Serie im `tmp_path` mit korrekten `ImagePositionPatient`, `RescaleSlope/Intercept`, `SeriesDescription`; keine Binärdaten im Repo.
- **Status:** ✅ Done (Oct 23, 2026)
- **Implementierung:** `create_ct_dicom()` fixture erstellt synthetische CT-DICOM-Dateien mit allen benötigten Tags

### `[x]` T-31 — Loader-Tests
- **Dateien:** `tests/unit/test_dicom_loader.py`, `tests/unit/test_npy_loader.py`
- **Abhängig von:** T-11, T-12, T-30
- **Akzeptanz:** 
  - DICOM: Sortierreihenfolge, HU-Umrechnung, Spacing-Mismatch → `ValueError`, `classify_dose`
  - NPY: 2D/3D Support, Ordner-Scan, Series-Loading, Unit-Detection

### `[x]` T-32 — Windowing- & MPR-Tests
- **Dateien:** `tests/visualization/test_windowing.py`, `tests/visualization/test_mpr.py`
- **Abhängig von:** T-13, T-14
- **Akzeptanz:** Window-Grenzen exakt (0 und 255 an den Rändern), Aspect-Ratio-Fall aus T-14, `width=0` → `ValueError`.
- **Status:** ✅ Done (Oct 19, 2026)

### `[x]` T-33 — Datenvalidierungsskript
- **Dateien:** `scripts/check_aapm.py`
- **Abhängig von:** T-11
- **Akzeptanz:** Tabellarische Ausgabe der Serien; Exit 2 bei fehlendem Verzeichnis oder null Serien; Warnung, wenn alle Serien `unknown` sind.
- **Status:** ✅ Done (Oct 23, 2026)
- **Implementierung:** Scannt Verzeichnis, zeigt Tabelle mit Patient ID, Series Description, Slices, Dose Class

## Phase 4 — Deploy (Tag 6)

### `[ ]` T-40 — Dockerfile
- **Dateien:** `../Dockerfile`, `.dockerignore`
- **Abhängig von:** T-03, T-22
- **Akzeptanz:** Multi-Stage, kein Torch/CUDA, Non-Root-User, Image < 400 MiB, startet ohne Mount im Demo-Modus, Build-Guard aus T-03 aktiv.

### `[ ]` T-41 — CI
- **Dateien:** `.github/workflows/ci.yml`
- **Abhängig von:** T-31, T-40
- **Akzeptanz:** Lint + Tests bei jedem PR; Daten-Guard läuft; Push nach GHCR nur auf `main` und Tags; PRs bauen ohne Push.

### `[ ]` T-42 — README
- **Dateien:** `README.md`
- **Abhängig von:** T-04, T-40
- **Akzeptanz:** Option A (Phantom) und Option B (eigene AAPM-Daten) getrennt; Screenshot zeigt Phantom; Satz zur Nicht-Weitergabe der Challenge-Daten enthalten.

### `[ ]` T-43 — Requirements
- **Ziel:** Projekt-Dependencies definieren.
- **Dateien:** `requirements.txt`, `requirements-dev.txt`
- **Abhängig von:** –
- **Akzeptanz:** 
  - `requirements.txt`: pydicom, numpy, streamlit, pyvista (oder plotly für 3D)
  - `requirements-dev.txt`: pytest, flake8, black, isort
  - Dockerfile verwendet `requirements.txt`

### `[ ]` T-44 — Deployment
- **Ziel:** App veröffentlichen.
- **Optionen:** GHCR, Streamlit Cloud, HuggingFace Spaces
- **Dateien:** `.github/workflows/deploy.yml` (optional)
- **Abhängig von:** T-40, T-41, T-42
- **Akzeptanz:** 
  - Docker-Image wird nach GHCR gepusht (bei Push auf main)
  - ODER: Link zu deployed Streamlit Cloud App im README

## Zeitplan

| Tag | Datum | Tasks |
|---|---|---|
| 1 | Mi, 14.10. | T-01 bis T-04 ✅ |
| 2 | Do, 15.10. | T-10 ✅, T-13 ✅ |
| 3 | Fr, 16.10. | T-11 ✅, T-12 ✅, T-20 ⚠️, T-22 ✅ |
| 4 | Mo, 19.10. | T-14 ✅, T-20 ✅, T-32 ✅ |
| 5 | Di, 20.10. | T-30 ⚠️, T-33 ⚠️ |
| 6 | Fr, 23.10. | T-21 ✅, T-30 ✅, T-33 ✅ |
| 7 | Fr, 24.10. | T-23 ✅ (3D visualization with Plotly) |

## Decision Log

| # | Datum | Entscheidung | Begründung |
|---|---|---|---|
| D-1 | 2026-10-13 | `pydicom` statt SimpleITK | leichtgewichtig, keine ITK-Builds |
| D-2 | 2026-10-13 | Gantry-Tilt in v1 nicht unterstützt | selten in AAPM-Daten, hoher Aufwand |
| D-3 | 2026-10-13 | Viewer- und Trainings-Dependencies getrennt | Image ohne Torch |
| D-4 | 2026-10-13 | Keine Daten in Repo oder Image | DUA der Challenge 2016 verbietet Weitergabe |
| D-5 | 2026-10-13 | AAPM 2016 nur verlinken, kein Download-Skript | kein öffentlicher API-Endpunkt |
| D-6 | 2026-10-13 | `.npy` enthält rohe HU → keine Rückskalierung | in `preprocess_aapm.py` verifiziert |
| D-7 | 2026-10-13 | Phantom bleibt trotz AAPM-Option | lizenzfreier Quickstart und Screenshots |
| D-8 | 2026-10-24 | Plotly statt PyVista für 3D | Keine VTK-Kompatibilitätsprobleme auf Windows |

## Offene Fragen

### Erledigt (Tag 4-7)
- Window-Preset für den Start: `abdomen` ✅ (default in T-20)
- Hover-Koordinaten implementiert ✅
- Keyboard-Navigation (arrows, Home/End, Tab) ✅
- Jump buttons (⏮/⏭) ✅
- T-23: 3D-Visualisierung mit Plotly ✅ (Oct 24, 2026)
  - Iso-Surface und Volume Rendering
  - Source/Detektor Visualization mit Auto/Manual Modus
  - Opacity Controls, Camera Presets, Downsample
  - Container Pattern für Layout (Plot zuerst, Options darunter)
  - Slice Options Expander für MPR

### Noch offen
- T-23.8: Tests für volume3d.py
- Mouse-Wheel-Scrolling über Bilder

## Implementation Notes (Oct 19, 2026)

### 3D Visualization Features (Oct 24, 2026)

| Feature | Description |
|---------|-------------|
| Render Mode | Iso-Surface (default) or Volume Rendering |
| Opacity Controls | Volume Opacity (0.1-1.0), Surface Opacity (0.1-1.0) |
| Camera Presets | iso, front, back, left, right, top, bottom |
| Source/Detector | Auto or manual positioning |
| Isocenter | Auto (from volume center) or manual (x, y, z) |
| Downsample | 1x, 2x, 4x (default) for performance |
| Layout | Container pattern - 3D plot above options in sidebar |

### Key Functions in app.py
| Function | Purpose |
|----------|---------|
| `setup_image_interaction()` | JavaScript for keyboard/click navigation via components.html |
| `slice_slider()` | Slider + anchor div + jump buttons |
| `to_isotropic()` | Resample for correct aspect ratio |
| `clamp_slice_state()` | Clamp session state values before widget creation |
| `plot_slot` | Container for visual ordering - plot renders first, options below |

### Key Functions in mpr.py
| Function | Purpose |
|----------|---------|
| `extract_slice()` | Extract 2D slice from 3D volume |
| `AXIS` | Mapping: axial→0, coronal→1, sagittal→2 |

### Key Functions in dicom.py
| Function | Purpose |
|----------|---------|
| `scan_series()` | Fast scanning by subdirectory (no DICOM reads) |
| `load_dicom_series()` | Load DICOM files into Volume |
| `SeriesInfo` | Dataclass with `files` attribute |

### Key Functions in volume3d.py
| Function | Purpose |
|----------|---------|
| `create_volume_figure()` | Create Plotly figure with isosurface or volume rendering |
| `add_source_detector_figure()` | Add source and detector markers to figure |
| `get_volume_center()` | Calculate center of volume for isocenter |
| `downsample_volume()` | Downsample volume for performance |
| `extract_isosurface()` | Extract isosurface using marching cubes |

### Commands
```bash
# Run server
python -m streamlit run src/visualization/app.py --server.headless true --server.port 8501

# Run tests
python -m pytest tests/ -v
```

## Risiken

| Risiko | Gegenmaßnahme |
|---|---|
| DUA-Verstoß | T-03 Guards, T-42 Hinweis, Phantom im Image |
| Daten in Git-Historie | T-02 vor erstem Push |
| MPR verzerrt bei anisotropem Spacing | T-14 Spacing-basierte Aspect-Ratio + Test |
| Normalisierte `.npy` schleichen sich ein | T-12 `assert_hu` bricht ab |
| Zeitplan reißt | T-23 ist explizit optional |

---

Soll ich als nächstes T-10 bis T-12 ausimplementieren (`volume.py`, `dicom.py`, `npy.py`), oder zuerst Phase 0 — also `LICENSE`, `NOTICE`, `../SECURITY.md`, `docs/data.md` und die Guards?
