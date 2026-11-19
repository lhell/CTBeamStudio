# CTBeamStudio — Agent Instructions

Streamlit CT viewer with forward-projection comparison (repo dir: CTOrientationViewer).

## Architecture
- `src/backend/` — numbers and data: `Volume`, `ProjectionGeometry`,
  `forward_project`, `attenuation`, `loaders/` (dicom, npy, projection, sinogram).
- `src/visualization/` — Streamlit UI only. Dependency is one-way:
  visualization → backend, never the reverse (ledger D-9).
- `parallelproj` is an optional lazy import.
- Data is HU internally; display/windowing converts at the edge. Forward projection
  consumes attenuation in 1/mm (`src/backend/attenuation.py`).

## Before you start
- Read your task's entry in `docs/plan.md` (German; single source of truth;
  T-numbers, acceptance criteria, decision log).
- Check `docs/superpowers/specs/` and `docs/superpowers/plans/` for existing design
  docs on the area you touch.
- Check `docs/audit-2026-11-13-findings.md` for open audit findings before
  starting work on the area you touch; update an item's Status there when you
  fix it.

## Environments — the conda env is mandatory

**Every command that imports this project runs inside the conda env `ct-viewer`.**
Do not run project code, pytest, or the lint tools with a bare system interpreter.

| Command | Where it runs |
|---|---|
| pytest, streamlit, any `import backend.*` / `import visualization.*` | conda env `ct-viewer` |
| flake8, black, isort | conda env `ct-viewer` (installed via `.[dev]`) |

`.[dev]` is the only extra needed to run the suite: it includes `nibabel`, so the
NIfTI tests run instead of skipping. Never install a non-existent extra — pip
accepts `.[anything]` **without any warning** and silently installs nothing.

The env exists for one hard reason: `parallelproj` ships compiled kernels and is
only on conda-forge, and its `parallelproj_c.dll` lives in the env's `Library\bin`,
which is on `PATH` only in an **activated** conda shell. A bare interpreter fails
with `ImportError: Cannot find parallelproj c lib`.

Activate first — every command in this repo assumes it:

```powershell
# this machine (see docs/local-environment.md)
cmd /c "call C:\Users\hellwege\miniforge3\Scripts\activate.bat ct-viewer && python -m pytest -q -rs"
```

```bash
# POSIX / CI
conda activate ct-viewer
python -m pytest -q -rs
```

Create it from `environment.yml` (`conda env create -f environment.yml`), or use
`run_app.cmd`, which activates the env and warns if `parallelproj`/`torch` are
missing. Details: `docs/local-environment.md`, `INSTALLATION.md`.

## Commands
- App: `python -m streamlit run src/visualization/app.py --server.headless true --server.port 8501`
  (or simply `run_app.cmd`)
- Tests: `python -m pytest -q -rs` — the `-rs` flag is deliberate: it names any
  skip, so a skip is a visible decision rather than silent lost coverage.
- Lint (this exact order; canonical source `LINTING.md`):
  1. `python -m flake8 . --ignore=F841,E501,E402,F541,F401,W503,E203`
  2. `python -m black .`
  3. `python -m isort .`

## Hard rules
- **Never run project code or tests outside `ct-viewer`.** A system interpreter
  silently skips the parallelproj tests instead of running them.
- **A skipped test is a defect.** The suite must report zero skips, so every test
  actually runs. If a dependency is missing, install it into `ct-viewer` (or the
  declared extras in `environment.yml`) — do not leave the skip in place. Skip
  guards exist only for environments outside this repo's control (CI installing
  a subset).
- NEVER commit data files (`.dcm`, `.ima`, `.npy`, `.npz`, …): gitignored, and the CI
  data-guard fails on them. AAPM data is external with citation duties (`docs/data.md`).
- DICOM via `pydicom` only — no SimpleITK, no ITK (D-1).
- Streamlit pin: `>=1.37.0,<1.40.0` (`st.fragment` GA in 1.37; 1.40 removes
  `use_column_width`, ledger D-13).
- Do not add per-test `AppTest` runs (a starter is ~5+ s; history: T-81 reduced the
  suite 30 s → ~16-20 s by removing them). One module-scoped instance per test module.
- Backend code is Streamlit-free; keep it importable and testable without Streamlit.

## Test bar
- Baseline in `ct-viewer`: **398 passed, 0 skipped**, ~25–50 s depending on disk
  cache (T-92 + T-93 added 29 tests, T-94 to T-97 added 10, T-101 + T-102
  added 2, over the 301 baseline; 1 removed by dropping the correlation
  metric; 2 added for the scan z-offset; T-104 added 5; T-106 added 6
  (release-tag lockstep); T-108 added 1 (FP progress callback); T-110
  removed 10 and added 3 (in-canvas overlay toggle replaced by the
  3D-options checkbox); T-109 added 28 (14 queue, 12 actions, 2 UI smoke);
  T-01-01 added 1 (DICOM origin frame); T-08-02 added 2 (source z offset);
  T-11-01 added 4 (2 row-sinogram helpers, 2 UI smoke); T-08-01 added 4
  (device-boundary conversion, no skips)). The same 398 pass with zero skips
  on the 8× RTX A6000 GPU env, including with `CUDA_VISIBLE_DEVICES=""`. When
  your task changes the suite profile, update the numbers here as part of done.
- No `slow` marker and no default deselection exist: a plain `pytest` run is the
  whole suite.
- `tests/unit/test_release_push.py` shells out to `bash` (Git Bash on Windows). When
  that `bash` is not on `PATH`, those four tests fail with `FileNotFoundError`
  instead of running.
- `AppTest` cannot fire `run_every` fragments or interactive modebar toggles —
  verify those in the browser and say so in the ledger status (precedent: T-83).

## Conventions
- `docs/plan.md` is German and stays German; new ledger tasks use its format
  (Ziel / Dateien / Abhängig von / Akzeptanz / Status).
- Task numbers are permanent: never renumber or reorder them, because they appear
  in code, tests, CI and specs. New tasks are numbered `T-<phase>-<nn>` (two-digit
  `nn`, starting at `01` per phase — e.g. the next Phase 11 task is `T-11-01`);
  legacy `T-01`–`T-110` stay unchanged and unstructured `T-111+` is no longer
  issued. File each new task under the phase of its theme (not at the end of the
  file). See `plan.md` § "Phasen, Themen und Nummernkreise".
- New documentation is English.
- Specs: `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`.
  Plans: `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`.
- Workflow (brainstorm → spec → plan → implement) is handled by the superpowers
  plugin already active in sessions.

## Pointers
- `LINTING.md` — lint order, ignore set, known-acceptable findings
- `INSTALLATION.md` — setup details for all platforms
- `docs/local-environment.md` — this workstation's exact paths (Miniforge, env)
- `docs/data.md` — data access and citation rules
- `docs/geometry.md` — projection geometry definition
- `docs/plan.md` — task ledger, Zeitplan, decision log
