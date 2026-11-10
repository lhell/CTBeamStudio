

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
- **Update (Nov 6, 2026):** `create_shepp_logan_3d()` now builds a true 3D
  phantom from ellipsoids instead of stacking the 2D slice. Ellipsoid geometry
  follows Kak & Slaney (1 phantom unit = 100 mm), painted outside-in with
  anatomical HU values: air −1000, skull +1000, brain 40, white matter 30,
  ventricles 10, lesions 60. Defaults are `size=256, num_slices=64,
  spacing=(3.0, 0.75, 0.75)` → 192 × 192 × 192 mm FOV. The returned array is
  `int16` HU; `create_shepp_logan_hu()`/`create_demo_volume()` wrap it in a
  `Volume`. Tests now assert differing axial slices and a real coronal/sagittal
  head profile instead of identical extruded slices.

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

### `[x]` T-67 — Comparison Module
- **Vergleich:** Synthetic vs Measured Projektionen.
- **Dateien:** `src/visualization/comparison.py`
- **Abhängig von:** T-63, T-64
- **Akzeptanz:** MAE, RMSE, SSIM, Correlation berechnen.
- **Status:** ✅ Done (Nov 6, 2026) — `compute_metrics()` + `difference_image()`; konstante Bilder liefern Korrelation 0 statt NaN, kleine Bilder nutzen einen SSIM-Fallback.

### `[x]` T-68 — Comparison Visualization
- **Ziel:** Side-by-side Visualisierung der Vergleichsergebnisse.
- **Dateien:** `src/visualization/projection_panel.py`
- **Abhängig von:** T-67
- **Akzeptanz:** Plotly-Visualisierung mit 3 Spalten (Synthetic | Measured | Difference).
- **Status:** ✅ Done (Nov 6, 2026) — 3-Spalten-Ansicht (Real | Simulated | Difference) plus Metrik-Kacheln im Tab „Real vs Simulated“.

### `[x]` T-69 — Integration Tests
- **Ziel:** Tests für den vollständigen Workflow.
- **Dateien:** `tests/integration/test_projection_workflow.py`
- **Abhängig von:** T-63, T-67
- **Akzeptanz:** Volumen → Forward Project → Compare funktioniert.
- **Status:** ✅ Done (Nov 6, 2026) — End-to-End mit echter parallelproj-Projektion, Sinogramm-Load und Metriken; läuft im `ct-viewer`-Env, wird sonst sauber geskippt.

## Phase 11 — App Integration

### `[x]` T-70 — Forward Projection UI
- **Ziel:** UI für Forward Projection und Vergleich in Streamlit-App.
- **Dateien:** `src/visualization/app.py`, `src/visualization/sidebar.py`, `src/visualization/projection_panel.py`
- **Abhängig von:** T-63, T-66, T-68
- **Akzeptanz:**
  - File-Upload für gemessene Daten
  - Row/Col/Projection Selection UI
  - Run Button
  - Results Display (Visual + Metrics)
- **Status:** ✅ Done (Nov 6, 2026) — umgesetzt als drei flache Tabs: `Viewer | Geometry | Real vs Simulated`.

#### T-70 Detailplan (Nov 6, 2026)

| Subtask | Beschreibung | Status |
|---------|--------------|--------|
| T-70a | Messdaten-Auswahl in der Sidebar (Pfad/Ordner, Achsen-Selektion, Axis-Order, Load-Button) | ✅ Done |
| T-70b | Tab „Geometry“: Parameter aus Datei anzeigen + editieren (Apply/Reset) | ✅ Done |
| T-70c | Tab „Real vs Simulated“: Forward-Projection-Controls, Run-Button, 3-Spalten-Vergleich + Metriken | ✅ Done |
| T-70d | Headless-UI-Tests (Tabs, Sidebar-Controls, Messdaten-Load via `AppTest`) | ⚠️ entfernt (`8de260b`), neu geplant als T-81 |

### `[x]` T-79 — Non-contiguous Projection Selection Fix
- **Ziel:** `forward_project` muss beliebige `proj_indices` (z. B. Downsample `[0, 10, 20]`) korrekt auf die passenden Gantry-Winkel abbilden.
- **Dateien:** `src/backend/forward_project.py`, `src/backend/parallelproj/geometry.py`
- **Abhängig von:** T-63
- **Akzeptanz:** `calculate_xray_beam_list(projection_indices=...)` berechnet nur die gewählten Winkel; Ergebnis entspricht der entsprechenden Auswahl aus der vollen Projektion.
- **Status:** ✅ Done (Nov 6, 2026) — Test `test_forward_project_selected_projection_indices_match_full`; Downsample/range-Auswahlen funktionieren jetzt ohne `IndexError`.

