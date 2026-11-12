# Local environment (this machine)

Recorded 2026-11-11. Reference for this workstation only; CI is separate.

**This env is mandatory for all project work.** Every command that imports the
project — the app, `pytest`, and the lint tools — runs inside `ct-viewer`. Rules
live in [AGENTS.md](../AGENTS.md).

## Installed

| Item | Path / value |
|---|---|
| **Miniforge** | `C:\Users\hellwege\miniforge3` |
| conda | `C:\Users\hellwege\miniforge3\Scripts\conda.exe` |
| **ct-viewer env** | `C:\Users\hellwege\miniforge3\envs\ct-viewer` |
| env python | `...\envs\ct-viewer\python.exe` (Python 3.11.18) |
| parallelproj | conda-forge, **CPU-only** |
| parallelproj C lib | `...\envs\ct-viewer\Library\bin\parallelproj_c.dll` |
| pytorch | `cpu_mkl_py311` |
| Streamlit | 1.39.1 |
| **nibabel** | installed (via the `nifti` extra) — keeps the NIfTI tests from skipping |
| flake8 / black / isort | installed (via the `dev` extra) |

No NVIDIA GPU on this machine (`nvidia-smi` absent), so CUDA is unavailable and
`cuda_enabled` is `False` by design.

## Running anything (activate first)

```powershell
# Tests — expect "301 passed, 0 skipped"
cmd /c "call C:\Users\hellwege\miniforge3\Scripts\activate.bat ct-viewer && python -m pytest -q -rs"

# Lint (order matters: flake8, black, isort)
cmd /c "call C:\Users\hellwege\miniforge3\Scripts\activate.bat ct-viewer && python -m flake8 . --ignore=F841,E501,E402,F541,F401,W503,E203"
cmd /c "call C:\Users\hellwege\miniforge3\Scripts\activate.bat ct-viewer && python -m black ."
cmd /c "call C:\Users\hellwege\miniforge3\Scripts\activate.bat ct-viewer && python -m isort ."
```

`-rs` is not optional: it lists every skip, so a skip cannot disappear into the
summary. The suite must report zero skips.

## Why Miniforge instead of Miniconda

`repo.anaconda.com` is unreachable from this network (DNS returns IPv6-only
addresses that do not connect). `conda.anaconda.org` (packages) and GitHub are
reachable, so Miniforge — hosted on GitHub, conda-forge by default — installs
and works normally.

## Start the app

```powershell
C:\Users\hellwege\PycharmProjects\CTOrientationViewer\run_app.cmd
```

or manually:

```powershell
cmd /c "call C:\Users\hellwege\miniforge3\Scripts\activate.bat ct-viewer && streamlit run src\visualization\app.py"
```

`run_app.cmd` activates the env and warns if `parallelproj`/`torch` are missing.

## Gotcha: activating matters

`parallelproj_c.dll` lives in the env's `Library\bin`, which is only on `PATH`
inside an **activated** conda shell. Running
`...\envs\ct-viewer\python.exe` directly fails with:

```
ImportError: Cannot find parallelproj c lib. Consider setting the environment
variable PARALLELPROJ_C_LIB.
```

Always go through `activate.bat` (or `run_app.cmd`), not the bare interpreter.

## Recreate from scratch

```powershell
$env:USERPROFILE\miniforge3\Scripts\conda.exe env create -f environment.yml -y
```

`environment.yml` already pins CPU-only `parallelproj` + `libparallelproj` and
`pytorch=*=cpu*`, then pip-installs the app with dev extras.
