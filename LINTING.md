# Linting Guide

This file is read by both humans and AI agents. **Follow the tool order below
exactly** — it matches the project's tooling and avoids reformat churn.

## Run order (MUST follow)

Run **inside the conda env `ct-viewer`**. Every tool below is installed there via
the `dev` extra, so there is one interpreter for lint and one for tests — no
system/conda split.

```powershell
cmd /c "call C:\Users\hellwege\miniforge3\Scripts\activate.bat ct-viewer && python -m flake8 . --ignore=F841,E501,E402,F541,F401,W503,E203 && python -m black . && python -m isort ."
```

> **Windows/UTF-8:** this repo contains emoji and `→` in source and tests. With the
> default cp1252 locale, `isort` prints `Unable to parse file ...` and **silently
> skips** those files, so a clean run can mean "not checked". Run it with UTF-8 so
> every file is really checked:
>
> ```powershell
> $env:PYTHONUTF8="1"; $env:PYTHONIOENCODING="utf-8"
> ```
>
> A correct run prints `Skipped 1 files` (that is `.git`) and no
> `Unable to parse` lines.

1. **flake8** — static lint check (reports issues; do not auto-fix)
2. **black** — auto-format (code style, line length 88)
3. **isort** — sort imports

Run on the files you changed (or `.` for the whole repo). Example:

```bash
# 1. Lint check (read-only) — use the project's ignore set
#    (repo ignores: E501, E402, F541, F401, F841, W503)
#    NOTE: E203 is black's slice-spacing style and is a known black/flake8
#    false positive — also ignore it.
python -m flake8 . --ignore=F841,E501,E402,F541,F401,W503,E203

# 2. Format
python -m black .

# 3. Sort imports
python -m isort .
```

## Why this order

- Run **flake8 first** so the unformatted file's real errors surface before
  black rewrites it.
- Run **black before isort** because black is the style authority for the
  project (line length 88). isort's `profile = "black"` is configured in
  `pyproject.toml` to stay consistent with it.
- black may reformat multi-line calls back onto fewer lines (it collapses to
  88 chars) — that is expected and correct.

## Tool availability

`flake8`, `black`, and `isort` are installed **inside the conda env `ct-viewer`**
(they come from the `dev` extra that `environment.yml` pip-installs). Use that env
for linting as well as for tests; do not reach for a separate system interpreter.

The env is mandatory because `parallelproj` only exists on conda-forge (see
`AGENTS.md`, `docs/local-environment.md`).
## Known flake8 findings (all acceptable)

| Code | Meaning | Why it's fine |
|------|---------|---------------|
| `E501` | line too long (>79) | Repo max line length is 88 (black config); ignored in pyproject |
| `E402` | module import not at top | `sys.path` setup in scripts / `importorskip` in tests |
| `F401` | imported but unused | Placeholder / re-exported names |
| `F841` | local var assigned, unused | Placeholder variables |
| `E203` | whitespace before `:` | black's slice syntax; false positive vs. black |

If flake8 reports anything *other* than the above (e.g. `F401` for a genuinely
dead import, undefined names, real logic errors), fix it.

## CI/CD Checks

See `.github/workflows/ci.yml` (if present).
