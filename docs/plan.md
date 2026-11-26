
# CTBeamStudio — Implementierungsplan

**Projekt:** `Res_Indep_CTO` / `src/visualization/`
**Stand:** 2026-11-19
**Start:** Mi, 2026-10-14

## Leitprinzipien

| Prinzip | Konsequenz |
|---|---|
| Keine Daten im Repo oder Image | nur Phantom + synthetische Fixtures |
| `pydicom` ausschließlich | kein SimpleITK, kein ITK |
| Viewer ohne Torch | separate Dependency-Gruppen |
| Datenintern HU | Normalisierung nur in der Darstellung |

## Phasen, Themen und Nummernkreise

Die Nummern vergibt das Projekt **unveränderlich** — sie stehen in
Code-Kommentaren, Tests, CI-Workflows, Specs und Commit-Messages (knapp 800
Fundstellen). Alte Nummern sagen deshalb nichts über ihr Thema; das Thema liefert die
**Phase**, und dorthin gehört der Eintrag.

**Neue Nummerierung ab dem nächsten Eintrag:** `T-<Phase>-<NN>`, wobei `<Phase>` die
Nummer aus der Tabelle unten ist und `<NN>` eine zweistellige Fortlaufnummer **pro
Phase**, beginnend bei `01`. Die nächste neue Aufgabe in Phase 11 heißt damit
`T-11-01`, die nächste in Phase 12 `T-12-01`. Alle bestehenden Nummern `T-01` bis
`T-110` bleiben unverändert — die gemischte Schreibweise in der Tabelle ist gewollt.
Unstrukturierte neue Nummern ab `T-111` werden nicht mehr vergeben.

| Phase | Thema | Nummern |
|---|---|---|
| 0 | Lizenz & Hygiene | T-01 – T-04 |
| 1 | Kern & Backend (`Volume`, Loader, MPR, Restrukturierung) | T-10 – T-14, T-78, T-01-01 |
| 2 | App (Viewer, Sidebar, Panels) | T-20 – T-23 |
| 3 | Tests & Tooling | T-30 – T-33, T-81, T-91 |
| 4 | Deploy (Dockerfile, CI) | T-40 – T-44 |
| 5 | Projection Geometry | T-50 – T-53 |
| 6 | Projection-Geometrie in 3D | T-54 – T-56a |
| 7 | Docker Self-Deployment | T-71 – T-74 |
| 8 | Forward Projection & Attenuation | T-61 – T-63, T-79, T-80, T-108, T-08-01, T-08-02 |
| 9 | Sinogram & Messdaten | T-64 – T-66, T-90, T-92, T-93, T-98, T-102 |
| 10 | Vergleich simuliert vs. gemessen | T-67 – T-69 |
| 11 | App & Viewer (Integration, Layout, 3D) | T-70, T-82 – T-89, T-94 – T-97, T-99 – T-101, T-103, T-109, T-110, T-11-01 – T-11-03 |
| 12 | Release Readiness | T-104 – T-107 |
| – | Research-Backlog | T-75 – T-77 |

**Neue Aufgabe:** `T-<Phase>-<NN>` nach der Regel oben, Eintrag unter der Phase
ihres Themas — nicht ans Dateiende. Wird eine Aufgabe thematisch falsch einsortiert
vorgefunden, wandert der Eintrag, nie die Nummer.

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

## Phase 1 — Kern & Backend (Tag 2–4)

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

### `[x]` T-78 — Backend-Restrukturierung (Refactor)
- **Ziel:** Numerisches / Daten-Backend von der UI trennen (one-way dependency: `visualization` → `backend`).
- **Dateien:** `src/backend/{volume,geometry,forward_project}.py`, `src/backend/loaders/`, Paketierung `pyproject.toml`
- **Abhängig von:** T-63
- **Akzeptanz:** `Volume`, `ProjectionGeometry`, `forward_project` und Loader (dicom, npy, projection) liegen unter `src/backend/`; `import backend` funktioniert ohne parallelproj (lazy); alle Imports (UI, Tests, Skripte) aktualisiert; Testsuite grün.
- **Status:** ✅ Done (Nov 4, 2026) — siehe Spec `docs/superpowers/specs/2026-11-04-backend-restructure-design.md`.

### `[x]` T-01-01 — DICOM-Origin in das FP-Weltkoordinatensystem umrechnen
- **Ziel:** Der DICOM-Loader reorientiert das Gitter in das Projekt-Frame (x = anterior, y = links), lieferte den Origin aber als rohes DICOM-LPS. Bei off-center- oder rechteckigen Volumina landet die FP dadurch gespiegelt/versetzt. Audit-Finding #6.
- **Dateien:** `src/backend/loaders/dicom.py`, `src/backend/volume.py`, `src/backend/forward_project.py`, `src/visualization/volume3d.py` (Doku/Kommentare), `docs/geometry.md`, `tests/unit/test_dicom_loader.py` (1 neuer Test + Origin-Assertion), `docs/audit-2026-11-13-findings.md`
- **Abhängig von:** T-11, T-94
- **Umsetzung:** Für `standard_axial`: `origin = (-(y_LPS + (nrows - 1) * row_spacing), x_LPS, z_first)` — dieselbe Transformation wie beim geflippten/transponierten Gitter. Nicht-axiale Daten behalten den Roh-Origin (Gantry-Tilt bleibt Warnung).
- **Akzeptanz:** Origin des ersten Voxels liegt im Projekt-Frame, FP und 3D-Ansicht nutzen dieselbe Position; der zentrierte quadratische Fall bleibt unverändert; volle Suite grün, 0 Skips.
- **Status:** ✅ Done (Nov 19, 2026) — 1 neuer Test für off-center/Rechteck (IPP (20.0, −30.0, 5.0), 4×6, Spacing (0.5, 0.8) → Origin (28.5, 20.0, 5.0)); Reorientierungs-Test pinnt den zentrierten Fall (−1.5, 0.0, 0.0). `Volume.origin` in Dataclass, FP, 3D-View und `docs/geometry.md` als Projekt-Frame dokumentiert; Audit #6 auf `fixed`. Suite grün, 0 Skips (Git Bash auf PATH); flake8/black/isort sauber.

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
| T-23.8 | Tests für volume3d.py | T-30 | ✅ Done (Nov 13, 2026) — durch T-94 abgedeckt (`tests/unit/test_volume3d.py`, 5 Tests: Origin-Platzierung, Downsample-Shift, Detektor-Konvention, Legacy-Pfad) |

#### Technische Entscheidungen

| Entscheidung | Optionen | Favorit |
|--------------|----------|---------|
| 3D-Bibliothek | PyVista, Plotly | **Plotly** (keine VTK-Kompatibilitätsprobleme auf Windows) |
| Volumen-Darstellung | Dropdown-Menu: "Iso-Surface" (default), "Volume Rendering" | Beide wählbar, **Standard: Iso-Surface** |
| Koordinatensystem | Patient, Slice, Scanner | Patient (DICOM-Standard) |
| Detektor-Positionierung | Fixed SID, berechnet aus Gantry | Fixed SID (1000mm default) |
| Volumen-Positionierung | Isocenter im Ursprung (0,0,0) | Volumen zentriert am Ursprung |

## Phase 3 — Tests & Tooling (Tag 5–6)

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

### `[x]` T-91 — Conda-Env `ct-viewer` verbindlich, keine übersprungenen Tests

- **Ziel:** Projektbefehle laufen ausschließlich im Conda-Env `ct-viewer`; die Suite meldet keine Skips mehr.
- **Hintergrund:** `pytest` mit dem System-Python (3.13) übersprang die vier parallelproj-Tests, weil `parallelproj_c.dll` nur im aktivierten Env auf `PATH` liegt — die Tests *liefen* also nie, obwohl sie im Repo vorhanden sind. Zusätzlich behauptete `LINTING.md`, `flake8`/`black`/`isort` seien **nicht** im Env installiert und müssten vom System-Python laufen; tatsächlich sind sie über das `dev`-Extra im Env vorhanden.
- **Umsetzung:**
  1. Neu: `AGENTS.md` (auto-geladen) mit verbindlicher Env-Regel, exakten Aktivierungsbefehlen, Lint-Reihenfolge, Hard Rules und Test-Bar.
  2. `LINTING.md`: falsche Tool-Verfügbarkeit korrigiert (alle drei im Env, ein Interpreter für Lint und Tests).
  3. `pyproject.toml`: `nibabel` zusätzlich in `dev` — die Suite deckt NIfTI-Laden ab, ohne nibabel skippen diese vier Tests still. Damit genügt `.[dev]` für einen vollständigen Lauf; `nifti` bleibt das reine Laufzeit-Extra.
  4. `environment.yml` und `.github/workflows/ci.yml`: bei `.[dev]` belassen (deckt nibabel jetzt ab).
  5. `INSTALLATION.md`: die dokumentierten `.[cpu]`/`.[gpu]`-Befehle entfernt — diese Extras existieren in `pyproject.toml` **nie** (per `git log -S` geprüft) und `pip` akzeptiert `.[irgendwas]` ohne jede Warnung, installiert aber nichts; ersetzt durch die tatsächlichen conda-Befehle. Ebenso `parallelproj.__version__` (existiert nicht) und `parallelproj_core` (Modul existiert nicht) korrigiert zu `parallelproj.cuda_present`.
  6. `docs/local-environment.md`, `docs/README.md`, `AGENTS.md`: Env als Pflicht dokumentiert, Test-/Lint-Befehle mit Aktivierung, Docs-Index ergänzt.
- **Dateien:** `AGENTS.md` (neu), `LINTING.md`, `pyproject.toml`, `environment.yml`, `.github/workflows/ci.yml`, `INSTALLATION.md`, `docs/local-environment.md`, `docs/README.md`
- **Abhängig von:** T-69
- **Akzeptanz:** `python -m pytest -q -rs` im Env `ct-viewer` endet mit „0 skipped"; `flake8` (Projekt-Ignore-Set), `black --check`, `isort --check-only` laufen im selben Env fehlerfrei.
- **Status:** ✅ Done (Nov 12, 2026) — Env 3.11.18 mit parallelproj, torch, nibabel, flake8/black/isort. Suite: **301 passed, 0 skipped** (~25–40 s), vorher 293 passed / 2 skipped im System-Python bzw. 297/4 im Env ohne nibabel. `flake8 --count` = 0, `black --check` 60 Dateien unverändert, `isort --check-only` exit 0. Zusatzbefund: `.[cpu]`/`.[gpu]` waren nur in der Doku vorhanden, nie in `pyproject.toml`; `pip install -e ".[bogus]"` warnt nicht und installiert nichts — die Doku führt jetzt die conda-Befehle.

## Phase 4 — Deploy (Tag 6)

### `[x]` T-40 - Dockerfile
- **Dateien:** `../Dockerfile`, `.dockerignore`
- **Abhängig von:** T-03, T-22
- **Akzeptanz:** Multi-Stage, kein Torch/CUDA, Non-Root-User, Image < 400 MiB, startet ohne Mount im Demo-Modus, Build-Guard aus T-03 aktiv.

### `[x]` T-41 — CI
- **Dateien:** `.github/workflows/ci.yml`
- **Abhängig von:** T-31, T-40
- **Akzeptanz:** Lint + Tests bei jedem PR; Daten-Guard läuft; Push nach GHCR nur auf `main` und Tags; PRs bauen ohne Push.
- **Status:** ⚠️ Teilweise (Nov 17, 2026) — Lint, Tests und Daten-Guard laufen; ein GHCR-Push-Job existiert in `ci.yml` **nicht**. Veröffentlichung siehe T-105.

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

## Phase 6 — Projection-Geometrie in 3D (Oct 26, 2026)

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

- **Status:** ❌ Dropped (Nov 13, 2026) — `st.text_input` bleibt; Demo-/Restore-Flows verringern den Bedarf, keine neue Dependency (`streamlit-explorer`).

## Phase 7 — Docker Self-Deployment (Nov 13: CI-Route statt lokalem Docker)

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

### `[ ]` T-73 — Docker-Image in CI bauen und verifizieren
- **Ziel:** Das Image verifizieren, ohne Docker lokal zu installieren (Route-Entscheidung Nov 13, 2026).
- **Dateien:** `.github/workflows/ci.yml`, `Dockerfile`
- **Abhängig von:** T-71, T-72
- **Akzeptanz:**
  - `:slim` (`docker build .`, Viewer ohne Projektion) startet, Port 8501 antwortet, Image < 400 MiB.
  - `:full` (`--target full`, Kunden-Image mit parallelproj + torch CPU) startet, Port 8501 antwortet, und der Build bricht ab, wenn `PARALLELPROJ_AVAILABLE` nicht `True` ist (Smoke-Test im Dockerfile). Größe ~1,6 GB, also gilt die 400-MiB-Grenze nur für `:slim`.
  - Kein lokaler Build nötig.
