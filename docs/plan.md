

# CTBeamStudio — Implementierungsplan

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

### [x] T-22 — Demo-Phantom
- **Dateien:** `src/visualization/phantom.py`, `src/visualization/sidebar.py`, `src/visualization/app.py`
- **Abhängig von:** T-10
- **Akzeptanz:** Start ohne DICOM-Ordner lädt synthetisches Phantom in plausiblen HU (Luft −1000, Wasser 0, Knocheneinschlüsse ~+800) mit anisotropem Spacing; Banner weist auf Demo-Modus hin.
- **Status:** ✅ Done (Oct 27, 2026)
- **Implementierung:**
  - Added `create_shepp_logan_hu()` and `create_demo_volume()` to phantom.py
  - Returns Volume with HU values (-1000 to +800) and anisotropic spacing (3.0, 0.7, 0.7) mm
  - Auto-loads in sidebar.py when no DICOM folder and no cached volume
  - Demo banner shown in app.py when demo_mode is active

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

### `[x]` T-40 - Dockerfile
- **Dateien:** `../Dockerfile`, `.dockerignore`
- **Abhängig von:** T-03, T-22
- **Akzeptanz:** Multi-Stage, kein Torch/CUDA, Non-Root-User, Image < 400 MiB, startet ohne Mount im Demo-Modus, Build-Guard aus T-03 aktiv.

### `[x]` T-41 — CI
- **Dateien:** `.github/workflows/ci.yml`
- **Abhängig von:** T-31, T-40
- **Akzeptanz:** Lint + Tests bei jedem PR; Daten-Guard läuft; Push nach GHCR nur auf `main` und Tags; PRs bauen ohne Push.

### `[x]` T-42 - README
- **Dateien:** `README.md`
- **Abhängig von:** T-04, T-40
- **Akzeptanz:** Option A (Phantom) und Option B (eigene AAPM-Daten) getrennt; Screenshot zeigt Phantom; Satz zur Nicht-Weitergabe der Challenge-Daten enthalten.

### `[x]` T-43 - Requirements
- **Ziel:** Projekt-Dependencies definieren.
- **Dateien:** `requirements.txt`, `requirements-dev.txt`
- **Abhängig von:** –
- **Akzeptanz:** 
  - `requirements.txt`: pydicom, numpy, streamlit, pyvista (oder plotly für 3D)
  - `requirements-dev.txt`: pytest, flake8, black, isort
  - Dockerfile verwendet `requirements.txt`

### `[x]` T-44 — Deployment
- **Ziel:** App veröffentlichen.
- **Optionen:** GHCR, Streamlit Cloud, HuggingFace Spaces
- **Dateien:** `.github/workflows/deploy.yml` (optional)
- **Abhängig von:** T-40, T-41, T-42
- **Akzeptanz:** 
  - Docker-Image wird nach GHCR gepusht (bei Push auf main)
  - ODER: Link zu deployed Streamlit Cloud App im README
- **Status:** ✅ Done (local), ⚠️ Docker deferred (T-71)

## Phase 5 — Projection Geometry (Oct 26, 2026)

### `[x]` T-50 — ProjectionGeometry Dataclass
- **Ziel:** Geometry-Klasse für Cone-Beam CT Projektionsdaten.
- **Dateien:** `src/visualization/geometry.py`
- **Abhängig von:** –
- **Akzeptanz:** Dataclass mit allen Feldern (sdd, sid, n_det_cols, n_det_rows, etc.), Validierung, berechnete Properties (collimation_width, fan_angle, cone_angle).
- **Status:** ✅ Done (Oct 26, 2026)
- **Implementierung:** ProjectionGeometry mit allen required fields, __post_init__ validation, computed properties

### `[x]` T-51 — YAML Loader
- **Ziel:** Geometry aus YAML-Datei laden.
- **Dateien:** `src/visualization/geometry.py`
- **Abhängig von:** T-50
- **Akzeptanz:** `load_geometry_from_yaml()` lädt alle Parameter aus YAML.
- **Status:** ✅ Done (Oct 26, 2026)

### `[x]` T-52 — TXT Loader (Mayo Clinic Format)
- **Ziel:** Geometry aus Mayo Clinic TXT-Format laden.
- **Dateien:** `src/visualization/geometry.py`
- **Abhängig von:** T-50
- **Akzeptanz:** `load_geometry_from_txt()` parsed Mayo Clinic Format.
- **Status:** ✅ Done (Oct 26, 2026)

### `[x]` T-53 — Geometry Unit Tests
- **Ziel:** Tests für ProjectionGeometry und Loaders.
- **Dateien:** `tests/unit/test_geometry.py`, `tests/unit/test_geometry_yaml.py`, `tests/unit/test_geometry_txt.py`, `tests/unit/test_geometry_trajectory.py`
- **Abhängig von:** T-50
- **Akzeptanz:** Alle Tests bestehen.
- **Status:** ✅ Done (Oct 26, 2026)

