# Day 01 Protocol — CTOrientationViewer
**Datum:** Mi, 14.10.2026  
**Phase:** Phase 0 — Lizenz & Hygiene

---

## 🎯 Goals

| Task | Beschreibung | Status |
|------|--------------|--------|
| T-01 | Lizenzdateien erstellen | ✅ |
| T-02 | Git-Historie auf Patientendaten prüfen | ✅ |
| T-03 | Daten-Guards implementieren | ✅ |
| T-04 | Datendokumentation | ✅ |

---

## ✅ Completed Tasks

### T-01 — Lizenzdateien

| Datei | Erstellt |
|-------|----------|
| `LICENSE` | ✅ MIT License |
| `NOTICE` | ✅ Fremdlizenzen (pydicom, numpy, streamlit, pylibjpeg) |
| `SECURITY.md` | ✅ Security Policy |

### T-02 — Git-Historie

- **Befehl ausgeführt:**
  ```bash
  git log --all --diff-filter=A --name-only | Select-String -Pattern "\.(dcm|npy|ckpt)$"
  git log --all --diff-filter=A --name-only | Select-String -Pattern "\.env$"
  ```
- **Ergebnis:** Keine Patientendaten in der Git-Historie ✅

### T-03 — Daten-Guards

| Datei | Status | Ergänzung |
|-------|--------|-----------|
| `.gitignore` | ✅ Update | `.dcm`, `.ima`, `.npy`, data/, etc. |
| `.dockerignore` | ✅ Create | Data + Secrets blocken |
| `Dockerfile` | ✅ Create | Build-Guard integriert |
| `.github/workflows/ci.yml` | ✅ Create | Data-Guard Job |

**Hinweis:** `.ima` Endung zu allen Guards hinzugefügt (für GE DICOM)

### T-04 — Datendokumentation

| Datei | Erstellt |
|-------|----------|
| `docs/data.md` | ✅ Inkl. IMA, Generic DICOM |
| `CITATION.cff` | ✅ |
| `configs/datasets/aapm_ldct2016.yaml` | ✅ |

---

## 📦 Additional Deliverables

| Datei | Beschreibung |
|-------|--------------|
| `pyproject.toml` | Projekt-Konfiguration (Python ≥3.11) |
| `requirements.txt` | ❌ Deleted (now in pyproject.toml) |
| `requirements-dev.txt` | ❌ Deleted (now in pyproject.toml) |
| `README.md` | Vollständige Projekt-Doku |
| `.github/workflows/ci.yml` | CI Pipeline |
| `Dockerfile` | Container mit Build-Guard |

---

## 📋 Plan Updates

| Änderung | Details |
|----------|---------|
| **T-23 (neu)** | 3D-Visualisierung mit Quelle/Detektor |
| **T-43 (neu)** | Requirements (pyproject.toml) |
| **T-44 (neu)** | Deployment (GHCR/Streamlit Cloud) |
| **T-23 (alt)** | ❌ Removed (Full/Low-Dose-Vergleich) |
| **Zeitplan** | Ohne Wochenende, nur Mo–Fr |

### Neuer Zeitplan

| Tag | Datum | Tasks |
|-----|-------|-------|
| 1 | Mi, 14.10. | T-01 bis T-04 ✅ |
| 2 | Do, 15.10. | T-10, T-13 |
| 3 | Fr, 16.10. | T-11, T-12 |
| 4 | Mo, 19.10. | T-14, T-20 |
| 5 | Di, 20.10. | T-21, T-22, T-23, T-30 – T-33 |
| 6 | Mi, 21.10. | T-40, T-41, T-42, T-43 |
| 7 | Do, 22.10. | T-44 (optional) |

---

## 📦 pyproject.toml — Vorteile

| Vorteil | Beschreibung |
|---------|--------------|
| **Single Source of Truth** | Dependencies nur an einer Stelle (pyproject.toml) |
| **Editable Install** | `pip install -e .` — Änderungen sofort wirksam |
| **Optional Dependencies** | `pip install -e ".[dev]"` für Tests/Linting |
| **Standard** | Moderner Python-Standard (PEP 517/518) |
| **Tool-Konfiguration** | pytest, black, isort, mypy direkt integriert |
| **Docker** | `pip install -e /app/` im Dockerfile |

### Umstellung auf pyproject.toml

- `requirements.txt` + `requirements-dev.txt` → **gelöscht**
- `Dockerfile` aktualisiert: nutzt jetzt `pip install -e .`
- `README.md` aktualisiert: `pip install -e .` statt `-r requirements.txt`

---

## 🔧 Tech Stack

- **Python:** ≥3.11
- **Core:** pydicom, numpy
- **UI:** Streamlit
- **3D:** PyVista, Plotly
- **Dev:** pytest, black, isort, flake8, mypy

---

## 📁 Final File Structure

```
CTOrientationViewer/
├── .github/workflows/ci.yml
├── configs/datasets/aapm_ldct2016.yaml
├── docs/
│   ├── data.md
│   └── plan.md
├── src/                    # (future)
├── tests/                  # (future)
├── .gitignore
├── .dockerignore
├── CITATION.cff
├── Dockerfile
├── LICENSE
├── NOTICE
├── README.md
├── SECURITY.md
├── pyproject.toml
└── app.py                  # (future)
```

---

## 🚀 Next Steps (Day 02)

1. **T-10** — Volume-Dataclass (`src/visualization/volume.py`)
2. **T-13** — Windowing (`src/visualization/windowing.py`)

---

## Notes

- IMA-Datenpfad für Tests: `O:\imageDataCT\Laura\data_lowDose_aapm\1mm B30-selected\full_1mm\L067\full_1mm`
- Gantry-Tilt wird vorerst nicht unterstützt (AAPM-Daten haben keinen)
- Keine Daten im Repo/Image — nur Phantom + synthetische Fixtures