### `[x]` T-80 — HU ↔ Attenuation mit Energieauswahl (FP-Grundlage)
- **Ziel:** CT-Darstellung flexibel zwischen HU und linearer Schwächung umschaltbar machen, mit monoenergetischer Energieauswahl. Grundlage der Forward Projection ist die Schwächung, nicht HU.
- **Dateien:** `src/backend/attenuation.py`, `src/visualization/display_units.py`, `src/visualization/app.py`, `src/visualization/projection_panel.py`
- **Abhängig von:** T-63, T-70
- **Modell:** wasseräquivalent, monoenergetisch — `μ(E) = μ_Wasser(E) · (1 + HU/1000)`. `μ_Wasser(E)` aus NIST-Tabellen (flüssiges Wasser, 30–150 keV, log-log interpoliert). Keine Beam-Hardening-Korrektur.
- **Akzeptanz:**
  - Umschalter **Display Unit: HU / Attenuation (1/cm)** in „Slice Options“, Energie-Slider 30–150 keV (Default 70)
  - Fenster-Presets und Slider-Grenzen rechnen mit um
  - `hu_to_mu` / `mu_to_hu` / `hu_window_to_mu` / `volume_to_mu` / `volume_for_projection`
  - Forward Projection akzeptiert **nur** Attentuation (`1/mm`/`1/cm`) und lehnt HU mit `ValueError` ab
  - Tab „Real vs Simulated“ konvertiert das Volumen vor der Projektion und bietet einen Energie-Slider
- **Status:** ✅ Done (Nov 6, 2026) — `volume_for_projection()` liefert `1/mm`, weil parallelproj die Strahlen in mm integriert (1/cm wäre Faktor 10 daneben). Tests: `test_attenuation.py`, `test_display_units.py`, `test_forward_project.py`, `test_projection_panel.py`.

### `[x]` T-81 — Schneller UI-Smoke-Test (ersetzt T-70d)
- **Ziel:** Tab-/Sidebar-Layout wieder absichern, ohne die Testsuite zu verlangsamen.
- **Hintergrund:** Die sechs `AppTest`-Tests aus T-70d dauerten **96,8 s** (~75 % der Suite), weil jeder Test einen kompletten Streamlit-Script-Run startet. Ein `AppTest.run()` kostet 10–30 s: ~8 s Import von `visualization.volume3d` (skimage/pyvista) und ~3,6 s in `load_last_loaded()` (87 KB Cache mit 560 toten Netzwerkpfaden). Entfernt in `8de260b`, Datei bleibt in der Historie (`6307a6a`).
- **Dateien:** `tests/integration/test_ui_smoke.py` (neu)
- **Abhängig von:** T-70
- **Umsetzung:**
  1. **Eine** `AppTest`-Instanz pro Modul (`scope="module"`), nicht pro Test.
  2. Session-State vorab setzen (`demo_mode`, `volume`), damit `load_initial_volume()` und der Cache-Pfad übersprungen werden.
  3. `auto_load_cache=False` erzwingen, um die 560 toten `O:`-Pfade nicht anzufassen.
  4. `visualization.volume3d`-Import messen; ggf. 3D-Render lazily laden.
  5. Optional `@pytest.mark.slow`, per Default ausgeschlossen (`-m "not slow"`).