- **Status:** ⚠️ Open (Nov 17, 2026) — Dockerfile hat jetzt die Targets `slim`/`full` inkl. Build-Zeit-Smoke-Test, aber **unverifiziert**: auf diesem Rechner ist kein Docker installiert, und der CI-Job fehlt noch.

### `[ ]` T-74 — Create Run Script
- **Ziel:** Komfort-Script zum Starten des Containers.
- **Dateien:** `scripts/run-docker.sh`, `scripts/run-docker.ps1`
- **Abhängig von:** T-73
- **Akzeptanz:** Script baut `--target full`, mountet ein Datenverzeichnis read-only und startet den Container auf Port 8501.
- **Status:** ⚠️ Beide Scripts liegen (Nov 17, 2026); `run-docker.ps1` baut `full`, mountet `-v <daten>:/data:ro` und pollt `/_stcore/health` — Syntax geprüft, Lauf gegen echtes Docker steht aus (kein Docker auf dem Rechner).

## Phase 8 — Forward Projection with Parallelproj (Oct 27, 2026)

### `[x]` T-61 — Add parallelproj Dependency
- **Ziel:** parallelproj als Dependency hinzufügen.
- **Dateien:** `requirements.txt` oder `pyproject.toml`
- **Abhängig von:** –
- **Akzeptanz:** `import parallelproj` funktioniert.
- **Status:** ✅ Done by design (Nov 13, 2026) — `parallelproj` ist conda-forge-only und kann kein pip-Extra sein (D-22); verbindlich dokumentiert in `AGENTS.md`/`environment.yml`, Installation nur im Env `ct-viewer`.

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

### `[x]` T-108 — Fortschritt der Forward Projection (x/y Projektionen)
- **Ziel:** „Run Forward Projection“ zeigt x/y Projektionen statt nur eines Spinners, damit ein Lauf über die volle Geometrie (bis 2304 Projektionen) sichtbaren Fortschritt hat.
- **Dateien:** `src/backend/forward_project.py` (Chunking + `progress=`-Callback), `src/visualization/projection_panel.py` (`st.progress` + Text), `tests/unit/test_forward_project.py`
- **Abhängig von:** T-63, T-79, T-104
- **Umsetzung:**
  1. `forward_project(..., progress=callback(done, total))` projiziert in Chunks (`min(32, n_projs // 10)` Projektionen, also ~10 Updates) statt in einem einzigen joseph3d-Aufruf; der Zeros-Fallback meldet einmal `(n, n)`.
  2. Die Helix-Zentrierung bekommt `n_projections_total or n_projs` übergeben, sonst würde jeder Chunk auf seine eigene Länge neu zentrieren (der Helix-Test deckt das ab).
  3. Die UI rendert eine Progress-Bar mit „Forward projecting x/y projections“ und räumt sie nach dem Lauf ab.
- **Akzeptanz:** `done` wächst monoton und endet bei `total`; das Ergebnis ist identisch mit einem ungechunkten Lauf; die UI zeigt den Zähler.
- **Status:** ✅ Done (Nov 19, 2026) — Neuer Test `test_forward_project_reports_progress_and_chunking_is_transparent` (Callback-Sequenz + Chunk-Ergebnis == Einzelprojektion); Helix-Tests decken die Zentrierung ab. Test-Bar 362 → 363.