## Phase 6 — Projection Geometry 3D Visualization (Oct 26, 2026)

### `[x]` T-54 — Geometry Loader für User-Dateien
- **Ziel:** Projektions-Geometrie aus User-Dateien laden.
- **Dateien:** `src/visualization/loaders/projection.py`
- **Abhängig von:** T-52
- **Akzeptanz:** `load_projection_geometry(txt_path)` Funktion verfügbar.
- **Status:** ✅ Done (Oct 26, 2026)
- **Implementierung:** Wrapper um load_geometry_from_txt

### `[x]` T-55 — Geometry-Based Source/Detector in 3D Plot
- **Ziel:** 3D-Plot zeigt Source/Detektor basierend auf ProjectionGeometry.
- **Dateien:** `src/visualization/volume3d.py`
- **Abhängig von:** T-54
- **Akzeptanz:** 
  - `get_source_position(geometry, source_angle)` 
  - `get_detector_position(geometry, source_angle)`
  - `get_trajectory_positions(geometry, n_projections)`
- **Status:** ✅ Done (Oct 26, 2026)

### `[x]` T-56 — UI für Projection Geometry in App
- **Ziel:** UI zum Laden der Geometry-Datei und Anpassen des Downsampling.
- **Dateien:** `src/visualization/app.py`
- **Abhängig von:** T-54, T-55
- **Akzeptanz:** 
  - File-Uploader für Geometry-TXT
  - Downsample-Dropdown (N = 1000, 100, 10, 1)
  - Trajektorie in 3D-Plot anzeigen
- **Status:** ✅ Done (Oct 27, 2026)

### `[ ]` T-56a — Directory Picker UI (Future)
- **Ziel:** Bessere Ordner-Auswahl mit `streamlit-explorer` DirPicker.
- **Dateien:** `src/visualization/sidebar.py`
- **Abhängig von:** T-20
- **Akzeptanz:** Ersetzt text_input durch grafischen Ordner-Dialog.
- **Implementierung:**
  ```python
  from streamlit_explorer import DirPicker
  # Replace st.text_input("DICOM Folder") with DirPicker
  ```

### `[ ]` T-75 — Desktop App Wrapper (Future)
- **Ziel:** Streamlit als Desktop-App ohne Browser starten.
- **Dateien:** `src/visualization/desktop_launcher.py`
- **Optionen:**
  1. **streamlit-desktop-app** (PyPI) - PyInstaller support, stabil
  2. **streamlitrunner** (PyPI) - Einfacher wrapper
  3. **pywebview** manuell - Mehr Kontrolle
- **Windows Requirements:** .NET Framework > 4.0, Edge WebView2
- **Implementierung:**
  ```python
  # Start streamlit in background thread, wrap in pywebview window
  ```
- **Status:** ⚠️ Research

## Phase 7 — Docker Self-Deployment (Build blocked - no Docker installed)

### `[x]` T-71 — Review/Update Dockerfile
- **Ziel:** Dockerfile für Self-Deployment vorbereiten.
- **Dateien:** `Dockerfile`
- **Abhängig von:** T-40
- **Akzeptanz:** Non-root user, korrekter Pfad zu app.py, Health-Check.
- **Status:** ✅ Done (Oct 29, 2026) — install order fixed (README + src before pip install)
- **Offen:** Build-Verifikation (siehe T-73)

### `[x]` T-72 — Create .dockerignore
- **Ziel:** Ungewollte Dateien vom Docker-Build ausschließen.
- **Dateien:** `.dockerignore`
- **Abhängig von:** –
- **Akzeptanz:** Keine .dcm, .npy, __pycache__, .git im Image.
- **Status:** ✅ Done (Oct 29, 2026) — zusätzlich docs, tests, scripts, IDE/Cloud-Ordner ausgeschlossen

### `[ ]` T-73 — Build and Test Docker Image
- **Ziel:** Docker-Image bauen und verifizieren.
- **Dateien:** –
- **Abhängig von:** T-71, T-72
- **Akzeptanz:** Image < 400 MiB, Container startet, App erreichbar auf Port 8501.
- **Status:** ⚠️ Blocked (Docker nicht installiert; Build/Health-Check nicht ausgeführt)

### `[ ]` T-74 — Create Run Script
- **Ziel:** Komfort-Script zum Starten des Containers.
- **Dateien:** `scripts/run-docker.sh`
- **Abhängig von:** T-73
- **Akzeptanz:** Script startet Container auf Port 8501.
- **Status:** ⚠️ Script erstellt und ausführbar (Oct 29, 2026), aber Inbetriebnahme unverifiziert (T-73 blocked)