- **Akzeptanz:** Tab-Reihenfolge, Sidebar-Controls, Geometry-Hinweis und Messdaten-Load abgedeckt; Laufzeit < 15 s; Suite bleibt unter 20 s.
- **Status:** ✅ Done (Nov 9, 2026) — `tests/integration/test_ui_smoke.py` deckt Tab-Reihenfolge, Sidebar-Controls (Sektionsreihenfolge, Expanded-Defaults, kein „Data"-Header, Cache-Controls oben), Geometry-Hinweis, Missing-Inputs-Hinweis, Messdaten-Load und Empty-State-Start ab (14 Tests, eine modulweite `AppTest`-Instanz). **Laufzeit-Ziel erreicht:** Modul ~5 s, Suite ~16–20 s (vorher 22 s / 30 s). Der frühere Engpass `pyvista` (~5,6 s) ist durch den Lazy-Import (`test_volume3d_import.py`) und das Shelving des PyVista-Render-Modus (T-82/T-84) ganz aus dem Startpfad verschwunden.

### `[x]` T-83 — Background-Startup-Load (nicht blockierender Start)
- **Ziel:** Den Ladevorgang beim Start aus dem Streamlit-Script-Thread herausnehmen, damit Shell, Sidebar und alle drei Tabs schon bedienbar sind, während eine Serie gelesen wird.
- **Dateien:** `src/visualization/background_load.py` (neu), `src/visualization/sidebar.py`, `src/visualization/app.py`, `tests/unit/test_background_load.py`, `tests/unit/test_startup_selection.py`, `tests/integration/test_ui_smoke.py`
- **Abhängig von:** T-81
- **Umsetzung:**
  1. Streamlit-freie Job-Registry: `start_job` / `job_state` / `reset_job` / `run_and_capture` mit `threading.Lock` und Daemon-Thread; genau ein Ergebnis pro Job, `run_and_capture` setzt den Endstatus im `finally` (kein endloses Polling).
  2. `effective_status(status, started_at, now, deadline_s=600)` bricht Jobs mit Wanduhr-Deadline ab; Endzustände werden nie überschrieben.
  3. `@st.fragment(run_every="1s")` `render_startup_status()` pollt; der `startup_polling`-Flag ist der Ausschalter, weil `run_every` nicht von innen abgeschaltet werden kann. Das Fragment zeichnet bewusst **keine** Elemente (sonst blieb eine veraltete „Loading data …"-Box stehen) — die sichtbare Box rendert der normale Script-Pfad.
  4. Ergebnis wird nur geschrieben, wenn `st.session_state["volume"]` noch `None` ist; ein explizit geladenes „Load Series" gewinnt.
  5. `reset_job(startup_job_name())` in „Clear Cache" (Registry lebt außerhalb des Session-State) und pro Session eigener Job-Name über `startup_job_token`.
- **Status:** ✅ Done (Nov 9, 2026) — 11 Unit-Tests (`test_background_load.py`), 4 Tests für die Startup-Policy (`test_startup_selection.py`). **Polling und Interaktivität sind nicht durch die Suite abgedeckt**, weil `run_every` unter `AppTest` (1.39.1) nicht feuert; im Browser verifiziert. Spec: `docs/superpowers/specs/2026-11-09-background-startup-load-design.md`, Plan: `docs/superpowers/plans/2026-11-09-background-startup-load.md`.
- **Hinweis:** Der ursprüngliche Auto-Load-Pfad ist mit T-85 entfallen; `render_startup_status()` bleibt als Polling-Mechanismus im Code, wird aktuell aber nicht angestoßen.

### `[x]` T-84 — Geometrie-Overlay im 3D-Canvas schaltbar (PyVista aus der UI)
- **Ziel:** Das Projektionsgeometrie-Overlay im 3D-Plot ein-/ausschalten, ohne einen Script-Rerun auszulösen.
- **Dateien:** `src/visualization/volume3d.py` (`add_geometry_toggle`), `src/visualization/app.py`, `tests/unit/test_geometry_toggle.py`, `tests/integration/test_ui_smoke.py`
- **Abhängig von:** T-23, T-55
- **Akzeptanz:**
  - `updatemenus`-Buttonpaar „On"/„Off" unten rechts im Canvas (`x=0.99, y=0.02`), clientseitig über `visible`-Listen — kein Rerun.
  - `n_base_traces = len(fig.data)` wird nach `create_volume_figure()` und vor jedem Overlay-Trace erfasst; „Off" blendet nur Source/Detector, Trajektorie, Detektor-Ebenen und Zentralstrahlen aus, nie das Volumen.
- **Status:** ✅ Done (Nov 9, 2026, `53d4291`) — 10 Unit-Tests in `test_geometry_toggle.py`, Smoke-Test prüft die Button-Spec in der Figur. Zusätzlich: redundante „Show Trajectory"-Checkbox entfernt (Trajektorie folgt der geladenen Geometrie), Lade-Abschlussmeldung als selbst verschwindender Toast statt permanentem Status-Box, PyVista-Render-Modus aus der UI entfernt (`Dockerfile`/`README` ohne `pyvista`) — Reaktivierung bleibt als T-82 offen.

### `[x]` T-85 — Kein Auto-Load, Empty State, Zirkulärscan-Defaults, sichtbare Richtungspfeile
- **Ziel:** Start und „Clear Cache" landen im selben leeren Zustand, die UI ist wieder durchgehend englisch, die Geometrie-Defaults beschreiben einen zirkulären Cone-Beam-Scan, und die Richtungspfeile der Trajektorie sind sichtbar.
- **Dateien:** `src/visualization/app.py`, `src/visualization/sidebar.py`, `src/visualization/projection_panel.py`, `src/visualization/volume3d.py`, `src/backend/geometry.py`, `tests/integration/test_ui_smoke.py`, `tests/unit/test_geometry.py`, `tests/unit/test_geometry_trajectory.py`, `tests/unit/test_startup_selection.py`
- **Abhängig von:** T-83
- **Umsetzung:**
  1. `should_startup_load()` liefert immer `False`; die „Auto-load cache"-Checkbox ist entfernt, Caching ist immer aktiv. `render_empty_state()` („Nothing to show — load image data in the sidebar, or use the demo phantom.") bietet „Load Demo Phantom" an; sie ersetzt den alten Welcome-Screen und wird auch nach einem fehlgeschlagenen Startup gezeigt.
  2. `ProjectionGeometry.pitch = 0.0` (nur negativer Pitch wird abgelehnt) = Zirkulärscan; „Projections" startet mit `projections_per_rotation` (2304, aus der Geometrie geseedet) statt 51326; „Trajectory Downsample" startet bei 1/100, damit der Ring das Volumen nicht zudeckt.
  3. Richtungspfeile: `sizemode="raw"` + `ARROW_LENGTH_MM = 25.0` statt `sizemode="absolute"` mit `sizeref=1` (das zeichnete Cones von einer Dateneinheit, also unsichtbar); eigener Legendeneintrag „Direction" mit Plotlys nativem Cone-Swatch.
  4. Sidebar: nur „Image" ist offen, „Projection Geometry" und „Measurements" sind zu; die abgeleiteten Geometriewerte (Fan/Cone angle, Collimation) sind eine kompakte Caption statt drei großer `st.metric`-Kacheln. Alle sichtbaren Strings wieder englisch.
- **Status:** ✅ Done (Nov 9, 2026, `c4ad84e`) — Tests: Startup-Policy, `pitch=0.0` als gültiger Zirkulärscan, 2304-Default, Arrow-Sizing und „Direction"-Legendeneintrag, Empty-State-Start, zugeklappte Sektionen, entfallende Auto-load-Checkbox. Suite danach: **256 passed, 2 skipped** in ~16–23 s.

### `[ ]` T-82 — PyVista-Render-Modus reaktivieren (verschoben)
- **Ziel:** Den off-screen PyVista-Render-Modus wieder in der UI anbieten — mit Geometrie-Overlay und On/Off-Schalter, nicht als statisches Bild.
- **Status:** ⚠️ Shelved (Nov 9, 2026) — Der Modus wurde aus der UI entfernt (`render_mode` bietet nur noch Iso-Surface), weil `create_pyvista_volume()` serverseitig ein PNG rendert (`plotter.screenshot()` → `st.image`). Ein statisches Bild kann keinen interaktiven Schalter tragen, und der PyVista-Zweig zeichnete gar kein Geometrie-Overlay. Der Renderer bleibt unverändert in `src/visualization/volume3d.py` (inkl. Lazy-Import-Guard `PYVISTA_AVAILABLE`) — nichts gelöscht, nur nicht mehr verdrahtet. Aus dem Dockerfile wurde `pyvista` entfernt.
- **Dateien (bei Reaktivierung):** `src/visualization/volume3d.py` (`create_pyvista_volume`), `src/visualization/app.py` (Render-Mode-Liste + Zweig), `Dockerfile`, `tests/unit/test_volume3d_import.py`
- **Abhängig von:** –
- **Umsetzung (Skizze):**
  1. Geometrie-Overlay in den PyVista-Plot aufnehmen (Source/Detector/Trajektorie analog zu `add_trajectory_to_figure`).
  2. Schalter bereitstellen: interaktiv geht nur ein Streamlit-`st.toggle` über dem Bild (rerun + Re-Render) — oder PyVista durch `panel`/`vtk.js`/`stpyvista` ersetzen, dann ist ein echter In-Canvas-Schalter möglich.
  3. `pyvista` wieder in `Dockerfile` installieren.
- **Akzeptanz:** Render-Mode-Auswahl bietet PyVista wieder an, das Overlay ist sichtbar und per Schalter abschaltbar, der Lazy-Import-Guard bleibt grün.

### `[x]` T-86 — Viewer-Layout: All/2D/3D-Umschalter, gestapelte MPR, schwebende Options-Panels
- **Ziel:** Der 3D-Ansicht die Mehrheit des Viewer-Tabs geben: drei kleine MPR-Ebenen links gestapelt, große 3D-Ansicht rechts, umschaltbar auf Vollbreite je Seite. Options-Panels sollen schweben, damit ihr Öffnen keine Ansicht verschiebt.
- **Dateien:** `src/visualization/app.py` (`render_viewer_tab`), `pyproject.toml`, `tests/unit/test_viewer_layout.py` (neu), `tests/integration/test_ui_smoke.py`
- **Abhängig von:** T-23, T-84
- **Umsetzung:**
  1. `st.radio(..., horizontal=True)` mit `All` / `2D` / `3D`, **außerhalb** der Spalten gerendert — in einer kollabierten Spalte wäre er unerreichbar.
  2. Spaltenbreiten aus `viewer_column_spec()`: `All=[1, 2]`, `2D=[1, 0.0001]`, `3D=[0.0001, 1]`. Der Epsilon-Wert rendert exakt 0 px; eine literale `0` lehnt `st.columns` ab (`StreamlitInvalidColumnSpecError`).
  3. MPR-Ebenen im festen `st.container(height=VIEWER_HEIGHT_PX, border=False)`; in `2D` stattdessen ein 2×2-Raster aus zwei `st.columns(2)`-Zeilen (vierte Zelle leer).
  4. Beide Options-Panels als `st.popover` (Slice Options, 3D Options) statt `st.expander`.
  5. Slice-/Spacing-Readout (`Slice N/M | Spacing (…)`) aus dem Bild-Untertitel in das Slice-Options-Panel verschoben.
  6. 3D-Figur nur bauen, wenn `viewer_has_3d(view)` — in `2D` ist die Spalte 0 px breit, Marching Cubes wäre verschwendet.
  7. `pyproject.toml`: `streamlit>=1.28.0` → `>=1.37.0,<1.40.0`. Die alte Untergrenze war schon vorher unerfüllbar, weil `app.py` `@st.fragment` nutzt (GA erst ab 1.37).
- **Status:** ✅ Done (Nov 10, 2026, `b0687d2`) — 7 neue Tests (5 Layout-Geometrie in `test_viewer_layout.py`, 2 Smoke-Tests für Popovers und Umschalter). Im laufenden Server alle drei Ansichten geprüft: `All` 195/399 px mit 3×190 px Ebenen (Stapel 685 px in 700 px), `2D` 594 px Vollbreite mit 3×289 px im Raster, `3D` 594 px mit Plot 594×700; keine Überläufe, kein Seiten-Scrollbalken.
- **Abweichung vom ersten Entwurf:** `VIEWER_HEIGHT_PX` ist **700** statt 900, und die Bilder nutzen `use_column_width=True` statt eines festen 260-px-Caps. Bei 900 px begann die Plotly-Canvas 362 px unter dem Seitenanfang und die Szene lief aus dem Bild; ein fester Pixel-Cap läuft in einer schmalen Spalte über (gemessen: 260 px Bild in 201 px Spalte). Details in `docs/superpowers/specs/2026-11-09-viewer-layout-design.md` §3.3/§3.4.

### `[ ]` T-87 — Vollbild je Ansicht (Fullscreen) prüfen und dokumentieren
- **Ziel:** Sicherstellen, dass jede der vier Ansichten (3× MPR, 1× 3D) auf Knopfdruck den verfügbaren Platz einnimmt — ohne eigenen Code, wo Streamlit/Plotly das schon können.
- **Hintergrund:** Beim Prüfen des Viewer-Layouts (T-86) zeigte sich, dass **beide** Vollbild-Pfade bereits nativ vorhanden sind:
  - `st.image` rendert jede MPR-Ebene in einen `stFullScreenFrame` mit eingebautem „View fullscreen"-Button (`data-testid="StyledFullScreenButton"`, erscheint beim Hover, `position: fixed`, z-index 1000050). Gemessen: drei sichtbare Buttons, einer pro Ebene.
  - Plotly 7.1 bietet in der Modebar des 3D-Charts einen „Fullscreen"-Eintrag (`_context.displayModeBar == "hover"` ist bereits aktiv).
  Es fehlt also **kein Feature**, sondern eine Entscheidung, ob diese zwei verschiedenen Mechanismen gut genug sind.
- **Dateien:** `src/visualization/app.py` (`render_viewer_tab`), ggf. `src/visualization/volume3d.py` (nur Modebar-Config), `tests/integration/test_ui_smoke.py`
- **Abhängig von:** T-86
- **Offene Punkte / zu entscheiden:**
  1. **Zwei verschiedene Bedienmuster** — Bild-Vollbild ist ein Hover-Button unten rechts, 3D-Vollbild liegt im Plotly-Menü. Ein einheitlicher „⛶"-Button je Spalte wäre konsistenter, kostet aber eigene Implementierung.
  2. **Feste Höhe vs. Vollbild — geprüft:** kein Problem. Plotly ignoriert `height` im Vollbild und baut auf die Viewport-Höhe um. Gemessen: `399×700` → **`1088×612`** (Viewport 1112×670), `_fullLayout.height` 700 → 612. `layout.height` wird dabei temporär überschrieben, nicht dauerhaft verändert.
  3. **MPR-Vollbild skaliert nur das Bild**, nicht die zugehörigen Slice-Slider — ein Vollbild-Slice-Viewer mit Slidern wäre `st.dialog(width="large")` (in 1.39.1 vorhanden) und würde einen eigenen Renderpfad brauchen.
  4. **Bild-Vollbild nutzt `position: fixed` + z-index 1000050** — verifiziert; die Seite muss danach neu geladen werden, sonst bleiben die `stFullScreenFrame`-Wrapper bei 0×0 hängen (im Test beobachtet). Kein App-Fehler, aber relevant für automatisierte Tests.
  5. **Bild-Vollbild skaliert das Bild nicht hoch — gemessen.** Der Frame wächst korrekt auf den Viewport (`190×190` → **`1112×670`**, `position: fixed`), das `<img>` bleibt aber bei seiner **nativen Größe (256×256)**. Der Slice wird also nicht größer, nur die Umgebung dunkel. Für echte Detailarbeit an einer Schicht ist das zu wenig — Abhilfe: Bild vor dem Anzeigen auf die Zielauflösung hochskalieren (z. B. `to_isotropic` + Faktor) oder ein `st.dialog(width="large")`-Viewer mit eigenem Renderpfad.
- **Akzeptanz:** Im Browser verifiziert, dass alle vier Ansichten per nativem Vollbild die Bildschirmhöhe nutzen (oder begründet dokumentiert, warum nicht). Entscheidung zu Punkt 1–3 im Decision Log festgehalten. Ein Smoke-Test pinnt, dass die Vollbild-Buttons vorhanden bleiben.
- **Status:** ⚠️ Teilweise geprüft (Nov 10, 2026) — **3D-Vollbild voll nutzbar:** `399×700` → `1088×612`, Plotly baut auf die Viewport-Höhe um und ignoriert `height=700` dabei. **Bild-Vollbild nur eingeschränkt nutzbar:** Container füllt den Viewport (`1112×670`), Bild bleibt aber bei 256 px (Punkt 5). Offen: Entscheidung zu Punkt 1 und 5.

### `[x]` T-88 — Slice-Options-Panel: Readout-Zeilen bei Volumenwechsel konsistent halten
- **Ziel:** Das per-Plane-Readout im Slice-Options-Popover darf nicht auf veraltete Slice-Indizes zeigen, wenn sich die Volumen-Dimensionen ändern.
- **Hintergrund:** Mit T-86 liest der Readout die Indizes aus `raw_slices`, das **vor** dem Popover aus `st.session_state` gebaut wird; die Slider im Popover schreiben dieselben Keys. Die Reihenfolge (Clamp → `extract_slice` → Slider → Readout) ist damit korrekt, aber nur durch die Aufrufreihenfolge in `render_viewer_tab()`.
- **Prüfung:** Im Browser/`AppTest` nacheinander Volumen mit `(64,256,256)`, `(20,50,60)`, `(60,20,30)`, `(10,10,10)` geladen — keine Exception, kein Index über dem jeweiligen Maximum (Readout zeigt z. B. `20/20`, `20/60`, `10/10`).
- **Dateien:** `src/visualization/app.py` (unverändert), `tests/unit/test_app_integration.py`
- **Abhängig von:** T-86
- **Akzeptanz:** Ein Test lädt nacheinander Volumen mit unterschiedlichen Shape und prüft, dass der Readout-Index immer `<=` dem jeweiligen Maximum ist und kein `IndexError`/Widget-Key-Fehler auftritt.
- **Status:** ✅ Done (Nov 10, 2026) — Verhalten war bereits korrekt; `test_switching_to_a_smaller_volume_keeps_indices_valid` pinnt es jetzt gegen Regressionen (19 Tests in `test_app_integration.py`).

### `[x]` T-89 — Plan-Doku an tatsächliche Implementierung angleichen
- **Ziel:** `docs/plan.md` soll den Viewer-Stand korrekt beschreiben; mehrere Notizen sind durch T-86 überholt.
- **Überholte Stellen (in diesem Task korrigiert):**
  - „Implementation Notes → 3D Visualization Features": „Layout | Container pattern - 3D plot above options in sidebar" — ersetzt durch `All`/`2D`/`3D` plus schwebende Panels.
  - „Key Functions in app.py": `plot_slot` existiert nicht mehr — ersetzt durch `viewer_column_spec()` / `viewer_has_mpr()` / `viewer_has_3d()`.
  - „Offene Fragen → Erledigt (Tag 4-7)": nannte „Slice Options Expander für MPR" — jetzt als Popover vermerkt.
- **Dateien:** `docs/plan.md`
- **Abhängig von:** T-86
- **Akzeptanz:** Kein Verweis mehr auf `plot_slot`, „Expander" oder „plot above options"; die Viewer-Notes beschreiben `All`/`2D`/`3D` und die Popovers.
- **Status:** ✅ Done (Nov 10, 2026) — die drei Stellen korrigiert, zusätzlich zwei Risikozeilen (Stapel-Überlauf, 3D unter dem Fold) und ein „Erledigt (2026-11-10)"-Block ergänzt.

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
| 11 | Fr, 06.11. | T-67 ✅, T-68 ✅, T-69 ✅, T-70a–d ✅, T-79 ✅ (Backend in App + Verhalten getestet) |
| 12 | Mo, 09.11. | T-83 ✅, T-84 ✅, T-85 ✅ (Hintergrund-Start, In-Canvas-Geometrie-Schalter, Empty State; T-82 shelved) |

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
| D-10 | 2026-11-09 | Start lädt nichts automatisch; „Clear Cache" führt in denselben Empty State | Startup und Cache-Reset sind ein Zustand, ein Pfad; der Nutzer wählt Bilddaten oder Demo-Phantom |
| D-11 | 2026-11-09 | Geometrie-Overlay über Plotly-`updatemenus` im Canvas statt `st.toggle`/Rerun | clientseitiges Umschalten ohne Script-Rerun; PyVista kann als statisches PNG keinen interaktiven Schalter tragen (T-82) |
| D-12 | 2026-11-09 | `pitch = 0.0` als Default = zirkulärer Cone-Beam-Scan | entspricht dem Aufbau der Messdaten; nur negativer Pitch ist fachlich sinnlos |
| D-13 | 2026-11-10 | Viewer-Umschalter `All`/`2D`/`3D` über `st.radio(horizontal=True)` statt `st.segmented_control` | `segmented_control` gibt es erst ab 1.40, die Obergrenze bleibt wegen `use_column_width` bei `<1.40` |
| D-14 | 2026-11-10 | Kollabieren über Spaltenverhältnis `0.0001` statt `0` | rendert exakt 0 px; eine literale `0` lehnt `st.columns` mit `StreamlitInvalidColumnSpecError` ab |
| D-15 | 2026-11-10 | Umschalter **außerhalb** der Spalten | in einer kollabierten Spalte wäre er unerreichbar und der Nutzer in dieser Ansicht gefangen |
| D-16 | 2026-11-10 | `VIEWER_HEIGHT_PX = 700` (nicht 900) + `SCENE_DOMAIN_Y = [0.2, 1]` | bei 900 px begann die Canvas 362 px unter dem Seitenanfang und die Szene lief aus dem Bild; Plotly zentriert 3D-Szenen sonst im Canvas |
| D-17 | 2026-11-10 | MPR-Bilder mit `use_column_width=True`, kein fester Pixel-Cap | ein fester Cap läuft in einer schmalen Spalte über (gemessen: 260 px in 201 px); das 1:2-Verhältnis hält den Stapel stattdessen bei 685/700 px |
| D-18 | 2026-11-10 | Kein eigener Fullscreen-Code — native Mechanismen nutzen | `st.image` bringt „View fullscreen" mit, Plotly 7 eine Modebar-Schaltfläche; 3D-Vollbild verifiziert (`399×700` → `1088×612`) |

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
  - Slice Options als Popover (früher: Expander) — T-86
  - Viewer-Layout `All`/`2D`/`3D` mit gestapelten MPR-Ebenen — T-86

### Noch offen
- T-23.8: Tests für volume3d.py
- Mouse-Wheel-Scrolling über Bilder
- T-61: parallelproj Dependency (teilweise — conda-env `ct-viewer`, nicht als pip-Dep)

## Erledigt (2026-11-10)

- ✅ T-86: Viewer-Layout `All`/`2D`/`3D`, gestapelte MPR-Ebenen (700 px, `border=False`), 2×2-Raster in `2D`, beide Options-Panels als `st.popover`, Slice-/Spacing-Readout ins Panel verschoben, 3D-Build in `2D` übersprungen; `streamlit>=1.37` (`b0687d2`)
- ⚠️ T-87: Fullscreen — 3D voll nutzbar (`399×700` → `1088×612`), Bild-Vollbild füllt den Viewport (`1112×670`), skaliert das Bild aber **nicht** hoch (bleibt 256 px). Entscheidung offen.
- ✅ T-88: Readout-Konsistenz beim Volumenwechsel geprüft und per Test gepinnt (`test_switching_to_a_smaller_volume_keeps_indices_valid`)
- ✅ T-89: Plan-Notizen (`plot_slot`, „Expander", „plot above options") korrigiert

## Erledigt (2026-11-09)

- ✅ T-83: Background-Startup-Load (Job-Registry, `st.fragment`-Polling, Deadline, `reset_job` bei Clear Cache)
- ✅ T-84: Geometrie-Overlay als In-Canvas-On/Off-Buttons; „Show Trajectory" entfernt; PyVista aus der UI genommen (T-82)
- ✅ T-85: Kein Auto-Load + Empty State, englische UI, Zirkulärscan-Defaults (`pitch=0.0`, 2304 Projektionen, 1/100 Downsample), sichtbare Richtungspfeile (`sizemode="raw"`, `ARROW_LENGTH_MM`)
- ⚠️ T-82: PyVista-Render-Modus shelved (statisches PNG kann keinen In-Canvas-Schalter tragen)
- ✅ T-81: Smoke-Test-Modul jetzt bei ~5 s (vorher 22 s) — die Beseitigung des PyVista-Imports aus dem Startpfad hat das Laufzeit-Ziel erreicht

## Erledigt (2026-11-06)

- ✅ T-67: Comparison Module (`visualization/comparison.py`)
- ✅ T-68: Real-vs-Simulated-Ansicht mit Differenzbild
- ✅ T-69: End-to-End-Integrationstest mit echtem parallelproj
- ✅ T-70a: Messdaten-Auswahl/‑Load in der Sidebar
- ✅ T-70b: Geometry-Tab (Parameter lesen + anpassen)
- ✅ T-70c: Real-vs-Simulated-Tab (Forward Projection + Metriken)
- ✅ T-70d: Headless-UI-Tests via Streamlit `AppTest` — ⚠️ entfernt (zu langsam, siehe T-81)
- ✅ T-79: Non-contiguous Projection-Selection-Fix

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
| Render Mode | Iso-Surface (Plotly). PyVista shelved — see T-82 |
| Geometry Overlay | In-canvas "Projection Geometry" On/Off buttons (no rerun) |
| Opacity Controls | Volume Opacity (0.1-1.0), Surface Opacity (0.1-1.0) |
| Camera Presets | iso, front, back, left, right, top, bottom |
| Source/Detector | Auto or manual positioning |
| Isocenter | Auto (from volume center) or manual (x, y, z) |
| Downsample | 1x, 2x, 4x (default) for performance |
| Layout | `All` / `2D` / `3D` switcher; MPR stacked left, 3D right; option panels float as popovers |

### Key Functions in app.py
| Function | Purpose |
|----------|---------|
| `setup_image_interaction()` | JavaScript for keyboard/click navigation via components.html |
| `slice_slider()` | Slider + anchor div + jump buttons |
| `to_isotropic()` | Resample for correct aspect ratio |
| `clamp_slice_state()` | Clamp session state values before widget creation |
| `viewer_column_spec()` | Column widths for a viewer mode (`All` = `[1, 2]`) |
| `viewer_has_mpr()` / `viewer_has_3d()` | Whether a mode renders that side at all |

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
| MPR-Stapel läuft in schmaler Spalte über | T-86: `use_column_width=True` statt Pixel-Cap; 1:2-Verhältnis hält den Stapel bei 700 px |
| `VIEWER_HEIGHT_PX` zu hoch → 3D unter dem Fold | T-86: 700 px + `SCENE_DOMAIN_Y = [0.2, 1]` |
| Zeitplan reißt | T-23 ist explizit optional |


