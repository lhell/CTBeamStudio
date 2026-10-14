# Plan Day 01 — Phase 0: Lizenz & Hygiene

**Datum:** Mi, 14.10.2026  
**Tasks:** T-01, T-02, T-03, T-04

## Übersicht

| Task | Beschreibung | Abhängigkeiten | Geschätzte Zeit |
|------|--------------|----------------|-----------------|
| T-01 | Lizenzdateien erstellen | – | 30 min |
| T-02 | Git-Historie auf Patientendaten prüfen | – | 15 min |
| T-03 | Daten-Guards implementieren | T-02 | 45 min |
| T-04 | Datendokumentation | – | 30 min |

---

## T-01 — Lizenzdateien

### Ziel
Projekt ist rechtlich veröffentlichbar.

### Dateien
- `LICENSE` (MIT License)
- `NOTICE`
- `SECURITY.md`

### Akzeptanzkriterien
- Alle drei Dateien im Root-Verzeichnis
- `NOTICE` nennt Fremdlizenzen von: `pydicom`, `numpy`, `streamlit`, `pylibjpeg`

### Umsetzung

#### 1. LICENSE (MIT)
```
MIT License

Copyright (c) 2026 CT-Viewer Project

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

#### 2. NOTICE
```
CT-Viewer Notice
================

This project includes the following third-party components:

- pydicom: https://github.com/pydicom/pydicom
  License: BSD 3-Clause "New" or "Revised" License

- numpy: https://numpy.org
  License: BSD 3-Clause "New" or "Revised" License

- streamlit: https://streamlit.io
  License: Apache License 2.0

- pylibjpeg: https://github.com/pydicom/pylibjpeg
  License: BSD 3-Clause "New" or "Revised" License

The CT-Viewer project itself is licensed under the MIT License.
See the LICENSE file for details.

AAPM LDCT Challenge 2016 Data
=============================
This software is designed to work with data from the AAPM Low-Dose CT
Challenge 2016. The challenge data is NOT distributed with this software.
Users must register separately at the challenge website to obtain access.

Please cite the original challenge data if you use it in your research:
- The AAPM TG-201 supplementary data on low-dose CT
- Reference: https://www.aapm.org/grandchallenge/lowdosect/
```

#### 3. SECURITY.md
```markdown
# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability within this software, please send an email to the project maintainers. All security vulnerabilities will be promptly addressed.

Please include the following information:
- Type of vulnerability
- Full path of source file(s) related to vulnerability
- Location of the affected source code
- Any special configuration required to reproduce the issue
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue

## Security Best Practices

- Never commit patient data, credentials, or secrets to the repository
- Use environment variables for sensitive configuration
- Review `.gitignore` and ensure no sensitive files are tracked
```

---

## T-02 — Git-Historie prüfen

### Ziel
Keine Patientendaten oder Secrets in der Git-Historie.

### Akzeptanzkriterien
```bash
git log --all --diff-filter=A --name-only
```
enthält keine:
- `.dcm` Dateien
- `.npy` Dateien
- `.ckpt` Checkpoint-Dateien
- `.env` Environment-Dateien

### Umsetzung

#### 1. Prüfen ob Dateien im Repo sind
```bash
# Check for binary data files in git history
git log --all --diff-filter=A --name-only | grep -E '\.(dcm|npy|ckpt)$'

# Check for env files
git log --all --diff-filter=A --name-only | grep -E '\.env$'
```

#### 2. Falls Dateien gefunden werden: History Rewrite
```bash
# Using git filter-branch (older) or git filter-repo (recommended)
# Install git-filter-repo first: pip install git-filter-repo

# Example for removing .dcm files
git filter-repo --path '*.dcm' --invert-paths