## Phase 8 — Forward Projection with Parallelproj (Oct 27, 2026)

### `[x]` T-61 — Add parallelproj Dependency
- **Ziel:** parallelproj als Dependency hinzufügen.
- **Dateien:** `requirements.txt` oder `pyproject.toml`
- **Abhängig von:** –
- **Akzeptanz:** `import parallelproj` funktioniert.
- **Status:** ⚠️ Teilweise — Hinweis in `pyproject.toml` (conda-forge), aktive Installation nur im conda-Env `ct-viewer`.

### `[x]` T-62 — Forward Projection Module
- **Ziel:** Forward-Projection-Funktion mit parallelproj.
- **Dateien:** `src/backend/forward_project.py` (ehemals `src/visualization/forward_project.py`)
- **Abhängig von:** T-61, T-50, T-10
- **Akzeptanz:** `forward_project(volume, geometry)` gibt Projektionen zurück.
- **Status:** ✅ Done — Modul mit Fallback (Zeros) + `parallelproj`-Pfad; Tests grün.

### `[x]` T-63 — Implement Parallelproj Forward Projection
- **Ziel:** Tatsächliche Implementation mit parallelproj (PyTorch).
- **Dateien:** `src/backend/parallelproj/` (Implementierung), `src/backend/forward_project.py` (Einstieg)
- **Abhängig von:** T-62
- **Akzeptanz:** Synthetische Projektionen aus Volumen generieren.
- **Status:** ✅ Done (Nov 4, 2026) — Cone-Beam via `ListmodePETProjector` (joseph3d), geometrie/orientierung verifiziert (0°-Vier-Regionen-Test).

### `[x]` T-78 — Backend-Restrukturierung (Refactor)
- **Ziel:** Numerisches / Daten-Backend von der UI trennen (one-way dependency: `visualization` → `backend`).
- **Dateien:** `src/backend/{volume,geometry,forward_project}.py`, `src/backend/loaders/`, Paketierung `pyproject.toml`
- **Abhängig von:** T-63
- **Akzeptanz:** `Volume`, `ProjectionGeometry`, `forward_project` und Loader (dicom, npy, projection) liegen unter `src/backend/`; `import backend` funktioniert ohne parallelproj (lazy); alle Imports (UI, Tests, Skripte) aktualisiert; Testsuite grün.
- **Status:** ✅ Done (Nov 4, 2026) — siehe Spec `docs/superpowers/specs/2026-11-04-backend-restructure-design.md`.

## Phase 9 — Sinogram Loader with Lazy Loading

### `[x]` T-64 — Sinogram Loader with Selection
- **Ziel:** Sinogram-Daten laden mit Row/Col/Projection Selection.
- **Dateien:** `src/backend/loaders/sinogram.py`
- **Abhängig von:** –
- **Akzeptanz:** `load_sinogram()` mit SelectionConfig.
- **Status:** ✅ Done (Nov 4, 2026) — Node `src/backend/loaders/sinogram.py`; Format-Support numpy (.npy/.npz), NIfTI, DICOM; Selektion all/central/range/downsample/custom; `axis_order` nach dem Laden änderbar (In-Memory Transpose bzw. Disk-Re-Read). Siehe Spec `docs/superpowers/specs/2026-11-04-sinogram-loader-design.md`.

### `[x]` T-65 — DICOM Lazy Loading
- **Ziel:** Lazy Loading für Helical-DICOM-Daten.
- **Dateien:** `src/backend/loaders/sinogram.py`
- **Abhängig von:** T-64
- **Akzeptanz:** Nur benötigte Rows/Projections laden.
- **Status:** ✅ Done (Nov 4, 2026) — `scan_dicom_sinogram()` (Header-Only-Scan) + `_load_dicom`; nur die selektierten Projektionen werden gelesen (Pixel-Arrays der nicht-selektierten Frames nie geladen). Siehe Spec `docs/superpowers/specs/2026-11-04-sinogram-loader-design.md`.

### `[x]` T-66 — Update Loaders __init__.py
- **Ziel:** Sinogram-Loader exportieren.
- **Dateien:** `src/backend/loaders/__init__.py`
- **Abhängig von:** T-64
- **Akzeptanz:** `from backend.loaders import load_sinogram` funktioniert.
- **Status:** ✅ Done (Nov 4, 2026) — Exportiert `SelectionConfig`, `SinogramData`, `load_sinogram`, `resolve_indices`, `scan_dicom_sinogram`.

## Phase 10 — Comparison

### `[ ]` T-67 — Comparison Module
- **Vergleich:** Synthetic vs Measured Projektionen.
- **Dateien:** `src/visualization/comparison.py`
- **Abhängig von:** T-63, T-64
- **Akzeptanz:** MAE, RMSE, SSIM, Correlation berechnen.
- **Status:** ⚠️ Open

