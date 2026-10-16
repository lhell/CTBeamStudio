# Testing Setup Hinweise

## Struktur

```
tests/
├── conftest.py           # pytest config mit sys.path setup
├── test_phantom.py       # Top-level tests
└── unit/                 # Unit-Tests (NICHT "visualization"!)
    ├── test_dicom_loader.py
    ├── test_volume.py
    └── test_windowing.py
```

## Wichtig

- **Niemals** Test-Ordner `tests/visualization` nennen!
- pytest behandelt `tests/X/` als Package `X`
- `tests/visualization` wird als `visualization.test_xxx` importiert
- → Konflikt mit `src/visualization`!

## conftest.py (KRITISCH!)

```python
"""Pytest configuration for tests."""

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

## Warum ist das noetig?

- pytest fuegt automatisch `tests/` zum Python-Path hinzu
- `tests/` an Position 0 shadowed alles andere!
- `from visualization import X` wuerde zuerst `tests/visualization/` suchen
- Loesung: `tests/` entfernen, `src/` an Position 0 einfuegen

## pyproject.toml

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
# pythonpath NICHT verwenden - wird von conftest.py behandelt
```

## Import in Tests

```python
from visualization.volume import Volume  # NICHT: from src.visualization...
```