### `[x]` T-08-01 — Device-unabhängige Forward Projection (echte CUDA-Unterstützung)
- **Ziel:** Forward Projection läuft auf CUDA ohne `TypeError: can't convert cuda:0 device type tensor to numpy`; CPU und GPU liefern innerhalb einer gemessenen float32-Toleranz dasselbe Ergebnis.
- **Hintergrund:** `forward_project` defaultet `use_cuda=True`, die UI-Checkbox ist an, und `ConeBeamGeometry.calculate_xray_beam_list(dev="cuda")` erzeugt CUDA-Tensoren. `ConeBeamProjector` ruft in `__init__`, `apply` und `adjoint` `np.asarray` darauf auf — Audit-Finding #1, am 19.11.2026 auf 8× RTX A6000 reproduziert: erster Lauf py3.12 + `parallelproj 2.0.2`/cuda130, 340 passed / 19 failed; nach der Versions-Korrektur py3.11 + `parallelproj 1.10.2`/cuda129 dieselbe Ursache, 370 passed / 20 failed / 0 skipped. Ein GPU-gebautes `libparallelproj` konnte im 2.0.7-Lauf CPU-Input nicht verarbeiten: mit `CUDA_VISIBLE_DEVICES=""` 336 passed / 23 failed, `cudaSetDevice failed`; für 1.10.2 ergab derselbe Lauf nach dem Fix 398 passed / 0 skipped, der OpenMP-Fallback greift dort also. Details in `docs/superpowers/specs/2026-11-19-gpu-forward-projection-design.md` (Kapitel „Evidence").
- **Versions-Entscheidung (Nov 19, 2026):** Der scheinbare Deadlock („py3.11+1.3.5 importiert nicht, App braucht 2.x, 2.x hat keine py3.11-Builds") kam von einem falschen Pin in INSTALLATION.md. Verifiziert im lokalen Env: py3.11.18 + `parallelproj` **1.10.2** + `libparallelproj` 1.10.2 (cpu); `parallelproj.projectors.ListmodePETProjector` und `backend.parallelproj` importieren. 1.10.x hat auch CUDA-Builds (`cuda129*`/`cuda130*`), 2.x braucht py3.12 und ist nicht nötig. `environment.yml` pinnt jetzt 1.10.x.
- **Dateien:** `src/backend/parallelproj/projector.py` (Konversions-Grenze), `src/backend/forward_project.py` (Device-Durchreichung), `tests/unit/test_parallelproj.py`, `tests/unit/test_forward_project.py`, `tests/integration/test_projection_workflow.py`, `scripts/verify_forward_projection.py`, `scripts/forward_projection_plot.py`, `environment.yml`, `INSTALLATION.md`, `docs/audit-2026-11-13-findings.md`, `AGENTS.md`
- **Abhängig von:** T-63, T-79, T-91, T-108
- **Umsetzung:**
  1. Upstream-Vertrag von `parallelproj` 1.10.2 aus dem installierten Quelltext geklärt: `joseph3d_fwd` entscheidet anhand des **Bild-Arrays**. Host-numpy nimmt die Hybrid-Route (CUDA-Lib, wenn Geräte sichtbar sind, sonst OpenMP), CUDA-Torch braucht `cupy`. Damit ist Host-numpy die CUDA-Route ohne neue Abhängigkeit; `CUDA_VISIBLE_DEVICES=""` fällt laut Quelle auf OpenMP und wurde auf der A6000 mit 398 passed / 0 skipped bestätigt.
  2. `_as_numpy_xyz` durch `_as_host_array` / `_to_operator_input` / `_from_operator_output` ersetzt; `__init__`, `apply` und `adjoint` nutzen nur noch diese. Jedes `np.asarray` auf einem möglicherweise-CUDA-Tensor ist weg; Input bleibt `float32`, `(n, 3)`, contiguous; Shape/Reihenfolge der Projektionen unverändert.
  3. Kein `device`-Argument an `ConeBeamProjector`: mit Host-numpy-Input wäre es unbenutzt. `dev` wählt weiterhin nur, wo die LOR-Geometrie entsteht; das Volume bleibt Host-numpy, weil parallelproj die Kopie aufs Gerät selbst macht. Chunking (32), Helix-Zentrierung und Progress-Callback unverändert.
  4. Vier Tests ohne neue Skip-Guards in `tests/unit/test_parallelproj.py`: Fake-Device-Tensor mit werfendem `__array__`, `_from_operator_output`, gestubbter `ListmodePETProjector` und ein Available-Device-LOR-Vergleich (`cuda:0` falls vorhanden, sonst `cpu`). Suite im `ct-viewer`: 398 passed, 0 skipped (mit Git Bash; ohne Bash die 4 dokumentierten `test_release_push`-Fehler).
  5. Auf echter GPU: Suite (0 Skips), Lauf mit `CUDA_VISIBLE_DEVICES=""`, VRAM-Spitze, Browser-Lauf mit Checkbox an/aus; Results in den Status schreiben. Echte CUDA-Kernel laufen nur hier — manuell, mit Status-Eintrag (Präzedenz T-109/T-83), kein Skip-Guard.
  6. Hilfsskripte wählen CUDA automatisch (wie die App) und haben `--cpu`; sie drucken LOR-Device und die von parallelproj gesehenen CUDA-Geräte. Die UI-Hilfe sagt jetzt, dass die Checkbox nur die LOR-Geometrie steuert, nicht den Kernel. INSTALLATION.md und Audit #1 stehen auf dem verifizierten Stand; Test-Bar in AGENTS.md 394 → 398.
- **Akzeptanz:** Suite in CPU- und GPU-Env je 0 Skips; CPU-Ergebnisse bitgleich wie vorher; GPU-Ergebnisse innerhalb der gemessenen Toleranz identisch; Browser-Verifikation auf GPU-Maschine dokumentiert. Kein Eingriff in Docker-Image oder CI (beide bleiben CPU).
- **Status:** ✅ Done (Nov 19, 2026) — Konversions-Grenze in `projector.py`, 4 neue Tests, Suite **398 passed / 0 skipped** auf CPU (lokal ohne Git Bash die 4 dokumentierten `test_release_push`-Fehler) und **398 passed / 0 skipped** im GPU-Env (py3.11.18 + `parallelproj 1.10.2` + `libparallelproj 1.10.2=cuda129` + `pytorch 2.9.1=cuda129` + `cuda-toolkit 12.9.2`, 8× RTX A6000, Commit `d184122`). GPU-Gate: `CUDA_VISIBLE_DEVICES=""` ebenfalls 398 / 0 (OpenMP-Fallback bestätigt, Fehler #2 gilt für 1.10.2 nicht); Volle Geometrie `(60, 192, 512)` mit 36.8 MB `torch.cuda.max_memory_allocated` / 386 MB `nvidia-smi`-Delta; Checkbox an/aus über die Projektions-API bitgleich und nicht-null (Summe 20.4678, Max 0.09999), Streamlit auf der GPU-Maschine projiziert mit dem Fix. Audit #1 → `fixed`, INSTALLATION.md „verified". Spec `docs/superpowers/specs/2026-11-19-gpu-forward-projection-design.md`, Plan `docs/superpowers/plans/2026-11-19-gpu-forward-projection.md`.
- **Siehe auch:** Audit-Finding #1 (`docs/audit-2026-11-13-findings.md`), INSTALLATION.md „GPU setup".

### `[x]` T-08-02 — Source-Z-Offset in der Forward Projection
- **Ziel:** `ProjectionGeometry.source_offset_z` verschiebt nicht nur die 3D-Trajektorie, sondern auch die simulierten Strahlen.
- **Hintergrund:** Das UI kennt `Source Offset Z (mm)` und `volume3d` zieht die Quelle mit, der Projektor ignorierte den Wert aber: `calculate_xray_beam_list` nutzte nur `z_offset_mm` (Volume-Zentrum) und den Helix-Vorschub. Simulierte und gemessene Projektion konnten dadurch in z versetzt liegen.
- **Dateien:** `src/backend/parallelproj/geometry.py`, `src/backend/forward_project.py`, `src/visualization/volume3d.py`, `tests/unit/test_parallelproj.py`, `tests/unit/test_forward_project.py`, `docs/geometry.md`, `docs/superpowers/specs/2026-11-12-3d-view-real-world-origin-design.md`, `AGENTS.md`
- **Abhängig von:** T-63, T-104
- **Umsetzung:**
  1. `calculate_xray_beam_list(..., source_offset_z_mm=0.0)` addiert den Offset auf die per-Projektion-z; Quelle und Detektor teilen ihn, die Rotation bleibt unverändert.
  2. `forward_project` reicht `geometry.source_offset_z` durch; `get_detector_position` in `volume3d` zieht ebenfalls nach (vorher nur die Quelle).
  3. Tests: LOR-Start/End verschieben sich in z ohne x/y-Änderung; `source_offset_z` ändert das FP-Ergebnis; FP ↔ 3D-Trajektorie stimmen auch bei Offset überein.
- **Akzeptanz:** Offset 0 bleibt unverändert; Suite grün, 0 Skips; Test-Bar angepasst.
- **Status:** ✅ Done (Nov 19, 2026) — `source_offset_z_mm` in `calculate_xray_beam_list` verschiebt Quelle und Detektor; `forward_project` reicht den Feldwert durch, `get_detector_position` zieht in der 3D-Ansicht nach. Neue Tests: LOR-Offset ohne x/y-Änderung, FP-Ergebnis ändert sich mit dem Offset, FP ↔ 3D-Trajektorie auch bei Offset (bestehender Test erweitert). Offset 0 bleibt unverändert. Suite 390 passed, 0 skipped.

## Phase 9 — Sinogram & Messdaten

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

### `[x]` T-90 — Sinogramm-Achsenreihenfolge wirkt auch für DICOM-Ordner und sofort

- **Ziel:** Die Auswahl „File axis order" im Measurements-Panel muss das geladene Bild tatsächlich umorientieren — für jeden Formatpfad und ohne zweiten Klick auf „Load Measurements".
- **Hintergrund (gemeldeter Fehler):** Bei einem DICOM-Projektionsordner änderte die Auswahl nichts. `_load_dicom` nahm `axis_order` entgegen, benutzte es aber nie und schrieb `source_axis_order=("proj","row","col")` fest; der Setter fiel danach in den Re-Read-Zweig, der wieder über `_load_dicom` lief — die Auswahl war an jeder Stelle wirkungslos. Bei `.npy`/NIfTI wurde die Reihenfolge korrekt angewandt, aber nur beim nächsten Klick auf „Load Measurements", weil der Selectbox-Wert ausschließlich im `if clicked:`-Zweig gelesen wurde.
- **Umsetzung:**
  1. `_load_dicom` reicht `axis_order` an `_finish_sinogram` weiter; der native DICOM-Stapel `(proj,row,col)` wird gemäß Deklaration transponiert (z. B. `proj → col → row` ⇒ Rahmen `(n_rows,n_cols)` → `(n_cols,n_rows)`). Die Zeilen-/Spaltenselektion bleibt kanonisch.
  2. Lazy-Read bleibt erhalten, wenn `proj` auf der ersten Dateiachse liegt (dann wird die Projektionsauswahl weiterhin header-only aufgelöst); bei jeder anderen Reihenfolge liegen die „Projektionen" nicht mehr auf den Dateien, also werden alle Rahmen gelesen und die Auswahl kanonisch aufgelöst.
  3. `apply_axis_order_change()` im UI wendet die Auswahl sofort über den vorhandenen `SinogramData.axis_order`-Setter an (In-Memory bei Volllast, sonst Re-Read) und ist bei unveränderter Reihenfolge ein No-op.
  4. Setter um den Fall „kein Roharray, kein `path`" ergänzt (in-memory erzeugte Daten): reine Transposition zwischen alter und neuer Deklaration über `_reorder_canonical`.
- **Dateien:** `src/backend/loaders/sinogram.py`, `src/visualization/projection_panel.py`, `tests/conftest.py` (Fixture-Variante `graded=True`), `tests/unit/test_sinogram_loader.py`, `tests/unit/test_projection_panel.py`, `tests/integration/test_ui_smoke.py`
- **Abhängig von:** T-64, T-65
- **Akzeptanz:** Ein DICOM-Ordner mit deklarierter Reihenfolge `("proj","col","row")` liefert `data.shape == (n_proj, n_cols, n_rows)` und `source_axis_order` wie deklariert; ein Wechsel nach dem Laden orientiert um; die UI wendet die Auswahl ohne erneuten Lade-Klick an.
- **Status:** ✅ Done (Nov 12, 2026) — 5 neue Loader-Tests, 3 Helper-Tests, 1 UI-Test. Nachweis mit künstlichen DICOM-Serien (3 Rahmen, 4×6, je Rahmen ein eigener Gradient, damit eine Transposition sichtbar ist): `proj,row,col` → `(3,4,6)`, `proj,col,row` → `(3,6,4)`, Setter hin und zurück reversibel. `_reorder_canonical` zusätzlich gegen einen vollständigen Re-Derive über alle 36 Reihenfolge-Übergänge geprüft (0 Abweichungen). Volle Suite: 301 passed, 0 skipped.

### `[x]` T-92 — Sinogram-Loader: Lazy Subset-Reads für große Dateien
- **Ziel:** Subset-Auswahl (Zeilen/Spalten/Projektionen) aus großen `.npy`-/NIfTI-Dateien lesen, ohne die ganze Datei in den RAM zu laden — gemäß der in `docs/superpowers/plans/2026-11-04-sinogram-loader.md` vorgesehenen, aber nie umgesetzten mmap-/dataobj-Slices. DICOM bleibt unverändert (T-65 liest bereits nur die gewählten Projektionen, frame-weise).
- **Dateien:** `src/backend/loaders/sinogram.py`, `tests/unit/test_sinogram_loader.py`, `docs/superpowers/specs/2026-11-12-sinogram-lazy-subset-reads-design.md` (neu)
- **Abhängig von:** T-90
- **Umsetzung:**
  1. `.npy`: Subset → `np.load(path, mmap_mode="r")`; die bestehende `_apply_selection` (transpose + `np.ix_`) materialisiert nur die Auswahl, der Rest der Datei wird nie gelesen. Vollauswahl bleibt auf dem eager-Pfad (`_raw_file_order` hält das Roharray für die In-Memory-`axis_order`-Ableitung). `.npz` (Zip-Container) kann nicht gemappt werden — bleibt eager.
  2. NIfTI: Jede Dateiachse, deren kanonischer Modus als Basic-Slice ausdrückbar ist (`central`/`range`/`downsample`), wird vor dem Materialisieren über `img.dataobj[slice_tuple]` auf der Platte vorgeschnitten (ein Read, nur der gewählte Bereich); vorgeschnittene Achsen werden in `applied_selection` auf `"all"` gesetzt — dasselbe Muster wie im DICOM-Loader. `custom`-Indexlisten brauchen Fancy-Indexing, das der Proxy nicht kann (verifiziert in nibabel 5.5.0: `ArrayProxy`/`slicer` werfen „Cannot handle fancy indexing") → voller Read-Pfad wie bisher.
  3. Validierung bleibt erhalten: ungültige `range_` (leer/außerhalb) werden nicht vorgeschnitten, sodass `resolve_indices` weiterhin `IndexError`/`ValueError` wirft — ein `slice` würde Out-of-Bounds stillschweigend clampsen. Neue Helfer: `_is_full_selection` (nutzt auch `_finish_sinogram` statt der doppellten Bedingung), `_selection_axis`, `_mark_axis_all`, `_basic_slice_for_axis`.
- **Akzeptanz:** Subset-Loads liefern exakt die Daten der eager-Variante; Tests belegen mmap (Spy auf `np.load`: `mmap_mode="r"` bei Subset, `None` bei Vollauswahl) bzw. Basic-Slice-Read (Spy auf `ArrayProxy.__getitem__`: ein Slice-Tuple, nie ein Voll-Read); Vollauswahl und Fehlerverträge unverändert; Suite grün ohne neue Skips.
- **Status:** ✅ Done (Nov 12, 2026) — 10 neue Tests (3 numpy/npz, 7 NIfTI inkl. downsample, Mehrachsen- und transponiertem Subset). `test_sinogram_loader.py`: 48 passed. `SinogramData.lazy` bleibt `False` (Auswahl ist nach dem Load materialisiert; Lazy ist Read-Zeit, nicht Zugriffszeit) — chunk-weises Streamen durch die Vorwärtsprojektion bleibt out of scope. `SinogramData`/UI/`forward_project` unverändert.

### `[x]` T-93 — Dummy-Messung: 3D-Shepp-Logan-FP + Streuung + Rauschen
- **Ziel:** Ein künstliches „gemessenes" Sinogramm für das Demo-Phantom — 3D-Shepp-Logan-Forward-Projektion + Streuung + Poisson-Rauschen — per Knopfdruck im Measurements-Panel, als kohärentes Demo-Trio (Volumen + Geometrie + Messung) für den Sinogram-Inspection-Vergleich ohne echte Messdaten.
- **Hintergrund:**
  - Das Demo-Phantom ist bereits in Standard-Kopfgröße (~138 × 184 × 180 mm im 192-mm-FOV, durch `test_head_dimensions_match_phantom_geometry` gepinnt); die Dummy-Messung nutzt genau diese Größe, kein geschrumpftes Spielzeug-Volumen.
  - Die Default-Geometrie (64 Detektorzeilen × 1 mm) überstreicht nur ~32 mm in z auf der Isocenter-Ebene — ein kopfgroßes Phantom würde auf einen Slab zugeschnitten. Die Dummy-Geometrie (192 Zeilen × 2 mm, 512 Spalten × 1 mm, 60 Views/Rotation) überstreicht 192 mm in z und sieht den ganzen Kopf.
  - Vorab gemessen (CPU-only, keine CUDA in `ct-viewer`): FP des Standard-Phantoms ≈ 10–20 s, Streuung+Rauschen ≈ 3 s. Ohne Puffer wäre jeder Klick eine Re-Projektion.
- **Umsetzung:**
  1. `create_dummy_geometry()` in `src/visualization/phantom.py`: Dummy-CBCT-Geometrie in Kopfgröße (s.o.).
  2. `create_dummy_measured_sinogram()`: FP des HU→1/mm-konvertierten Phantoms → idealer Linienintegral-Stack; Streuung als Gauß-geglättete Kopie der Primär-Transmittanz (SPR-Verhältnis, Sigma in mm am Detektor, pro Achse konvertiert), in der Intensitätsdomäne addiert (Streuung zählt Photonen dazu, gemessenes Linienintegral also niedriger — Kontrastverlust/Cupping-Richtung); Poisson-Zählrauschen mit `i0` einfallenden Photonen pro Ray, Photonenmangel floort bei einem Zählwert. Ergebnis als `SinogramData` (format `"synthetic"`, kanonisch, ohne Datei — der T-90-Setter-Zweig transponiert in-memory).
  3. **Ideal-FP auf Disk gepuffert** (`data/cache/dummy_fp_standard.npz`, gitignored; Fingerprint aus Geometrie + Energie + Cache-Version): erste Generierung ~13–23 s, jeder weitere Klick/App-Start ~3,5 s. Nur die Standard-Phantom-Strecke wird gepuffert; Streuung/Rauschen bleiben live, sodass `spr`/`i0`/`seed` nie re-projizieren. Keine committeden Binärdateien (CI-Data-Guard, Hard Rule).
  4. Phantom auf die Rotationsachse zentriert (Origin ≈ (−95.6, −95.6, −94.5) mm): der parallelproj-Kreis rotiert um den Weltsprungpunkt, der Demo-Default-Origin (0,0,0) parkt den Kopf im +x/+y/+z-Oktanten — außerhalb des FOV und halb außerhalb des Kegels (vorab so gemessen, siehe Preview). Der geteilte Demo-Default bleibt unverändert (separater Quirk, eigener Task-Kandidat).
  5. UI: Button „🎲 Generate dummy measurement" im Measurements-Expander; setzt Volumen + Geometrie (`geometry_is_default=False`, `geometry_loaded_original`) + Messung in den Session-State und presetet die FP-Auswahl auf „all" — ein Klick auf „Run Forward Projection" reproduziert die Messform exakt, Difference und Metriken leben sofort. Empty-State-Hint im Inspection-Tab verweist auf den Button.
- **Dateien:** `src/visualization/phantom.py`, `src/visualization/projection_panel.py`, `src/backend/loaders/sinogram.py` (Kommentar: `"synthetic"`-Format), `tests/test_dummy_measurement.py` (neu, 16 Tests), `tests/integration/test_ui_smoke.py` (3 Tests, Generator per Stub), `docs/superpowers/specs/2026-11-12-dummy-measured-sinogram-design.md` (neu)
- **Abhängig von:** T-67, T-69, T-90
- **Akzeptanz:** Der Generator liefert `(ppr, Zeilen, Spalten)` float32, endliche Werte, mit Seed reproduzierbar; `spr=0` ist reines Poisson-Rauschen um das ideale FP (Mittelwert ≈ 0), `spr>0` senkt die gemessenen Linienintegrale systematisch; Photonenmangel floort bei `ln(i0)`; Achsenwechsel transponiert in-memory reversibel; Cache-Roundtrip bit-identisch, invalidiert bei Geometrie-/Energie-Änderung, Custom-Volumes schreiben nie; UI-Button setzt das kohärente Trio und presetet die FP-Auswahl. Volle Suite grün, 0 Skips.
- **Status:** ✅ Done (Nov 12, 2026) — 19 neue Tests (16 Unit + 3 UI-Stub). Nachgemessen in `ct-viewer` (CPU-only): erste Generierung 12,6 s (unkorrekter Origin) bzw. 19,5 s (zentriert, ganzer Kopf im Kegel), Cache-Treffer 3,2 s, Cache 4,0 MB komprimiert; Preview bestätigt zentrierten, rotierenden Kopf mit Schädelrand, Streu-Belag und Rauschkorn. Lint: flake8 0, black/isort sauber.

### `[x]` T-98 — Messungs-Laden lädt die ganze Datei („All" statt Downsample-Default)
- **Ziel:** „Load Measurements" nutzte die geteilte Sample-Options-Auswahl mit FP-freundlichen Downsample-Defaults (proj 100, row 4, col 8) — eine Datei mit 2304 Projektionen wurde still auf (24, 16, 64) subsampelt (Nutzermeldung: „default measurement loading in sidebar: All statt 2304"). Jetzt lädt der Loader immer die ganze Datei; die Sample options im Tab steuern nur noch die Forward-Projektion.
- **Dateien:** `src/visualization/projection_panel.py` (Loader-Selection = voll; `read_shared_selection`/`default_sample_selection` entfernt; Sample-Options-Caption und Shapes-differ-Hinweis angepasst), `tests/integration/test_ui_smoke.py` (redundante `_select_all_samples`/`_restore_sample_defaults`-Aufrufe entfernt; App-Fixture seedet jetzt auch die Dataclass-Default-Geometrie)
- **Abhängig von:** T-93, T-96 (Sample-Options-Refactor)
- **Umsetzung:**
  1. Der Loader baut `build_selection_config()` (alle Achsen „all") statt `read_shared_selection()` — die Form-Readout zeigt die wahre Shape, und der T-90-Achsenwechsel kann in-memory ableiten. Zum Shape-Vergleich preset man die FP auf „all" (📐 Full projection geometry) — der Shapes-differ-Hinweis sagt es jetzt.
  2. Die dadurch toten Helper `read_shared_selection`/`default_sample_selection` entfernt; die `_select_all_samples`/`_restore_sample_defaults`-Test-Helfer entfallen (der Loader lädt immer voll) — damit verschwindet auch der module-scoped „all"-Leak, der `fp_run`-Klicks auf die volle Default-Geometrie (2304 × 64 × 512 ≈ 75 M Rays) und einen 90-s-AppTest-Timeout auslöste.
  3. Test-Determinismus: die App-Fixture seedet jetzt neben dem Volumen auch `projection_geometry` (Dataclass-Defaults) — ohne Seed stellte die App die machine-abhängige `data/.last_geometry.json` wieder her (zuletzt die Dummy-Geometrie mit 360 Views aus einer Form-Bearbeitung), und die erwartete FP-Shape war rechnerabhängig.
- **Akzeptanz:** „Load Measurements" lädt die ganze Datei (Load-Tests ohne Sample-Vorwahl grün, exakte Daten); `fp_run` mit Downsample-Defaults liefert (24, 16, 64) unabhängig vom Maschinen-Cache; Sample-Options-Caption nennt nur noch die FP. Volle Suite grün, 0 Skips.
- **Status:** ✅ Done (Nov 12, 2026) — `test_sinogram_inspection_run_button_produces_simulation` läuft jetzt deterministisch in ~3 s (vorher 90-s-Timeout bzw. maschinenabhängige Shape).

### `[x]` T-102 — Geometry wird bei allen Messungsformaten mitgeführt; Default-Geometrie = Dummy-Phantom-Geometrie
- **Ziel:** `load_sinogram` reichte `geometry` nur an den DICOM-Pfad durch — ein `.npy`/NIfTI-Messungs-Laden verlor die Geometrie still (`SinogramData.geometry = None`), obwohl die App die aktive Geometrie übergibt. Dadurch bekamen die Sinogram-Ansichten kein Detektor-Spacing und die Geometrie-Readouts waren inkohärent. Jetzt: alle drei Formate führen die Geometrie mit. Und: ohne Geometry-File ist die Default-Geometrie jetzt die **Dummy-Phantom-Geometrie** (`create_dummy_geometry()`, 60 Views, 512 × 1 mm Spalten, 192 × 2 mm Zeilen, SDD 1000 / SID 500, cone beam) statt der nackten Dataclass-Defaults — der Leerzustand und das Demo bleiben kohärent (gleicher Detektor, gleicher Scan).
- **Dateien:** `src/backend/loaders/sinogram.py` (`_load_numpy`/`_load_nifti` mit `geometry`-Parameter, Forward an `_finish_sinogram`; `load_sinogram` reicht durch), `src/visualization/geometry_cache.py` (`default_geometry` → Cached oder `create_dummy_geometry()`), `tests/unit/test_sinogram_loader.py` (+1 Test: numpy-Laden mit Geometrie führt sie mit), `tests/unit/test_geometry_cache.py` (Fallback-Test auf die Dummy-Geometrie)
- **Abhängig von:** T-98
- **Umsetzung:** `_load_numpy`/`_load_nifti` nehmen `geometry` entgegen und geben es an `_finish_sinogram` weiter; `load_sinogram` reicht es an alle drei Pfade durch. `default_geometry()` fällt auf `create_dummy_geometry()` zurück (lazy Import, kein Zirkel). Eine Variante, `projections_per_rotation` aus der Projektionszahl der geladenen Datei abzuleiten, wurde verworfen: für Teil-Dateien (z. B. den 1-Projektions-Fall) wäre sie falsch, und sie leckte über die module-scoped UI-App-Fixture in Folgetests. Nachtrag: das Measurements-Expander bekommt die Sampling-Options als Opt-in zurück (T-98 lud immer die ganze Datei) — eine Checkbox „Sample instead of the whole file" (default aus) blendet die Per-Achsen-Auswahl ein (`render_selection_controls`, Prefix `load`, Proj-Default Downsample 10), ein gesampelter Load liest nur den gewählten Bereich (lazy für .npy/NIfTI), nie stillschweigend.
- **Akzeptanz:** `.npy`-Laden mit `geometry=ProjectionGeometry()` → `sinogram.geometry is geometry` und `projections_per_rotation == 2304`; `default_geometry()` ohne Cache → `create_dummy_geometry()`; bestehende Loader-Tests (ohne Geometrie → `None`) unverändert grün; UI-Smoke-Suite grün (Checkbox aus per Default, Per-Achsen-Auswahl erscheint beim Anschalten); Lint sauber.
- **Status:** ✅ Done (Nov 12, 2026) — Suite 341 passed, 0 skipped (die Korrelations-Metrik wurde separat entfernt).

## Phase 10 — Vergleich simuliert vs. gemessen

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

## Phase 11 — App & Viewer (Integration, Layout, 3D)

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

### `[ ]` T-87 — Vollbild je Ansicht (Fullscreen) (verschoben)
- **Ziel:** Sicherstellen, dass jede der vier Ansichten (3× MPR, 1× 3D) auf Knopfdruck den verfügbaren Platz einnimmt — ohne eigenen Code, wo Streamlit das schon kann.
- **Status:** ⚠️ Shelved (Nov 10, 2026) — auf Wunsch zurückgestellt. Die Mechanismen existieren und sind vermessen (siehe unten), aber keiner der offenen Punkte wird jetzt umgesetzt. **Kein Code geändert:** die nativen Buttons bleiben so, wie Streamlit sie liefert.
- **Vermessung (Grundlage für die Wiederaufnahme, `All`-Ansicht, Viewport 1112×670):**
  - **Quelle ist Streamlit, nicht Plotly.** `plotly.min.js` (3.8.2) hat keinen Modebar-Button mit „fullscreen" im Namen. Streamlit injiziert ihn in `streamlit/static/js/8237.210a5ac4.chunk.js` per `config.modeBarButtonsToAdd = [{name: "Fullscreen", icon: fullscreen-expand, click: …}]`. Die Bilder bekommen denselben Mechanismus über `stFullScreenFrame` in `streamlit/static/js/5711.229cb7d0.chunk.js` (`state.expanded`, `fullWidth = window.innerWidth - 2*padding`).
  - **3D-Button:** Modebar oben rechts im Chart, `x=800…1024`, `y=364…390`; „Fullscreen" ist der achte und letzte Button (nach `Download plot as a png`, `Zoom`, `Pan`, `Orbital rotation`, `Turntable rotation`, `Reset camera to default`, `Reset camera to last save`). Button 24×25 px bei `x=1000, y=364`. Sichtbar beim Hover über den Chart.
  - **MPR-Buttons:** einer pro Slice, `position: absolute`, **`top: -6px`, `right: -48px`, 40×40 px**, relativ zum `stElementContainer` des Bildes. Standardmäßig `opacity: 0`, `transform: scale(0)`; `.st-emotion-cache-9aoz2h:hover .e1vs0wn31 { opacity: 1; transform: scale(1) }` blendet ihn ein. Also nur beim Hover sichtbar, nicht „weg".
- **Offene Punkte bei Wiederaufnahme:**
  1. **3D-Vollbild funktioniert** — geprüft: `399×700` → **`1088×612`** (Viewport 1112×670), `_fullLayout.height` 700 → 612. `height=VIEWER_HEIGHT_PX` stört nicht, Plotly re-measured sich selbst.
  2. **Bild-Vollbild skaliert das Bild nicht hoch** — der Frame bekommt korrekt `{width: 1112, height: 670}` (`190×190` → `1112×670`, `position: fixed`), aber `st.image` schreibt seine Breite beim Rendern als festen Inline-Style (`style="width: 189.86px"`) und liest die neue Größe nicht. Das `<img>` bleibt bei **256×256**. Abhilfe: Bild vorher hochskalieren oder `st.dialog(width="large")` mit eigenem Renderpfad.
  3. **Hover-Button ragt in die 3D-Spalte** — `right: -48px` lässt ihn 48 px über den Bildrand hinausstehen: MPR-Spalte endet `x=606`, Button bis `x=654`, 3D-Spalte ab `x=627` → **27 px Überlappung** je Ebene, mit `z-index: 101` gewinnt der Button Klicks in diesem Streifen. Optionen: `overflow: hidden` am MPR-Container (schneidet den Button an), Überlappung akzeptieren (nur beim Hover sichtbar), oder eigener Button je Spalte.
  4. **Zwei Bedienmuster bei einer Mechanik** — Bild-Vollbild ist ein Hover-Button am Bildrand, 3D-Vollbild liegt im Chart-Menü. Ein einheitlicher „⛶"-Button je Spalte wäre konsistenter.
  5. **MPR-Vollbild skaliert nur den Container**, nicht die Slice-Slider. Ein Vollbild-Slice-Viewer mit Slidern wäre `st.dialog(width="large")`.
  6. **Test-Hinweis:** Bild-Vollbild setzt `position: fixed` + z-index 1000050; nach dem Umschalten muss die Seite neu geladen werden, sonst bleiben die `stFullScreenFrame`-Wrapper bei 0×0 hängen (beim Vermessen beobachtet). Relevant für automatisierte Tests.
- **Dateien (bei Wiederaufnahme):** `src/visualization/app.py` (`render_viewer_tab`), `tests/integration/test_ui_smoke.py`
- **Abhängig von:** T-86

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

### `[x]` T-94 — 3D-Ansicht: echtes Weltkoordinatensystem (Origin + Spacing der FP)
- **Ziel:** Der 3D-Plot muss das Volumen im selben Weltkoordinatensystem zeichnen, in dem die Forward-Projektion rechnet — echter DICOM-Origin, echtes Spacing — sodass Geometrie-Overlay (Source-Pfad, Detektor-Ebene, Zentralstrahlen) und gerendertes Phantom mit den simulierten Projektionen übereinstimmen. Gemeldeter Fehler: der 3D-Plot zeigte den Zentralstrahl durch die Phantommitte, während die simulierte FP das Phantom oben am Detektor zeigte.
- **Hintergrund:**
  - `create_volume_figure()` positionierte das Volumen-Mesh schematisch zentriert auf den Weltsprungpunkt und ignorierte `Volume.origin` komplett; die FP platziert Voxel `[0, 0, 0]` (in `(x, y, z)`-Ordnung) am echten Origin. Mit dem Demo-Default-Origin (0,0,0) parkt der Kopf im `+x/+y/+z`-Oktanten: die FP sieht das Phantom oberhalb der Rotationsachse (Phantom oben am Detektor), der 3D-Plot tat so, als sei es zentriert — daher die Inkonsistenz.
  - Zweitdiscrepanz: `get_detector_position()` zeichnete die Detektor-Ebene bei `-sdd` vom Isocenter, der Projektor platziert sie bei `-(sdd - sid)` (SDD ist ab Source gemessen, nicht ab Rotationsachse — siehe `backend.parallelproj.geometry`). Die gezeichnete Ebene lag `sid` mm zu weit außen, die Zentralstrahlen waren länger als die echten Rays (`sdd`).
- **Umsetzung:**
  1. `create_volume_figure(..., origin=None)`: `origin` = Weltposition `(x, y, z)` des ersten Voxels (DICOM-Origin, gleiche Konvention wie `Volume.origin`). Mesh (Iso-Modus) und Voxel-Wolke (Volume-Modus) werden am echten ersten-Voxel-Ort gezeichnet; die Kamera-Bounds umrahmen das zellzentrierte Gitter (Ausdehnung `n * spacing`). `None` behält die alte schematische Zentrierung (Rückwärtskompatibilität).
  2. Downsample-Korrektheit: Mean-Pooling von `factor` Voxeln verschiebt die erste gezeichnete Voxelmitte um `0.5 * (factor - 1)` Source-Voxel in den Origin hinein; die Zeichenpfade (Iso: Gesamtfaktor `downsample`; Volume: `downsample * ds`) wenden den Shift an, sodass die Fläche exakt auf den Weltpositionen liegt, die der Projektor durchtraced. Der Legacy-Pfad (`origin=None`) bleibt unverändert.
  3. `get_volume_center(..., origin=None)`: mit Origin die echte Gittermitte (`origin + halbe Ausdehnung`), ohne `(0, 0, 0)`.
  4. `get_detector_position()`: Detektor-Ebene bei `did = sdd - sid` vom Isocenter — gleiche Konvention wie `backend.parallelproj.geometry`; Zentralstrahlen jetzt mit echter Länge `sdd`.
  5. `app.py` reicht `volume.origin` an `create_volume_figure()` und `get_volume_center()` durch; Volumen ohne `origin`-Attribut fallen auf die Legacy-Zentrierung zurück.
- **Dateien:** `src/visualization/volume3d.py`, `src/visualization/app.py`, `tests/unit/test_volume3d.py` (neu, 5 Tests), `tests/unit/test_geometry_trajectory.py`, `docs/geometry.md`, `docs/superpowers/specs/2026-11-12-3d-view-real-world-origin-design.md` (neu)
- **Abhängig von:** T-55, T-93 (gemeldeter Fehler)
- **Akzeptanz:** Iso-Mesh und Voxel-Wolke liegen bei `origin + index * spacing` (exakt getestet, auch nach Downsampling auf den gemergten Voxelzentren); Legacy-`origin=None`-Platzierung unverändert; Detektor-Ebene bei `sdd - sid` vom Isocenter. Demo-Volumen (Origin (0,0,0)): 3D-Ansicht zeigt den Kopf im `+`-Oktanten — genau wie die simulierte FP (Phantom oben am Detektor); Dummy-Messung (zentriert): 3D-Ansicht zentriert — passend zu ihrer FP. Volle Suite grün, 0 Skips.
- **Bekannte Grenze (Update Nov 13, 2026):** Der Helix-Vorschub ist inzwischen implementiert (`b7b7279` — z-feed pro Projektion, `z_step = pitch * n_rows * row_spacing / ppr`); der Projektor wendet `pitch` als Tabellenvorschub an. Verifikations-Tests und Doku-Sync: ✅ T-104 (Nov 17, 2026).
- **Status:** ✅ Done (Nov 12, 2026) — 5 neue Tests in `test_volume3d.py` (exakte Mesh-/Marker-Positionen, Legacy-Pfad, Downsampling), `test_get_detector_position` auf die `sdd - sid`-Konvention umgestellt. Bekannt: die FP zeigt für das Demo-Volumen den Phantomkopf oben am Detektor — das ist jetzt **gewollt sichtbar** (die Ansicht zeigt, was gerechnet wird); ob das Demo-Phantom auf die Rotationsachse zentriert wird, ist eine eigene Entscheidung → T-95.

### `[x]` T-95 — Demo-Phantom-Origin auf die Rotationsachse zentriert
- **Ziel:** `create_shepp_logan_hu()` erzeugte das Demo-Phantom mit Origin (0,0,0) — der Kopf parkte im `+x/+y/+z`-Oktanten, außerhalb des in-plane-FOV und halb außerhalb des Kegels (der Quirk, den T-93 nur für die Dummy-Kopie umgangen hatte). Jetzt zentriert: der erste Voxel sitzt bei minus halber Voxelzentren-Ausdehnung pro Achse (DICOM-Ordnung x, y, z), die Gittermitte auf der Rotationsachse.
- **Dateien:** `src/visualization/phantom.py`, `tests/test_phantom.py`
- **Abhängig von:** T-94
- **Umsetzung:** Origin in `create_shepp_logan_hu()` berechnet statt (0,0,0); der dadurch redundante `_centered_shepp_logan_hu`-Wrapper im Dummy-Generator entfernt — der Dummy nutzt jetzt direkt die geteilte Default-Volumen-Funktion. Der Ideal-FP-Disk-Cache bleibt gültig: die Weltposition des zentrierten Volumens ist identisch zur bisherigen Dummy-Kopie (gleicher Array, gleiches Spacing, gleicher Origin).
- **Akzeptanz:** Regressionstest pinnt die Gittermitte ≈ (0,0,0) in allen Achsen; `test_hu_volume_metadata` pinnt den zentrierten Origin; FP und 3D-Ansicht stimmen überein (Phantom zentriert auf der Rotationsachse, Zentralstrahl durch die Kopfmitte).
- **Status:** ✅ Done (Nov 12, 2026) — 1 neuer Regressionstest, Metadata-Test aktualisiert; 65 Tests der betroffenen Module grün.

### `[x]` T-96 — Dummy-Messung wird automatisch mit dem Demo-Bild erzeugt
- **Ziel:** Das Laden des Demo-Bildes („Load Demo Phantom" im Empty State) erzeugt automatisch die kohärente Demo-Trio — Volumen + Dummy-Geometrie + synthetische Messung — ohne eigenen Button-Klick (Nutzerentscheidung: „generate automatically when demo image is loaded").
- **Dateien:** `src/visualization/sidebar.py` (`load_demo_volume`), `src/visualization/app.py` (Spinner-Text), `tests/unit/test_demo_load.py` (neu, 2 Tests)
- **Abhängig von:** T-93, T-95
- **Umsetzung:** `load_demo_volume()` ruft `create_dummy_measured_sinogram()` auf und setzt das Trio in den Session-State (Volumen, Dummy-Geometrie mit `geometry_is_default=False`, Sinogramm, Sample-Auswahl auf „all", `clear_geometry_edit_state`). Der manuelle „🎲 Generate dummy measurement"-Button bleibt als explizite Regeneration erhalten. Der Ideal-FP ist disk-gepuffert → ~3,5 s nach der ersten Generierung (~13–23 s frisch), der Spinner im Empty State nennt die Mess-Schritte.
- **Akzeptanz:** AppTest (Generator per Stub, Numerics in `test_dummy_measurement.py`): Klick auf „Load Demo Phantom" setzt das kohärente Trio (Sinogramm format `"synthetic"`, Dummy-Geometrie, „all"-Preset) und überschreibt zuvor geladene Daten.
- **Status:** ✅ Done (Nov 12, 2026) — 2 neue Tests in `tests/unit/test_demo_load.py` (eigenes Modul mit module-scoped `AppTest`, frische Session → Empty State).

### `[x]` T-97 — Sinogram-Ansichten im korrekten Detektor-Spacing
- **Ziel:** Die Projektions-Ansichten im Sinogram-Inspection-Tab (gemessen, simuliert, Differenz) zeigten das Roh-Array, ohne die Pixel-Anisotropie in mm zu berücksichtigen — ein 2 mm × 1 mm-Detektor zeigte das Phantom halb so hoch wie real. Jetzt resampelt die UI die Zeilenachse um row/col-Spacing vor der Anzeige — dieselbe Kanten-Konversion, die die MPR-Ebenen bekommen (`to_isotropic`).
- **Dateien:** `src/visualization/projection_panel.py` (`projection_display_spacing`, `_render_projection_image`, Differenz-Ansicht), `tests/unit/test_projection_panel.py` (2 Tests)
- **Abhängig von:** T-93
- **Umsetzung:** Neuer Helper `projection_display_spacing(geometry)` → `(det_row_spacing_mm, det_col_spacing_mm)` oder `None`; `_render_projection_image(..., spacing=)` und die Differenz-Ansicht wenden `to_isotropic` (lazy aus `visualization.app`) auf das normalisierte Bild an. Ohne Geometrie (unbekanntes Spacing) bleibt das Roh-Shape unverändert.
- **Akzeptanz:** Helper-Tests pinnen `(2.0, 1.0)` für die Dummy-Geometrie bzw. `None`; die Ansichten zeigen quadratische mm-Pixel; bestehende Inspection-Tests unverändert grün.
- **Status:** ✅ Done (Nov 12, 2026) — 2 neue Helper-Tests, `test_sinogram_inspection_*`-Suite grün.

### `[x]` T-99 — Geometrie-Laden im Geometry-Tab statt der Sidebar; Trajectory-Settings nur Visualisierung
- **Ziel:** Der Geometry-File-Upload (inkl. der Notes „Geometry loaded!"/„No geometry file loaded") lebte im Sidebar-Expander — die Notiz über die geladene Geometrie gehört neben die Readouts und das Editier-Formular im Geometry-Tab. Die Sidebar hält nur noch die Trajectory-Overlay-Settings („Projections", „Trajectory Downsample") — Visualisierung only, ohne Einfluss auf die Forward-Projektion (die die Sample options im Sinogram-Inspection-Tab nutzt).
- **Dateien:** `src/visualization/projection_panel.py` (`render_geometry_tab`: Uploader + Load-Logik + Notes), `src/visualization/sidebar.py` (`_render_geometry_section` ohne Upload; Caption „3D geometry overlay only"; tote Imports entfernt)
- **Abhängig von:** T-93, T-98
- **Umsetzung:** Uploader + Upload-Dedup (`last_loaded_geometry_key`) + Temp-File-Pfad ziehen in `render_geometry_tab`; nach erfolgreichem Laden `st.rerun()` (Readouts/Formular oben haben im selben Run die alte Geometrie gerendert). Die Sidebar-Section behält „Projections"/„Trajectory Downsample" mit dem Caption „3D geometry overlay only — does not affect the forward projection. Load a geometry file in the Geometry tab." — beide Widgets speisen ausschließlich `get_trajectory_positions`/`add_trajectory_to_figure` (3D-Overlay), nie die FP.
- **Akzeptanz:** UI-Smoke-Suite grün (Sidebar-Expander „Projection Geometry" bleibt, jetzt ohne Upload); Notes erscheinen im Geometry-Tab; Trajectory-Settings wirken nur auf das 3D-Overlay.
- **Status:** ✅ Done (Nov 12, 2026) — `test_ui_smoke.py` + `test_demo_load.py` grün, flake8/black/isort sauber.

### `[x]` T-100 — Difference-Bild auf gleicher Starthöhe wie die Nachbarspalten
- **Ziel:** Das Difference-Bild im Sinogram-Inspection-Tab startete eine Caption-Zeile höher als die Measured/Simulated-Bilder: die Nachbarspalten haben `st.caption` über dem Bild, die Difference-Spalte übergab ihr Label als `st.image`-Caption (unter dem Bild) — das Bild begann also am Spaltenanfang. Jetzt gleiche Struktur in allen drei Spalten: Caption-Zeile oben, dann das Bild.
- **Dateien:** `src/visualization/projection_panel.py` (Difference-Zweig)
- **Abhängig von:** T-97
- **Umsetzung:** `st.caption("Difference (measured − simulated)")` über dem Bild, `st.image` ohne `caption=`-Parameter — die drei Spalten sind strukturell identisch und die Bildoberkanten liegen auf einer Höhe.
- **Akzeptanz:** Difference-Bild startet auf derselben vertikalen Höhe wie Measured/Simulated; UI-Smoke-Suite grün.
- **Status:** ✅ Done (Nov 12, 2026) — `test_ui_smoke.py` + `test_projection_panel.py` grün, Lint sauber.

### `[x]` T-101 — Shepp-Logan-Phantom um 90° gedreht: erste (anterior) Projektion zeigt das klassische aufrechte Oval
- **Ziel:** Das 3D-Phantom legte die klassische Shepp-Logan-Scheibe in die Axialebene (klassisch-horizontal → x, klassisch-vertikal → y). Die erste Projektion (Quelle bei 0° = anterior, +X; Detektor-Spalten entlang y, Zeilen entlang z) zeigte das Phantom therefore um 90° gedreht (Tumoren links, „Top-Ellipse" rechts). Jetzt: die klassische Scheibe liegt in der Koronalebene — klassisch-horizontal → y (patient left-right), klassisch-vertikal → z, Tiefenachse → x (anterior-posterior). Die erste Projektion zeigt das aufrechte Oval (Schädel 138 mm breit × 184 mm hoch), die Kopfabmessungen sind anatomisch plausibel (A-P 180 mm > L-R 138 mm, S-I 184 mm).
- **Dateien:** `src/visualization/phantom.py` (`ELLIPSOIDS_3D` zyklisch permutiert: (x0, y0, z0) → (z0, x0, y0), a/b/c folgen; `create_shepp_logan_3d` baut die klassische Ebene aus Zeilen (y) und Slices (z), Tiefenachse = Spalten (x); `DUMMY_CACHE_VERSION` 2 → 3, 2D-Docstring), `src/visualization/volume3d.py` (`get_camera_preset` + PyVista-`camera_views`: front = +X anterior, back = −X, left = +Y, right = −Y), `src/visualization/mpr.py` (Ebenen-Kommentare auf die Patient-Konvention umgestellt), `docs/geometry.md` (Coordinate-System-Section: X = anterior/posterior, Y = lateral — war inkonsistent mit dem Winkel-Diagramm und dem Code), `tests/test_phantom.py` (Head-Dimensions-Test auf die neue Achsenzuordnung)
- **Abhängig von:** T-93, T-95
- **Umsetzung:**
  1. `ELLIPSOIDS_3D`: zyklische Permutation der Positionen (x0, y0, z0) → (z0, x0, y0) mit a entlang y, b entlang z, c entlang x; theta rotiert jetzt in der klassischen (y, z)-Ebene, die ±18°-Kammer-Tilts bleiben erhalten. Kommentare auf y-Vorzeichen-Labels umgestellt (+y = patient left).
  2. `create_shepp_logan_3d`: das (V, U)-Gitter läuft über Slices (z) × Zeilen (y), die Ellipsen-Formel rotiert in dieser Ebene, die Füllschleife läuft über die Spalten (x). Shape-(num_slices, size, size)- und Spacing-Verträge unverändert.
  3. `DUMMY_CACHE_VERSION` gebumpt — der Ideal-FP-Cache enthält die Phantom-Orientierung nicht im Fingerprint und würde sonst eine veraltete (ungedrehte) Projektion wiederverwenden.
  4. Kamera-Presets: „front" blickt jetzt von +X (anterior, wie die FP bei 0°), „left" von +Y — vorher folgten die Namen der veralteten X=lateral-Konvention und waren zur FP-Richtung falsch.
- **Akzeptanz:** Erste (anterior-)Projektion zeigt das aufrechte Oval (vorher: nahezu runder Blob mit seitlichen Tumoren — vorher/nachher als PNG verifiziert); Head-Dimensionen x≈180/y≈138/z≈184 mm; volle Suite 340 passed, 0 skipped; flake8/black/isort sauber.
- **Status:** ✅ Done (Nov 12, 2026) — `DUMMY_FP_CACHE` wird durch den Versions-Bump automatisch invalidiert; erster Demo-Lauf rechnet die FP neu.

### `[x]` T-103 — Restore last session button in empty state (Reload überleben)
- **Ziel:** Nach einem Browser-Reload (neue Streamlit-Session) sind Volume, Geometrie und Demo-State aus der `session_state` weg, obwohl die Caches (`data/.last_loaded.json`, In-Memory `_volume_cache`, disk-cached Ideal-FP) überleben. Die Empty State bekommt jetzt einen „↺ Restore last session"-Button, der den letzten Stand wiederherstellt: DICOM-Volumen aus dem In-Memory-Cache (Reload = gleicher Server-Prozess → Cache-Hit), Demo-Trio neu aus dem disk-cached Forward-Projection.
- **Dateien:** `src/visualization/volume_cache.py` (Record `{kind, files}`; `save_last_demo`, `load_last_session`; `load_last_loaded`-Kompatibilität), `src/visualization/sidebar.py` (`load_demo_volume` persistiert die Demo, `restore_last_session`), `src/visualization/app.py` (Restore-Button in `render_empty_state`)
- **Abhängig von:** T-85, T-96
- **Status:** ✅ Done (Nov 12, 2026) — Restore-Button erscheint nur, wenn ein gültiger Session-Record existiert; Clear Cache entfernt ihn (Cache-Datei gelöscht).

### `[x]` T-109 — Aktions-Queue: neue Klicks stoppen keine laufenden Aktionen
- **Ziel:** Die vier langlaufenden UI-Aktionen (Load Series, Load Measurements, Dummy measurement, Run Forward Projection) werden pro Session in einer FIFO-Queue ausgeführt. Ein weiterer Klick stellt keine laufende Aktion ein und verwirft kein fertiges Ergebnis. Die Queue ist über das Sidebar-Kontrollkästchen „Show queue" erreichbar (standardmäßig aus, ohne zusätzlichen Expander), zeigt wartende Einträge und erlaubt das Abbrechen einzelner wartender Einträge.
- **Dateien:** `src/visualization/action_queue.py` (Streamlit-freier Registry mit einem Daemon-Worker pro Session), `src/visualization/actions.py` (Eingaben einfrieren, Ergebnis auf dem Hauptthread anwenden, Queue-Panel und Poller), `src/visualization/sidebar.py`, `src/visualization/projection_panel.py`, `src/visualization/app.py`, `tests/unit/test_action_queue.py`, `tests/unit/test_actions.py`, `tests/integration/test_ui_smoke.py`, `docs/actions.md`
- **Abhängig von:** T-85, T-108
- **Umsetzung:** Jeder Button-Klick friert seine Eingaben in einem `run()`-Closure ein und hängt den Eintrag an die Session-Queue. Ein Worker pro Session arbeitet strikt FIFO, ein Eintrag nach dem anderen; `drain_action_results` wendet fertige Einträge am Anfang von `main()` an, bevor Widgets erzeugt werden. Ein unsichtbarer 1-s-Poller erzwingt bei Statuswechsel einen App-Rerun — auch wenn „Show queue" aus ist. Abbrechen ist nur für wartende Einträge möglich (ein laufender C-Aufruf kann nicht gestoppt werden). Ein 10-min-Timeout markiert hängende Einträge als fehlgeschlagen. `actions_inline` ist ein reiner Test-Seam für AppTest.
- **Akzeptanz:** Keine Aktion blockiert den Script-Thread; Einträge laufen in Klickreihenfolge; fertige Ergebnisse gehen nicht durch einen Rerun verloren; das Panel listet Status, Laufzeit, Fortschritt und Fehler und bietet „✕ Cancel" nur für wartende Einträge; Suite grün ohne Skips, Lint sauber.
- **Status:** ✅ Done (Nov 19, 2026) — 14 Queue-, 12 Action-Unit-Tests; Queue-Panel, `Show queue` und Cancel eines wartenden Eintrags im UI-Smoke abgedeckt. Test-Bar 359 → 387 passed, 0 skipped; flake8/black/isort sauber. Im Browser (Port 8502) verifiziert: Panel in der Sidebar, Live-Fortschritt (`60/60`), Ergebnis auch bei ausgeblendetem Panel, Klick-Reaktivität während des Laufs, Cancel eines wartenden Eintrags, Tab-Wechsel ohne Fehler, neuer Tab ohne Queue. `AppTest` feuert `run_every` nicht. Offen durch die Umgebung: echte DICOM-/Projektionsdateien und ein CUDA-Gerät (hier `CUDA present: False`; `use_cuda=True/False` liefern identische Summen, der Worker-Lauf mit CUDA-Option endet normal). Details in `docs/actions.md` und im Plan.

### `[x]` T-110 — Scan-Projektionszahl in den Geometry-Tab, Overlay-Anzeige in die 3D Options
- **Ziel:** Die beiden Trajectory-Overlay-Widgets aus dem Sidebar-Expander „Projection Geometry" stehen an ihrem thematischen Ort: die Projektionszahl des Scans im Geometry-Tab bei den Readouts, die Sichtbarkeit („Show projections") und „Trajectory Downsample" (reine 3D-Darstellung) im 3D-Options-Popover des Viewer-Tabs. Die In-Canvas-„Projection Geometry"-On/Off-Buttons entfallen: ein einziger Schalter statt zweier Bedienorte. Die Zahl ist die **Scan-Länge** (nicht eine Umdrehung): sie steuert sowohl die 3D-Trajektorie als auch die Projektionsachse der Forward Projection; `projections_per_rotation` sagt nur, wie viele Views eine Umdrehung hat.
- **Dateien:** `src/visualization/projection_panel.py` (`render_geometry_tab`: Projektionszahl; `scan_n_projections`-Helper; FP-Achse und `n_projections_total`; `clear_geometry_edit_state` verwirft sie mit), `src/visualization/sidebar.py` (`_render_geometry_section` entfernt, Default-Geometrie bleibt via `_ensure_geometry`), `src/visualization/app.py` (Viewer-Popover, `show_projections`-Gate, Zahl via Helper), `src/visualization/volume3d.py` (`add_geometry_toggle` entfernt), `tests/unit/test_geometry_toggle.py` (gelöscht), `tests/integration/test_ui_smoke.py`
- **Abhängig von:** T-99
- **Umsetzung:** `scan_n_projections(geometry)` liest `st.session_state["scan_n_projections"]` (Fallback `projections_per_rotation`, bis der Geometry-Tab einmal gerendert hat — Streamlit wendet Widget-Werte vor dem Script-Lauf an). Der Viewer zieht die Trajektorie daraus, die FP löst ihre Projektionsauswahl gegen `(n_scan, rows, cols)` auf und übergibt `n_projections_total=n_scan`, damit eine Helix über den ganzen Scan zentriert bleibt. Laden oder Generieren einer Geometrie verwirft den Key, damit die neue Geometrie ihren Wert vorgibt. Die Sidebar hält nur noch den Default-Geometrie-Fallback.
- **Akzeptanz:** Sidebar zeigt nur noch Image/Measurements; der Geometry-Tab hat genau ein „Projections"-Feld (Startwert = `projections_per_rotation`); „all" in den Sample options projiziert `n_scan` Projektionen (nicht `projections_per_rotation`); die 3D Options bieten „Show projections" (an) und „Trajectory Downsample" (1/100); der Plotly-Spec trägt keine `updatemenus` mehr; Suite grün ohne Skips, Lint sauber.
- **Status:** ✅ Done (Nov 19, 2026) — Toggle-Modul gelöscht, UI-Smoke angepasst; Test-Bar 359 passed / 0 skipped. Im Browser (Port 8502) verifiziert: „Projections" = 12 ⇒ 3D-Trajektorie mit 12 Punkten **und** FP-Lauf meldet `Forward projecting 0/12` / `Simulated: (12, 192, 512) · 12 projections` (mit `projections_per_rotation` = 60 wären es 60 gewesen).

### `[x]` T-11-01 — Zeilen-Sinogramm als zweite Ansichtsreihe
- **Ziel:** Der Sinogram-Inspection-Tab zeigt unter dem Projektions-Slider eine zweite Ansichtsreihe im Schema `row → col → projection`: für eine gewählte Detektorzeile Spalten gegen Projektionswinkel, als gemessen / simuliert / Differenz nebeneinander, mit eigenem Zeilen-Slider.
- **Hintergrund:** Die erste Reihe zeigte nur die Projektionsansicht (`row × col` bei festem Projektionsindex). Damit ist der Blick auf den Sinogramm-Charakter der Daten — wie sich eine Detektorzeile über die Projektionen entwickelt — nicht möglich.
- **Dateien:** `src/visualization/projection_panel.py` (`row_sinogram`-Helper, zweite Reihe in `render_comparison_tab`, gemeinsames Level/Window, `render_forward_projection_tab`), `src/visualization/app.py` (neuer Tab), `src/visualization/sidebar.py` (Hinweis), `tests/unit/test_projection_panel.py`, `tests/integration/test_ui_smoke.py`, `AGENTS.md`
- **Abhängig von:** T-68, T-97
- **Umsetzung:**
  1. `row_sinogram(array, row_index)` schneidet aus dem kanonischen Stapel `(proj, row, col)` eine Zeile und transponiert sie nach `(col, proj)` — senkrecht Detektorspalten, waagerecht Projektionswinkel.
  2. Die neue Reihe sitzt direkt unter dem Projektions-Slider und spiegelt die erste: drei Panels mit Caption und Platzhaltern; `sino_row_index` wird wie der Projektionsindex über `resolve_view_index` geklemmt und bekommt einen eigenen Slider unter der Reihe. Fehlende simulated-Daten lassen den Index auf die jeweils vorhandene Zeilenzahl klemmen.
  3. Kein Detektor-Spacing-Resampling für die Sinogramm-Bilder: die waagerechte Achse ist ein Winkelindex, keine Detektorspalte. Die Differenz erscheint nur bei übereinstimmenden Shapes (gleiche Regel wie in der ersten Reihe).
  4. Beide Reihen nutzen denselben Viewer: die Höhe der Boxen ist auf die größte Seite eines Projektionsframes gedeckelt (`comparison_view_height`, 360–720 px), das Bild scrollt in der Box, `Ctrl` + Mausrad zoomt (0,1×–8×) um den Cursor, Doppelklick setzt zurück. Die Box-Höhe gilt für beide Reihen, damit sie bündig stehen; die Projektion ist vertikal zentriert, solange sie in die Box passt. Der iframe-Viewer (`build_zoomable_image_html`) bekommt ein dunkles Scrollbar-Theme (`color-scheme: dark`), weil er das App-Theme nicht erbt. PNG als Data-URI (lange Seite ≤ 2048 px), damit der Payload auch bei voller Projektionszahl klein bleibt.
- **Akzeptanz:** Eine geladene Messung zeigt „Measured sinogram, row n/N" und einen „Row index"-Slider; mit passender Simulation füllen sich simuliertes Sinogramm und Differenz; leere Slots reservieren dieselbe Höhe wie in der ersten Reihe; keine Exception ohne Volumen, ohne Messung oder bei Shape-Unterschied. Beide Reihen sind gleich hoch gedeckelt, scrollen intern und zoomen per `Ctrl` + Mausrad. Suite grün, 0 Skips, Lint sauber.
- **Status:** ✅ Done (Nov 19, 2026) — 2 Helper-Tests (Achsen/Zeile) und 2 UI-Smoke-Tests (Reihe mit Slider, Differenz); Platzhalter-Test auf 6 leere Slots aktualisiert. Suite 394 passed, 0 skipped (mit Git Bash auf `PATH`), flake8/black/isort sauber. Im Browser (Port 8502) verifiziert: Dummy-Messung und FP füllen beide Reihen; „Projection index" steht über, „Row index" unter der Sinogramm-Reihe; Leer- und Differenz-Platzhalter erscheinen wie erwartet, keine Console-Fehler. **Nachtrag (Nov 19, 2026):** Die zweite Reihe war bei Spaltenbreite ~2500 px hoch und machte die Seite unbrauchbar lang. Behoben mit dem gedeckelten, scroll- und zoombaren Viewer für **beide** Reihen (7 neue Tests: Höhen-Deckel, PNG-Data-URI inkl. Downscale, Viewer-HTML inkl. dunkler Scrollbar); Test-Bar 398 → 405. Im Browser (Port 8506) verifiziert: beide iframes 300 × 512 px, Projektion vertikal zentriert (144 px oben/unten), Sinogramm scrollt (scrollHeight 2471), `Ctrl` + Mausrad zoomt in beiden Reihen (115 % → 345 px breit), Doppelklick setzt auf 100 % zurück, `color-scheme: dark` aktiv, keine Console-Fehler. **Nachtrag 2 (Nov 19, 2026):** Alle Views und Slices nutzen jetzt ein gemeinsames Level/Window (`stack_window` über gemessenen + simulierten Stapel, `window_image` mit Clipping) und einen gemeinsamen symmetrischen Differenz-Maßstab (`difference_scale`, chunkweise, 0 bleibt Mittelgrau); die Statistik wird in `st.session_state` pro Stapel gecacht, damit Slider bei voller Geometrie nicht neu über hunderte MB lesen. Die Sample-Options inkl. Run-Button wanderten in einen eigenen Tab „🚀 Forward Projection" zwischen Geometry und Sinogram Inspection (`render_forward_projection_tab`); der Sinogram-Tab ist damit reines Bildraster. Die Namen der beiden Index-Slider sind nur noch für Screenreader vorhanden. 6 neue Helper-/Cache-Tests, Suite **411 passed, 0 skipped**, flake8/black/isort sauber; im Browser (Port 8506) Tab-Reihenfolge, FP-Controls, ausgeblendete Slider-Namen und alle sechs Grauwert-Bilder ohne Exception geprüft.

### `[x]` T-11-02 — 3D-Trajektorien-Punkte vektorisiert (Queue-Anfrage gemessen und abgelehnt)
- **Ziel:** Die Punktberechnung für das 3D-Overlay (`get_trajectory_positions`) ist schnell genug, dass eine Geometrie-Änderung sie nicht in die Action-Queue stellen muss — gemessen, belegt und den Bedarf damit korrigiert.
- **Hintergrund:** Nutzerwunsch „bei Geometrie-Änderung die Geometrie-Berechnung ebenfalls in die Queue". Die Messung widerlegt die Prämisse: `get_trajectory_positions` kostete 12,5 ms bei den Default-2304 Projektionen (302 ms bei 51k) — die Queue (Worker-Thread, Toast, 1-Hz-Rerun-Poller) hätte pro Job mehr gekostet als die Berechnung selbst. Der sichtbare Freeze nach einer Geometrie-Änderung stammt aus dem Trace-Aufbau (`add_trajectory_to_figure`, 4,8 s bei Downsample 1/1 wegen ~2300 Traces) und dem Isosurface (~0,5 s, `create_volume_figure`), die als UI-Renderpfad auf dem Script-Thread bleiben.
- **Dateien:** `src/visualization/volume3d.py` (`get_trajectory_positions` numpy-vektorisiert), `tests/unit/test_geometry_trajectory.py` (+1 Regressionstest), `AGENTS.md`, `docs/plan.md`
- **Abhängig von:** T-104
- **Umsetzung:** Winkel und z-Feed werden als numpy-Arrays ausgewertet (`linspace(endpoint=False)` für `i/n · total_angle`, `arange(n) · z_step` um den zentrierten Helix-Feed) und per `zip(...tolist())` in die bisherige Kontraktform (Liste von `(x, y, z)`-Tuples) überführt — die Tupel-Erzeugung war nach der Vektorisierung der Restkosten-Treiber. Ein Regressionstest pinnt die vektorisierte Ausgabe an die skalaren `get_source_position`/`get_detector_position`-Formeln (Helix, alle Offsets, rel 1e-9).
- **Akzeptanz:** Vektorisierte Ausgabe == skalare Formeln; 2304 Projektionen ≤ 5 ms, 51k ≤ 100 ms (vorher 12,5 / 302 ms); Suite grün, 0 Skips; Lint sauber.
- **Status:** ✅ Done (Nov 26, 2026) — 12,5 → 2,6 ms (2304) bzw. 302 → 57 ms (51k); Suite 412 passed / 0 skipped, flake8/black/isort sauber. Offene Folgekosten bewusst nicht angefasst: Detector-Plane-Traces (bis ~0,5 s bei Downsample 1/10) und ungecachtes `create_volume_figure` (~0,5 s pro Rerun) — Kandidaten für einen eigenen Task.

### `[x]` T-11-03 — Comparison-Views standardmäßig quadratisch
- **Ziel:** Alle Slots im Sinogram-Inspection-Tab (beide Reihen) sind standardmäßig quadratisch: Höhe = gerenderte Spaltenbreite via CSS `aspect-ratio`, unabhängig von der Fensterbreite. Die Python-Höhen (`comparison_view_height`, `PLACEHOLDER_HEIGHT_PX`) werden zum Fallback.
- **Hintergrund:** Nutzerwunsch „make first row measured sinogram window square as default". Bisher maßen die Boxen 300 × 512 px (Höhe = größte Frame-Seite, gedeckelt 360–720 px) — ein hohes Fenster mit großen Leerrändern, in dem das gemessene Sinogramm (~35 px Bildhöhe) vertikal zentriert versank.
- **Dateien:** `src/visualization/projection_panel.py` (`SQUARE_VIEW_CSS`, Injektion in `render_comparison_tab`, `_render_placeholder` als `.sino-placeholder`-Div, Doku zu `comparison_view_height`), `tests/integration/test_ui_smoke.py` (`_main_text` liest Markdown, Placeholder-Test zählt 6 quadratische Slots + Stylesheet, toter `_block_heights`-Helper entfernt, `test_comparison_tab_lists_missing_inputs` liest Markdown), `AGENTS.md`, `docs/plan.md`
- **Abhängig von:** T-11-01
- **Umsetzung:**
  1. `SQUARE_VIEW_CSS`: `iframe.stIFrame, iframe[title="st.iframe"] { height: auto !important; aspect-ratio: 1 / 1 !important; }` — beides Selector-Paare auf dieselben iframes, damit die Streamlit-Pin-Range (1.37–1.39) abgedeckt ist; `.sino-placeholder` als flex-zentrierter, gestrichelter Quadrat-Div. Der Demo-Banner und die `st.info`-Boxen im Geometry-Tab sind vom Selector nicht betroffen (bewusst kein `:has(stAlert)`).
  2. `_render_placeholder` rendert den Hinweis als `.sino-placeholder`-Div statt `st.container(height=...)` + `st.info` — der Slot selbst ist quadratisch und reserviert exakt den Footprint eines gefüllten Views. Der Text wandert damit von `at.info` nach `at.markdown`, deshalb lesen die Smoke-Tests Markdown mit.
  3. Alternativen verworfen: `streamlit:setFrameHeight`-Selbstresize aus dem iframe (im Live-Test ignoriert der Streamlit-Elternknoten die Message für `components.html` nicht respektiert — kein Resize) und serverseitige Spaltenbreiten-Schätzung (unbekannt im Backend).
- **Akzeptanz:** Alle sechs Slots quadratisch bei beliebiger Fensterbreite; beide Reihen bündig; Placeholder-Texte weiterhin in den Smoke-Tests sichtbar; Suite grün, 0 Skips; Lint sauber.
- **Status:** ✅ Done (Nov 26, 2026) — im Browser (Port 8501) verifiziert: gefüllte Views 190 × 190 px, leere Slots 188 × 188 px (vorher 300 × 512); Suite 412 passed / 0 skipped, flake8/black/isort sauber.

## Phase 12 — Release Readiness (Nov 13, 2026)

Nächster Meilenstein (Grilling-Round vom 13.11.2026): Deploy/Env-lose Enden schließen (T-73 CI-Route), Plan-Hygiene und Helix-FP-Verifikation. Nutzerentscheidung: Helix-FP gehört **in** den Meilenstein, nicht danach.

### `[x]` T-104 — Helix-FP-Verifikation und Doku-Sync
- **Ziel:** Die Helix-Vorschub-Implementierung (z-feed pro Projektion, `b7b7279`) durch Tests absichern und die veraltete Doku korrigieren.
- **Hintergrund:** `src/backend/forward_project.py` rechnet seit `b7b7279` einen Helix-Vorschub (`z_step = pitch * n_rows * row_spacing / ppr`); `src/backend/parallelproj/geometry.py` wendet per-Projektion-z an. Die frühere T-94-Notiz („Projektor ignoriert pitch/Tabellenvorschub") ist damit veraltet.
- **Dateien:** `tests/unit/test_forward_project.py` (Helix-Tests), `src/backend/forward_project.py` (nur falls die Tests eine Lücke zeigen), `docs/geometry.md`, `docs/plan.md` (T-94-Notiz), Spec in `docs/superpowers/specs/` (vor Umsetzung)
- **Abhängig von:** T-63, T-79
- **Umsetzung:**
  1. Spec schreiben (Workflow: brainstorm → spec → plan), bevor die Tests umgesetzt werden.
  2. Tests: `pitch > 0` verschiebt Projektionen entlang z messbar und reproduzierbar (`z_step`-Formel gepinnt); `pitch = 0` bleibt exakt zirkulär (identisch zum bisherigen Pfad); Helix-FP und 3D-Trajektorie (`get_trajectory_positions` mit `pitch > 0`) stimmen überein.
  3. Doku-Sync: `docs/geometry.md` Helix-Abschnitt ergänzen/angleichen.
- **Akzeptanz:** Helix-Tests grün; `pitch = 0` verhält sich bit-identisch zum bisherigen Verhalten; `docs/geometry.md` und die T-94-Notiz beschreiben den Ist-Zustand; Suite grün, 0 Skips.
- **Status:** ✅ Done (Nov 17, 2026) — 5 neue Tests in `test_forward_project.py` (Slab-Shift: nur die z=0-Projektion trifft die attenuierende Ebene, reproduzierbar; `pitch = 0` zirkulär und gleich; exakte z-Formel inkl. `n_projections_total` und Original-Index-Selektion, Detektor reitet auf z; `z_step = 0` = Pre-Helix-Pfad; FP ↔ `get_trajectory_positions`, Quellen und zentrale Detektor-Pixel, atol 1e-2 mm). Helix-Sektion in `docs/geometry.md`; Test-Bar 351 → 356. Keine Produktionsänderung nötig — die Tests bestätigen den Ist-Zustand. Spec: `docs/superpowers/specs/2026-11-17-helix-fp-verification-design.md`, Plan: `docs/superpowers/plans/2026-11-17-helix-fp-verification.md`.

### `[ ]` T-105 — Image veröffentlichen (GHCR + Tarball)
- **Ziel:** Kunden kommen an das `:full`-Image, ohne das Repo zu klonen oder Docker zu bauen.
- **Dateien:** `.github/workflows/ci.yml`, `scripts/export-image.sh`
- **Abhängig von:** T-73
- **Akzeptanz:** CI baut `:full` und `:slim` und pusht beide auf `main`/Tags nach GHCR; `docker save`-Tarball ist als Release-Asset verfügbar (Offline-Weg).
- **Status:** ⚠️ Open (Nov 17, 2026) — es gibt aktuell **keinen** Push-Job; `ci.yml` enthält nur Daten-Guard, Lint und Tests.

### `[x]` T-106 — Image-Name `ctbeamstudio` und Release-Versionierung
- **Ziel:** Ein Commit baut zwei Images; trotzdem muss „Release 1.0.0" genau ein Image bedeuten. Dazu kommen Name, Tag-Schema und ein automatisierter Release.
- **Dateien:** `Dockerfile`, `README.md`, `INSTALLATION.md`, `docs/versioning.md`, `docs/customer-docker-guide.md`, `scripts/run-docker.sh`, `scripts/run-docker.ps1`, `.github/workflows/release.yml` (neu)
- **Abhängig von:** T-73, T-105
- **Akzeptanz:** Image heißt `ctbeamstudio` (Container `ctbeamstudio`, Volume `ctbeamstudio-cache`, Tarball `ctbeamstudio-1.0.0-full.tar`); Conda-Env und Python-Distribution bleiben `ct-viewer`; `1.0.0`/`1.0`/`latest` zeigen alle auf `full` und denselben Digest; `release.yml` bricht ab, wenn `pyproject.toml`-Version und `v*`-Tag auseinanderlaufen, und hängt Digest + Tarball an das GitHub-Release.
- **Status:** ✅ Done (Nov 17, 2026) — Erster echter Release-Lauf am 17.11.2026 grün (Run #1, `v1.0.0` → `54ab0f4`): Lockstep-Check, Build ~2 min (CI-Cache), Tag+Push via `release_push.sh`, Digest `sha256:c62b760c…` in den Release-Notes, Asset `ctbeamstudio-1.0.0-full.tar.gz` 735 MB (gzip von 3,05 GiB, unter dem 2-GiB-Cap). `docker manifest inspect` ohne Login bestätigt: Pull ohne Auth. Verbleibend: manuell **immutable Tags** in den Package-Settings aktivieren; CI-Suite-Gate `362 passed, 0 skipped` vor Merge-Klassifizierung; T-105 (Push auf main/PR) offen.

### `[x]` T-107 — README und Doku auf den Code-Stand bringen
- **Ziel:** Wer über das Repo einsteigt (Recruiter, Contributors, Kunden), darf keinen Widerspruch zwischen Text und laufender Demo sehen. Die README ist die öffentliche Einstiegsseite.
- **Dateien:** `README.md`, `AGENTS.md`
- **Abhängig von:** T-67, T-68, T-69, T-104
- **Akzeptanz:**
  - Weg mit der Roadmap-Aussage, FP und Vergleich seien „planned" — der Vergleich steht als Kernfunktion vorn.
  - Usage beschreibt den echten Ablauf (drei Tabs, Text-Input statt „folder picker", `src/visualization/app.py`).
  - Keine Zusage, die die UI nicht einlöst (NumPy-Volumes), keine Links auf nicht getrackte Dateien.
  - Test-Bar in `AGENTS.md` stimmt mit dem Lauf überein.
- **Status:** ✅ Done (Nov 18, 2026) — README neu geordnet: Kernfunktion (simuliert vs. gemessen) zuerst, Features nach Workflow (Vergleich / Forward Projection / Geometrie / Viewer / Engineering), Roadmap → knapper Status-Abschnitt, Usage auf die drei Tabs umgestellt, Development-Abschnitt ergänzt, NumPy-Volume-Versprechen entfernt (kein UI-Pfad). `AGENTS.md`: erfundener `slow`-Marker und „7 slow Tests deselected" entfernt, `bash`-Voraussetzung von `test_release_push.py` dokumentiert. Lauf: `362 passed`; die 4 Fehler in `test_release_push.py` sind lokal (kein `bash` auf `PATH`), nicht durch diese Änderung verursacht.

## Zeitplan (Tag 1–16)

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
| 13 | Do, 12.11. | T-90 ✅ bis T-99 ✅ (Achsenreihenfolge für DICOM + sofortige Anwendung; Env-Pflicht, 0 Skips; Lazy Subset-Reads für Sinogramme; Dummy-Messung fürs Demo-Phantom; 3D-Ansicht im echten FP-Weltkoordinatensystem; Demo-Origin zentriert; Auto-Dummy-Messung beim Demo-Bild-Laden; Sinogram-Ansichten im korrekten Spacing; Messungs-Laden lädt die ganze Datei; Geometrie-Laden im Geometry-Tab) |
| 14 | Do, 12.11. | T-101 ✅ (Shepp-Logan-Phantom um 90° gedreht — klassische Scheibe in der Koronalebene, erste anterior-Projektion zeigt das aufrechte Oval; Kamera-Presets front=+X; geometry.md-Koordinaten-Section konsolidiert) + T-102 ✅ (Geometry auch bei .npy/NIfTI-Messungs-Laden mitgeführt — Default 2304 Projections/Rotation) |
| 15 | Fr, 13.11. | Grilling-Round (plan.md): T-104 geplant (Helix-FP-Verifikation; z-feed gelandet in `b7b7279`), Teil des Release-Readiness-Meilensteins; T-73 → CI-Route (Smoke + < 400 MiB in CI, kein lokales Docker); T-23.8 ✅ durch T-94; T-61 ✅ by design (conda-only); T-56a ❌ dropped; Mouse-Wheel → Backlog; T-76/T-77 → Research-Backlog; Erledigt-Sektionen dedupliziert, Tag-13-Datum korrigiert |
| 16 | Di, 17.11. | T-104 ✅ (Helix-FP-Verifikation: 5 neue Tests — Slab-Shift mit `z_step = 3 mm`, `pitch = 0` zirkulär, exakte z-Formel inkl. Original-Index, `z_step = 0` = Pre-Helix-Pfad, FP ↔ 3D-Trajektorie; `docs/geometry.md` Helix-Sektion; Test-Bar 351 → 356) |

## Research-Backlog (Nov 13, 2026 — nicht eingeplant)

T-75 bis T-77 sind aus dem aktuellen Projektumfang genommen (T-75 kam aus dem
Umfeld der 3D-Phase hierher, T-76/T-77 aus der Grilling-Round vom 13.11.2026); die
T-Nummern bleiben referenzierbar. Reaktivierung über einen eigenen Spec (Workflow:
brainstorm → spec → plan).

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

### `[ ]` T-76 — FDK / Analytische Rekonstruktion
- **Ziel:** FDK-Algorithmus für CBCT-Rekonstruktion implementieren.
- **Dateien:** `src/reconstruction/fdk.py` (bei Reaktivierung prüfen: numerical Code gehört nach D-9 nach `src/backend/`)
- **Abhängig von:** T-61
- **Implementierung:**
  1. Pre-Weighting (FDK weight)
  2. FFT-basierte Filterung (Ram-Lak, Shepp-Logan)
  3. Parker weighting für short-scan
  4. Cone-beam backprojection
- **Optionen:** ASTRA (bestehend), TomoPy, oder eigene Implementierung
- **Status:** ⚠️ Research-Backlog (Nov 13, 2026) — aus dem aktuellen Umfang genommen; Reaktivierung mit eigenem Spec.

### `[ ]` T-77 — Phantomlose Geometrie-Kalibrierung
- **Ziel:** Geometrie aus Projektionsdaten schätzen ohne Kalibrierphantom.
- **Dateien:** `src/calibration/geometry_calibration.py`
- **Abhängig von:** T-63, T-76
- **Implementierung:**
  1. Merkmalsextraktion (Kanten, Features)
  2. Feature-Tracking über Projektionen
  3. Bundle Adjustment: Geometrie + 3D-Punkte optimieren
  4. DCC-basierte Regularisierung
- **Status:** ⚠️ Research-Backlog (Nov 13, 2026) — aus dem aktuellen Umfang genommen; hängt an T-76.
- **Siehe auch:** `docs/research/phantomless-geometry-calibration-helix-cbct.md`

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
| D-18 | 2026-11-10 | Kein eigener Fullscreen-Code — Streamlits `stFullScreenFrame` nutzen | `st.image` bringt „View fullscreen" mit, Streamlit injiziert denselben Mechanismus als Modebar-Button in `st.plotly_chart` (`modeBarButtonsToAdd`); 3D-Vollbild verifiziert (`399×700` → `1088×612`), Bild-Vollbild skaliert das Bild nicht mit |
| D-19 | 2026-11-12 | `axis_order` gilt für alle Formate; ein DICOM-Ordner wird gemäß Deklaration transponiert statt ignoriert | Der Stapel `(proj,row,col)` ist strukturell eindeutig, aber wer die Detektorachse vertauscht gespeichert hat, muss das sagen können — sonst bleibt der einzige Weg zur Korrektur ein Umpacken der Dateien |
| D-20 | 2026-11-12 | Achsenreihenfolge wird beim Ändern **sofort** angewandt, nicht erst beim nächsten Lade-Klick | Der Nutzer beurteilt die Auswahl am Bild; ein Regler, der scheinbar nichts tut, gilt als defekt (gemeldeter Fehler) |
| D-21 | 2026-11-12 | Projektbefehle laufen ausschließlich im Conda-Env `ct-viewer`; ein Skip im Testlauf gilt als Defekt | `parallelproj_c.dll` liegt nur im aktivierten Env auf `PATH` — ein System-Interpreter *überspringt* die parallelproj-Tests, statt sie laufen zu lassen; das sieht wie grün aus, ist aber verlorene Abdeckung |
| D-22 | 2026-11-12 | `nibabel` steht in `dev` **und** in `nifti`; kein `cpu`/`gpu`-Extra | Die Suite deckt NIfTI ab, also muss die Test-Abhängigkeit `dev` sein — sonst skippt ein grüner Lauf still vier Tests. `parallelproj` ist conda-forge-only und kann kein pip-Extra sein; ein nicht existierendes Extra akzeptiert pip warnungslos und installiert nichts |
| D-23 | 2026-11-12 | Dummy-Messung puffert nur das **ideale** FP auf Disk (`data/cache/`, gitignored); Streuung/Rauschen bleiben live; Phantom zentriert auf der Rotationsachse; FP-Auswahl wird auf „all" presetet | Der FP ist der einzige teure Schritt (~10–20 s CPU) — Puffer macht jeden weiteren Klick ~3,5 s; live-Streuung hält `spr`/`i0`/`seed` ohne Re-Projektion veränderbar; ohne Zentrierung parkt der Demo-Origin (0,0,0) den Kopf außerhalb von FOV und Kegel (gemessen); „all" lässt einen Klick auf „Run Forward Projection" die Messform exakt reproduzieren. Keine committeden Binärdateien (CI-Data-Guard, Hard Rule) |
| D-24 | 2026-11-12 | 3D-Ansicht positioniert das Volumen am **echten DICOM-Origin** im Weltkoordinatensystem der FP statt schematisch zentriert; Detektor-Ebene bei `sdd - sid` statt `-sdd` | Die Ansicht soll zeigen, was die FP tatsächlich rechnet (gemeldeter Fehler: 3D-Plot Zentralstrahl durch die Phantommitte, FP Phantom oben am Detektor). Mit Origin (0,0,0) parkt der Demo-Kopf im `+`-Oktanten — die Diskrepanz wird sichtbar statt versteckt; SDD ist ab Source gemessen, die Ebene lag `sid` mm zu weit außen |
| D-25 | 2026-11-12 | Demo-Phantom-Origin zentriert auf die Rotationsachse (T-95); die Dummy-Messung wird automatisch beim Laden des Demo-Bildes erzeugt statt nur per Button (T-96) | Bei Origin (0,0,0) parkte der Demo-Kopf im `+`-Oktanten — seit T-94 zeigten FP und 3D-Ansicht ihn gewollt off-center; zentriert stimmen FP, 3D-Ansicht und MPR-Readout überein. Die Messung gehört zum Demo-Erlebnis: wer das Demo-Bild lädt, will den kompletten Vergleich ohne extra Klick (FP-Puffer macht den Auto-Pfad ~3,5 s) |
| D-26 | 2026-11-18 | Der Plan sortiert Aufgaben nach **Thema**; T-Nummern werden nie neu vergeben und nie umsortiert | Die Nummern stehen in Code, Tests, CI, Specs und Commit-Messages (knapp 800 Fundstellen); ein thematisches Renumbering würde Historie und Referenzen brechen, ohne dem Leser zu helfen. Die Phase trägt das Thema, die Nummer bleibt stabil — Aufgaben wandern beim Umsortieren, Nummern nicht |
| D-27 | 2026-11-26 | Ein Commit enthält **nur** die Dateien der eigenen Session (`git add <Datei>`); `git add .` / `git add -A` / `git commit -a` sind tabu | Der Baum kann fremde oder halb fertige Änderungen des Nutzers halten — ein pauschales Staging schleift sie unkontrolliert mit ein. `git status --short` vor dem Stagen gehört zum Done |

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
- ~~T-23.8: Tests für volume3d.py~~ — ✅ durch T-94 abgedeckt (`tests/unit/test_volume3d.py`, 5 Tests; Nov 13, 2026)
- Mouse-Wheel-Scrolling über Bilder — ⚠️ Backlog (Nov 13, 2026), UX-Polish zusammen mit T-87
- ~~T-61: parallelproj Dependency~~ — ✅ Done by design (Nov 13, 2026): conda-only, verbindlich dokumentiert (`AGENTS.md`, `environment.yml`)
- ~~T-104: Helix-FP-Verifikation und Doku-Sync~~ — ✅ Done (Nov 17, 2026): 5 Helix-Tests, `docs/geometry.md` Helix-Sektion, Test-Bar 356

## Implementation Notes

### 3D Visualization Features

| Feature | Description |
|---------|-------------|
| Render Mode | Iso-Surface (Plotly). PyVista shelved — see T-82 |
| Geometry Overlay | „Show projections" checkbox in the 3D options, plus „Trajectory Downsample"; the scan's projection count lives in the Geometry tab and also drives the forward projection |
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