### `[ ]` T-68 — Comparison Visualization
- **Ziel:** Side-by-side Visualisierung der Vergleichsergebnisse.
- **Dateien:** `src/visualization/comparison.py`
- **Abhängig von:** T-67
- **Akzeptanz:** Plotly-Visualisierung mit 3 Spalten (Synthetic | Measured | Difference).
- **Status:** ⚠️ Open

### `[ ]` T-69 — Integration Tests
- **Ziel:** Tests für den vollständigen Workflow.
- **Dateien:** `tests/integration/test_forward_projection_workflow.py`
- **Abhängig von:** T-63, T-67
- **Akzeptanz:** Volumen → Forward Project → Compare funktioniert.
- **Status:** ⚠️ Open

## Phase 11 — App Integration

### `[ ]` T-70 — Forward Projection UI
- **Ziel:** UI für Forward Projection und Vergleich in Streamlit-App.
- **Dateien:** `src/visualization/app.py`
- **Abhängig von:** T-63, T-66, T-68
- **Akzeptanz:** 
  - File-Upload für gemessene Daten
  - Row/Col/Projection Selection UI
  - Run Button
  - Results Display (Visual + Metrics)
- **Status:** ⚠️ Open

### `[ ]` T-76 — FDK / Analytische Rekonstruktion
- **Ziel:** FDK-Algorithmus für CBCT-Rekonstruktion implementieren.
- **Dateien:** `src/reconstruction/fdk.py`
- **Abhängig von:** T-61
- **Implementierung:**
  1. Pre-Weighting (FDK weight)
  2. FFT-basierte Filterung (Ram-Lak, Shepp-Logan)
  3. Parker weighting für short-scan
  4. Cone-beam backprojection
- **Optionen:** ASTRA (bestehend), TomoPy, oder eigene Implementierung
- **Status:** ⚠️ Open (Future)

### `[ ]` T-77 — Phantomlose Geometrie-Kalibrierung
- **Ziel:** Geometrie aus Projektionsdaten schätzen ohne Kalibrierphantom.
- **Dateien:** `src/calibration/geometry_calibration.py`
- **Abhängig von:** T-63, T-76
- **Implementierung:**
  1. Merkmalsextraktion (Kanten, Features)
  2. Feature-Tracking über Projektionen
  3. Bundle Adjustment: Geometrie + 3D-Punkte optimieren
  4. DCC-basierte Regularisierung
- **Status:** ⚠️ Open (Research)
- **Siehe auch:** `docs/research/phantomless-geometry-calibration-helix-cbct.md`

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
| 8 | Mo, 26.10. | T-50 bis T-55 ✅ (Projection Geometry) |
| 9 | | T-56 ⚠️, T-57 bis T-60 ⚠️ (Docker) |
| 10 | | T-61 bis T-70 ⚠️ (Parallelproj Forward Projection) |

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
| D-9 | 2026-11-04 | Numerisches Backend von UI trennen: `Volume`, `ProjectionGeometry`, `forward_project`, Loader (dicom/npy/projection) nach `src/backend/` | one-way dependency `visualization` → `backend`; `parallelproj` lazy import |

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
- T-61: parallelproj Dependency (teilweise — conda-env `ct-viewer`, nicht als pip-Dep)
- T-64: Sinogram Loader with Selection
- T-65: DICOM Lazy Loading
- T-66: Update Loaders __init__.py
- T-67: Comparison Module
- T-68: Comparison Visualization
- T-69: Integration Tests
- T-70: Forward Projection UI

## Erledigt

### Projection Geometry (Phase 5)
- ✅ T-50: ProjectionGeometry dataclass mit Validierung
- ✅ T-51: YAML Loader (load_geometry_from_yaml)
- ✅ T-52: TXT Loader (load_geometry_from_txt) - Mayo Clinic Format
- ✅ T-53: Unit Tests für Geometry (test_geometry.py, test_geometry_yaml.py, test_geometry_txt.py, test_geometry_trajectory.py)

### Projection Geometry 3D Visualization (Phase 6)
- ✅ T-54: Geometry Loader für User-Dateien (loaders/projection.py)
- ✅ T-55: 3D Trajectory Funktionen: get_source_position, get_detector_position, get_trajectory_positions

### Phase 1-4
- Alle Tasks T-01 bis T-44 ✅
- T-23: 3D-Visualisierung ✅ (Oct 24)
- Docker deferred to T-71-74 (T-71, T-72 ✅ done; T-73 ⚠️ blocked; T-74 script ⚠️ started)

## Implementation Notes

### 3D Visualization Features

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


