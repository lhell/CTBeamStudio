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

## pyproject.toml

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

## Import in Tests

```python
from visualization.volume import Volume  # NICHT: from src.visualization...
```

## Warum?

- pythonpath = ["src"] fügt `src/` zum Python-Path hinzu
- `from visualization import X` findet `src/visualization/`
- Wenn pytest `tests/visualization` lädt, gibt es Konflikt
