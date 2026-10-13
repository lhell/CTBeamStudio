# Format-Empfehlung

**Eine einzige Markdown-Datei `docs/PLAN.md`, versioniert im Repo.** Kein zweites YAML/JSON daneben — doppelte Quellen driften auseinander, und du pflegst dann zwei Wahrheiten.

| Format | Für dich | Für KI | Urteil |
|---|---|---|---|
| Markdown mit Task-IDs | sehr gut | sehr gut | **Empfehlung** |
| YAML/JSON-Plan | mühsam | gut | nur wenn Tooling ihn liest |
| GitHub Issues | gut | schlecht (Kontext nicht im Repo) | ergänzend, nicht als Quelle |
| Freitext-Notizen | gut | schlecht (keine Referenzen) | nein |
| Markdown + YAML-Spiegel | mittel | gut | Driftrisiko, nein |

Was Markdown KI-lesbar macht — diese sechs Regeln sind der eigentliche Unterschied:

1. **Stabile IDs** (`T-11`) statt „die DICOM-Aufgabe" — eindeutig referenzierbar über Sessions hinweg.
2. **Fixe Schlüssel pro Task**: `Ziel`, `Dateien`, `Abhängig von`, `Akzeptanz`. Gleiche Struktur überall, parsebar ohne Raten.
3. **Konkrete Repo-Pfade**, keine Umschreibungen.
4. **Akzeptanzkriterien als prüfbare Aussagen**, nicht als Wunsch („Loader ist robust" → unbrauchbar).
5. **Decision Log** am Ende: verhindert, dass bereits getroffene Entscheidungen neu diskutiert werden.
6. **Offene Fragen explizit markiert** — sonst füllt eine KI die Lücke mit Annahmen.

Status-Marker: `[ ]` offen, `[~]` läuft, `[x]` fertig, `[!]` blockiert.

---

Nachfolgend der Inhalt für `docs/PLAN.md`:

# CT-Viewer — Implementierungsplan

**Projekt:** `Res_Indep_CTO` / `src/visualization/`
**Stand:** 2026-10-13
**Start:** Mi, 2026-10-14

## Leitprinzipien

| Prinzip | Konsequenz |
|---|---|
| Keine Daten im Repo oder Image | nur Phantom + synthetische Fixtures |
| `pydicom` ausschließlich | kein SimpleITK, kein ITK |
| Viewer ohne Torch | separate Dependency-Gruppen |
| Datenintern HU | Normalisierung nur in der Darstellung |

## Phase 0 — Lizenz & Hygiene (Tag 1–2)

### `[ ]` T-01 — Lizenzdateien
- **Ziel:** Projekt ist rechtlich veröffentlichbar.
- **Dateien:** `LICENSE` (MIT), `NOTICE`, `SECURITY.md`
- **Abhängig von:** –
- **Akzeptanz:** Alle drei Dateien im Root; `NOTICE` nennt Fremdlizenzen von `pydicom`, `numpy`, `streamlit`, `pylibjpeg`.

### `[ ]` T-02 — Git-Historie prüfen
- **Ziel:** Keine Patientendaten oder Secrets in der Historie.
- **Dateien:** –
- **Abhängig von:** –
- **Akzeptanz:** `git log --all --diff-filter=A --name-only` enthält keine `.dcm`, `.npy`, `.ckpt`, `.env`. Bei Fund: History-Rewrite **vor** dem ersten Push.

### `[ ]` T-03 — Daten-Guards
- **Ziel:** Daten können nicht versehentlich veröffentlicht werden.
- **Dateien:** `.gitignore`, `.dockerignore`, `Dockerfile`, `.github/workflows/ci.yml`
- **Abhängig von:** T-02
- **Akzeptanz:** CI-Job schlägt fehl, wenn eine Testdatei `test.dcm` getrackt wird (lokal einmal verifizieren, dann zurücknehmen).

### `[ ]` T-04 — Datendokumentation
- **Ziel:** Zugang und Zitierpflicht dokumentiert.
- **Dateien:** `docs/data.md`, `CITATION.cff`, `configs/datasets/aapm_ldct2016.yaml`
- **Abhängig von:** –
- **Akzeptanz:** `docs/data.md` beschreibt Registrierungsweg der AAPM-Challenge 2016, enthält die wörtlichen Pflichtzitate und den Satz, dass das Repo keine Daten verteilt.

## Phase 1 — Kern (Tag 2–4)

### `[ ]` T-10 — `Volume`-Dataclass
- **Ziel:** Gemeinsames Austauschformat aller Loader.
- **Dateien:** `src/visualization/volume.py`
- **Abhängig von:** –
- **Akzeptanz:** Felder `array` (`np.int16`/`float32`, HU, Achsen `(z, y, x)`), `spacing` (mm, `(z, y, x)`), `origin`, `meta: dict`. `__post_init__` validiert Shape- und Spacing-Länge und wirft `ValueError` bei Spacing ≤ 0.

### `[ ]` T-11 — DICOM-Loader
- **Ziel:** DICOM-Serie → `Volume` in HU.
- **Dateien:** `src/visualization/loaders/dicom.py`
- **Abhängig von:** T-10
- **Akzeptanz:**
  - `scan_series(root)` gruppiert nach `SeriesInstanceUID`, liefert Patient, `SeriesDescription`, Slice-Anzahl, Dosisklasse.
  - Sortierung über Projektion von `ImagePositionPatient` auf die Schichtnormale aus `ImageOrientationPatient`.
  - HU über `RescaleSlope`/`RescaleIntercept`.
  - Inkonsistentes Slice-Spacing (> 1 % Abweichung) → `ValueError` mit Positionsangabe.
  - Gantry-Tilt (`ImageOrientationPatient` nicht achsparallel) → Warnung, kein Abbruch; in Docstring als v1-Limitation vermerkt.

### `[ ]` T-12 — NPY-Loader
- **Ziel:** Vorhandene AAPM-`.npy` laden.
- **Dateien:** `src/visualization/loaders/npy.py`
- **Abhängig von:** T-10
- **Entscheidung:** `preprocess_aapm.py` schreibt **rohe HU** → keine Rückskalierung, nur Plausibilitätsprüfung.
- **Akzeptanz:** Guard erkennt versehentlich normalisierte Arrays und bricht ab:

```python
HU_AIR_MAX = -500.0   # echte CT-Luft liegt bei ca. -1000
HU_RANGE_MIN = 300.0  # plausible Spannweite Luft..Knochen

def assert_hu(array: np.ndarray, source: str) -> None:
    lo, hi = float(array.min()), float(array.max())
    if lo > HU_AIR_MAX or (hi - lo) < HU_RANGE_MIN:
        raise ValueError(
            f"{source}: Wertebereich [{lo:.1f}, {hi:.1f}] sieht nicht wie HU aus. "
            "Erwartet rohe HU (Luft ca. -1000, Wasser ca. 0). "
            "Falls normalisiert: preprocess_aapm.py prüfen."
        )
```

### `[ ]` T-13 — Windowing
- **Ziel:** HU → 8-bit Grauwerte.
- **Dateien:** `src/visualization/windowing.py`
- **Abhängig von:** T-10
- **Akzeptanz:** `apply_window(array, center, width)` liefert `uint8`; Presets `lung (-600/1500)`, `abdomen (40/400)`, `bone (400/1800)`, `brain (40/80)`; `width <= 0` → `ValueError`; Clipping ohne Überlauf bei `int16`-Eingang.

### `[ ]` T-14 — Reslicing / MPR
- **Ziel:** Axial, koronal, sagittal bei anisotropem Spacing.
- **Dateien:** `src/visualization/mpr.py`
- **Abhängig von:** T-10
- **Akzeptanz:** `extract_slice(volume, plane, index)` gibt Bild **und** In-plane-Spacing zurück; Seitenverhältnis wird aus dem Spacing berechnet, nicht aus der Pixelanzahl. Testfall: Volume mit Spacing `(3.0, 0.7, 0.7)` ergibt im koronalen Schnitt ein Aspect-Ratio von ≈ 4,29.

## Phase 2 — App (Tag 4–5)

### `[ ]` T-20 — Streamlit-App
- **Dateien:** `src/visualization/app.py`, `configs/viewer.yaml`
- **Abhängig von:** T-11, T-13, T-14
- **Akzeptanz:** Ebenenauswahl, Slice-Slider, Window-Presets + manuelle Center/Width-Eingabe; HU-Wert unter dem Cursor oder zumindest Min/Max der aktuellen Schicht sichtbar.

### `[ ]` T-21 — Serienauswahl
- **Dateien:** `src/visualization/app.py`
- **Abhängig von:** T-11, T-20
- **Akzeptanz:** Sidebar listet gefundene Serien mit Patient, Beschreibung, Dosisklasse, Slice-Anzahl; Serien unter 20 Slices sind als „Localizer?" markiert.

### `[ ]` T-22 — Demo-Phantom
- **Dateien:** `src/visualization/phantom.py`
- **Abhängig von:** T-10
- **Akzeptanz:** Start ohne `CT_VIEWER_DATA_ROOT` lädt synthetisches Phantom in plausiblen HU (Luft −1000, Wasser 0, Knocheneinschlüsse ~+800) mit anisotropem Spacing; Banner weist auf Demo-Modus hin.

### `[ ]` T-23 — Full/Low-Dose-Vergleich *(optional)*
- **Dateien:** `src/visualization/app.py`
- **Abhängig von:** T-21
- **Akzeptanz:** Bei zwei Serien gleicher Geometrie Side-by-Side mit gekoppeltem Slider und identischem Window. Entfällt bei Zeitdruck.

## Phase 3 — Tests (Tag 5)

### `[ ]` T-30 — Synthetische Fixtures
- **Dateien:** `tests/visualization/conftest.py`
- **Abhängig von:** T-10
- **Akzeptanz:** Fixture erzeugt per `pydicom` eine Serie im `tmp_path` mit korrekten `ImagePositionPatient`, `RescaleSlope/Intercept`, `SeriesDescription`; keine Binärdaten im Repo.

### `[ ]` T-31 — Loader-Tests
- **Dateien:** `tests/visualization/test_loaders.py`
- **Abhängig von:** T-11, T-12, T-30
- **Akzeptanz:** Abgedeckt: Sortierreihenfolge, HU-Umrechnung, Spacing-Mismatch → `ValueError`, `classify_dose`-Parametrisierung, `assert_hu` lehnt `[0,1]`- und `[-1,1]`-Arrays ab.

### `[ ]` T-32 — Windowing- & MPR-Tests
- **Dateien:** `tests/visualization/test_windowing.py`, `tests/visualization/test_mpr.py`
- **Abhängig von:** T-13, T-14
- **Akzeptanz:** Window-Grenzen exakt (0 und 255 an den Rändern), Aspect-Ratio-Fall aus T-14, `width=0` → `ValueError`.

### `[ ]` T-33 — Datenvalidierungsskript
- **Dateien:** `scripts/check_aapm.py`
- **Abhängig von:** T-11
- **Akzeptanz:** Tabellarische Ausgabe der Serien; Exit 2 bei fehlendem Verzeichnis oder null Serien; Warnung, wenn alle Serien `unknown` sind.

## Phase 4 — Deploy (Tag 6)

### `[ ]` T-40 — Dockerfile
- **Dateien:** `Dockerfile`, `.dockerignore`
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

## Zeitplan

| Tag | Datum | Tasks |
|---|---|---|
| 1 | Mi, 14.10. | T-01, T-02, T-03 |
| 2 | Do, 15.10. | T-04, T-10, T-13 |
| 3 | Fr, 16.10. | T-11, T-12 |
| 4 | Sa, 17.10. | T-14, T-20 |
| 5 | So, 18.10. | T-21, T-22, T-30 – T-33 |
| 6 | Mo, 19.10. | T-40, T-41, T-42, T-23 falls Zeit |

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

## Offene Fragen

Keine blockierenden Punkte. D-6 hat den letzten Blocker (`NpyLoader`) aufgelöst.

Nicht blockierend, zu klären bis Tag 4:
- `assert_hu`-Schwellen (`HU_AIR_MAX`, `HU_RANGE_MIN`) gegen einen echten AAPM-Fall kalibrieren — bei beschnittenen Volumes ohne Luft könnten sie zu streng sein.
- Window-Preset für den Start: `abdomen` oder aus `configs/viewer.yaml`?

## Risiken

| Risiko | Gegenmaßnahme |
|---|---|
| DUA-Verstoß | T-03 Guards, T-42 Hinweis, Phantom im Image |
| Daten in Git-Historie | T-02 vor erstem Push |
| MPR verzerrt bei anisotropem Spacing | T-14 Spacing-basierte Aspect-Ratio + Test |
| Normalisierte `.npy` schleichen sich ein | T-12 `assert_hu` bricht ab |
| Zeitplan reißt | T-23 ist explizit optional |

---

Soll ich als nächstes T-10 bis T-12 ausimplementieren (`volume.py`, `dicom.py`, `npy.py`), oder zuerst Phase 0 — also `LICENSE`, `NOTICE`, `SECURITY.md`, `docs/data.md` und die Guards?