# Or for a specific file
git filter-repo --path path/to/sensitive_file.dcm --invert-paths
```

#### 3. Verifikation nach Rewrite
```bash
# Force push to update remote (nur nach Absprache!)
git push --force --all
git push --force --tags
```

---

## T-03 — Daten-Guards

### Ziel
Daten können nicht versehentlich veröffentlicht werden.

### Dateien
- `.gitignore`
- `.dockerignore`
- `Dockerfile`
- `.github/workflows/ci.yml`

### Akzeptanzkriterien
CI-Job schlägt fehl, wenn eine Testdatei `test.dcm` getrackt wird.

### Abhängigkeiten
- T-02 (Git-Historie muss sauber sein)

### Umsetzung

#### 1. `.gitignore` erweitern
```gitignore
# CT Data - NEVER commit
*.dcm
*.dicom
*.npy
*.npz
*.h5
*.hdf5
*.ckpt
*.pth
*.pt
*.onnx

# Data directories
data/
datasets/
CT_DATA/
patient_data/

# Secrets
.env
.env.local
*.pem
*.key

# OS
.DS_Store
Thumbs.db

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
.venv/
*.egg-info/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Streamlit
.streamlit/secrets.toml
```

#### 2. `.dockerignore` erstellen
```dockerignore
# Git
.git
.gitignore

# Data (must not be in image)
*.dcm
*.npy
data/
datasets/

# Python
__pycache__
*.pyc
.venv
venv

# IDE
.vscode
.idea

# Secrets
.env
*.pem

# OS
.DS_Store
Thumbs.db
```

#### 3. Dockerfile — Data Guard Erweiterung
```dockerfile
# Build Guard: Fail if data files exist
RUN find /app -type f \( -name "*.dcm" -o -name "*.npy" \) && \
    echo "ERROR: Data files found in repository!" && exit 1 || \
    echo "Data guard: OK"
```

#### 4. CI Workflow — Data Guard Job
```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  data-guard:
    name: Data Guard
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Check for data files
        run: |
          # Check for common data file extensions
          FOUND_FILES=$(find . -type f \( -name "*.dcm" -o -name "*.npy" -o -name "*.ckpt" \) 2>/dev/null)
          
          if [ -n "$FOUND_FILES" ]; then
            echo "ERROR: Data files found in repository:"
            echo "$FOUND_FILES"
            exit 1
          fi
          
          echo "Data guard: No data files tracked"

  lint:
    name: Lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install flake8 black isort
      - name: Run flake8
        run: |
          flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
      - name: Run black
        run: |
          black --check .
      - name: Run isort
        run: |
          isort --check-only .

  test:
    name: Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
      - name: Run pytest
        run: |
          pytest tests/ -v
```

---

## T-04 — Datendokumentation

### Ziel
Zugang und Zitierpflicht dokumentiert.

### Dateien
- `docs/data.md`
- `CITATION.cff`
- `configs/datasets/aapm_ldct2016.yaml`

### Akzeptanzkriterien
- `docs/data.md` beschreibt Registrierungsweg der AAPM-Challenge 2016
- Enthält die wörtlichen Pflichtzitate
- Enthält den Satz, dass das Repo keine Daten verteilt

### Umsetzung

#### 1. `docs/data.md` erstellen
```markdown
# Daten-Dokumentation

## AAPM Low-Dose CT Challenge 2016

Dieses Projekt ist für die Verwendung mit Daten der **AAPM Low-Dose CT 
Challenge 2016** konzipiert. Die Challenge-Daten werden **NICHT** mit 
diesem Repository verteilt.

### Registrierung und Datenzugang

1. Besuchen Sie die Challenge-Website: https://www.aapm.org/grandchallenge/lowdosect/
2. Registrieren Sie sich für ein Konto
3. Akzeptieren Sie die Nutzungsbedingungen (Data Use Agreement)
4. Laden Sie die Daten herunter

### Pflichtzitate

Wenn Sie die AAPM-Daten in Ihrer Forschung verwenden, zitieren Sie bitte:

> The AAPM TG-201 supplementary data on low-dose CT
> 
> "Low-dose CT: The phantom database testing a proton therapy treatment planning system"
> - AAPM Task Group 201

Bitte beachten Sie auch die offiziellen Zitierhinweise auf der Challenge-Website.

