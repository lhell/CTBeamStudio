# Linting Guide

## Vor jedem Commit ausführen:

```bash
# Formatierung
python -m black .
python -m isort .

# Linting
python -m flake8 . --ignore=F841
```

## CI/CD Checks (GitHub Actions)

Siehe `.github/workflows/ci.yml` (falls vorhanden).

## Hinweise

- `flake8 --ignore=F841` ignoriert ungenutzte Variablen (placeholder Variablen in T-63)
- `black` formatiert Code automatisch auf Zeilenlänge 88
- `isort` sortiert Imports alphabetisch