### Keine Datenweitergabe

**WICHTIG:** Dieses Repository enthält **KEINE** Patientendaten. Die 
AAPM-Daten dürfen aufgrund des Data Use Agreements nicht weitergegeben werden.

Dieses Projekt bietet stattdessen:
- Ein synthetisches Demo-Phantom für Tests
- Werkzeuge zum Laden eigener (lizenzierter) DICOM-Daten
- Unterstützung für selbst heruntergeladene AAPM-Daten

### Eigene DICOM-Daten

Sie können Ihre eigenen DICOM-Daten verwenden:
1. Laden Sie eine DICOM-Serie in die App
2. Die App erwartet DICOM-Dateien mit gültigen HU-Werten (RescaleSlope/Intercept)
```

#### 2. `CITATION.cff` erstellen
```yaml
cff-version: "1.2.0"
title: "CT-Viewer"
message: "If you use this software, please cite it as below."
authors:
  - name: "CT-Viewer Project"
    email: "contact@example.com"
version: "1.0.0"
date-released: "2026-10-14"
license: "MIT"

preferred-citation:
  type: article
  title: "CT-Viewer: A visualization tool for CT orientation"
  authors:
    - name: "CT-Viewer Project"
  journal: "SoftwareX"
  year: 2026

references:
  - type: book
    title: "Low-dose CT: The phantom database testing a proton therapy treatment planning system"
    journal: "AAPM Task Group 201 Report"
    year: 2016
    url: "https://www.aapm.org/grandchallenge/lowdosect/"
```

#### 3. `configs/datasets/aapm_ldct2016.yaml` erstellen
```yaml
# AAPM LDCT Challenge 2016 Dataset Configuration
# This config documents the expected data format, NOT the data itself

dataset:
  name: "AAPM Low-Dose CT Challenge 2016"
  description: |
    The AAPM Low-Dose CT Challenge provides CT scans with varying dose levels
    for research in low-dose CT reconstruction and analysis.
  
  official_url: "https://www.aapm.org/grandchallenge/lowdosect/"
  
  registration: |
    1. Register at the challenge website
    2. Accept the Data Use Agreement
    3. Download the data packages
    
  citation: |
    AAPM Task Group 201. "Low-dose CT: The phantom database testing 
    a proton therapy treatment planning system." 2016.
    
  data_use_agreement: |
    The data is provided for research purposes only. Redistribution or
    commercial use is prohibited. See the official DUA for details.

# Expected data format when using aapm_to_npy.py
format:
  extension: ".npy"
  dtype: "int16"  # Raw HU values
  axes: "(z, y, x)"  # Slice-first ordering
  
hu_values:
  air: -1000
  water: 0
  bone: ~800
  
spacing:
  # Typical AAPM spacing values
  axial: "2.5 - 5.0 mm"
  in_plane: "0.6 - 1.0 mm"

# Note: This file does NOT contain actual data
# It is a configuration/placeholder for documentation purposes
```

---

## Zusammenfassung Day 01

### Erstellte Dateien
| Datei | Aktion |
|-------|--------|
| `LICENSE` | Create |
| `NOTICE` | Create |
| `SECURITY.md` | Create |
| `docs/data.md` | Create |
| `CITATION.cff` | Create |
| `configs/datasets/aapm_ldct2016.yaml` | Create |
| `.gitignore` | Update (erweitern) |
| `.dockerignore` | Create |
| `Dockerfile` | Update (Build Guard hinzufügen) |
| `.github/workflows/ci.yml` | Create |

### Git Commands
```bash
# Nach Änderungen
git add LICENSE NOTICE SECURITY.md docs/data.md CITATION.cff
git add configs/datasets/aapm_ldct2016.yaml
git add .gitignore .dockerignore
git add .github/workflows/ci.yml
git commit -m "Phase 0: Add license files and data guards (T01-T04)"
```

### Nächste Schritte (Day 02)
- T-10: Volume-Dataclass
- T-13: Windowing
- T-11: DICOM-Loader
