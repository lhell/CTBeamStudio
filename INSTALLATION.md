# Installation Guide

This guide covers all installation options for CTBeamStudio.

## Which option should I choose?

**Recommendation: the conda env from `environment.yml` (Option 3a).** It is the
only route that is validated end to end here: Python 3.11, conda-forge's
`parallelproj` 1.x with CPU kernels, working forward projection, and the full
suite green (387 passed, 0 skipped). Forward projection is the point of this
tool, so a pip-only install gives you most of the UI but not its core feature.

| Situation | Pick |
|---|---|
| Developing this repo, or need working forward projection | **Option 3a** (Miniforge + `environment.yml`) |
| Want a GPU | [GPU setup](#gpu-setup-nvidia-read-before-you-start) below — GPU projection is **not** in the tested baseline yet; use the CPU env for a green suite |
| No Python tooling, just want to look at the app | Option 1, Docker `full` (`slim` is viewer-only) |
| Viewer only, no projection | Option 2, pip/venv |

If you do not have conda yet, install Miniforge (Option 3a) rather than
Miniconda: it defaults to conda-forge, which is where `parallelproj` lives, and
it works on networks where `repo.anaconda.com` is unreachable. Docker is a
good delivery format, but it is not required on the machine running the app
if you can build with conda directly.

> **Working on this repo? Use the conda env.** All development commands — the
> app, the test suite, and the lint tools — run inside the conda env `ct-viewer`.
> See [AGENTS.md](AGENTS.md) for the agent-facing rules and
> [docs/local-environment.md](docs/local-environment.md) for this workstation's
> exact paths. The pip/venv option below is for running the viewer only; it
> cannot run the parallelproj forward projection or the full test suite.

## Prerequisites

- **Python 3.11 for the validated conda env.** The pinned `parallelproj` 1.x
  builds provide Python bindings for 3.11. Python 3.12+ is fine for the pip
  viewer-only route and for `parallelproj` 2.x, but 2.x needs a different
  library generation (`parallelproj-core`/`libparallelproj` 2.0.x) and is not
  the tested baseline — see
  [GPU setup](#gpu-setup-nvidia-read-before-you-start).
- **Operating System**: Windows 10/11, macOS, or Linux
- **Minimum 8GB RAM** (16GB+ recommended for large CT datasets)
- **NVIDIA driver** — only for the optional GPU variant; check with `nvidia-smi`

## Quick Start

### Option 1: Docker (Recommended for quick setup)

> Release tagging and registry conventions: see [docs/versioning.md](docs/versioning.md).
> Handing the image to someone who does not develop this project? Use
> [docs/customer-docker-guide.md](docs/customer-docker-guide.md) instead — it
> covers loading the image, mounting data, and troubleshooting without any
> Python or conda.

The Dockerfile has two targets:

| Target | Contains | Projection | Size |
|---|---|---|---|
| `slim` | viewer only | returns zeros + warning | ~1.43 GB |
| `full` | + parallelproj + torch (CPU) | works | ~3.05 GB |

```bash
# Full image — this is the one that can forward-project
docker build -t ctbeamstudio:full --target full .

# Mount your DICOM folder; the app reads it from the container path /data
docker run -p 8501:8501 -v C:\data\ct:/data:ro ctbeamstudio:full
```

Open http://localhost:8501 in your browser, then enter `/data/<your-study>` in
the sidebar's **DICOM Folder** field.

The `full` target installs conda-forge's `parallelproj` via micromamba **inside
the image**. Nothing has to be installed on the host, and conda is not required
on the machine that runs the container — it is build-time machinery only.

Plain `docker build -t ctbeamstudio:slim --target slim .` builds `slim`, the
viewer-only image (no projection; ~1.43 GB — the viewer dependency set is the
bulk, see the Dockerfile header).

---

### Option 2: pip (Local installation)

```bash
# Clone the repository
git clone https://github.com/lhell/CTOrientationViewer.git
cd CTOrientationViewer

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# or: source venv/bin/activate  # Linux/Mac

# Install in development mode
pip install -e .

# Run the app
streamlit run src/visualization/app.py
```

---

### Option 3: Conda (Required for parallelproj forward projection)

parallelproj is **not available on PyPI** — it ships compiled kernels and must
be installed from conda-forge. Without it the app still runs, but
"Run Forward Projection" returns all zeros and shows a warning.

> **Start with the CPU env.** `environment.yml` pins Python 3.11,
> `parallelproj`/`libparallelproj` 1.x CPU builds and CPU PyTorch. That is the
> combination the test suite is validated on (387 passed, 0 skipped). If you
> have an NVIDIA GPU, read [GPU setup](#gpu-setup-nvidia-read-before-you-start)
> *before* running an unpinned `conda install ... pytorch cuda-toolkit`: the
> solver can bump Python to 3.12 and install `parallelproj` 2.x instead, which
> is a different, untested dependency combination here.

#### Option 3a: Miniforge (recommended — conda-forge by default)

[Miniforge](https://github.com/conda-forge/miniforge) is a minimal conda
distribution hosted on GitHub that defaults to the conda-forge channel. Prefer
it over Miniconda if `repo.anaconda.com` is unreachable on your network.

```bash
# 1. Download the installer for your platform from
#    https://github.com/conda-forge/miniforge/releases/latest
#    (Windows: Miniforge3-Windows-x86_64.exe)

# 2. Windows silent install, no PATH changes:
#    Miniforge3-Windows-x86_64.exe /InstallationType=JustMe /RegisterPython=0 /AddToPath=0 /S
#    Linux/macOS:
bash Miniforge3-Linux-x86_64.sh -b -p "$HOME/miniforge3"

# 3. Create the environment (CPU-only parallelproj)
#    Installs the app with the dev extra, which includes nibabel, so the whole
#    suite runs with zero skips.
conda env create -f environment.yml
conda activate ct-viewer

# 4. Run the app
streamlit run src/visualization/app.py

# 5. Run the tests — must report "0 skipped"
python -m pytest -q -rs
```

#### Option 3b: Using environment.yml with Miniconda

```bash
# Install Miniconda if not present:
# https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe

# Create environment from yml
conda env create -f environment.yml
conda activate ct-viewer
```

#### Option 3c: Manual conda install

Run the `pip install` from the **repository root** (the directory containing
`pyproject.toml`), not from its parent:

```bash
conda create -n ct-viewer python=3.11 -y
conda activate ct-viewer

# CPU-only (no NVIDIA GPU). The py311 build string is essential: plain
# "parallelproj" can resolve to a C-library-only build that has no Python
# module at all. PyTorch is required by the projection backend, not optional.
conda install -c conda-forge \
  "parallelproj=1.3.*=*py311*" "libparallelproj=1.3.*=*cpu*" "pytorch=*=cpu*" -y

# Install the app and remaining dependencies with pip
pip install -e ".[dev]"

# Run the app
streamlit run src/visualization/app.py
```

#### GPU setup (NVIDIA): read before you start

`environment.yml` is deliberately CPU-only. On a GPU machine, build a fresh
env instead of layering GPU packages onto the CPU one:

1. Confirm the driver: `nvidia-smi`. The CUDA version shown there is the
   driver's maximum supported toolkit version, not the version to install.
2. Keep **Python 3.11** in the solve — do not let a GPU PyTorch build pull 3.12.
3. Pick a **matched pair**: the same `parallelproj`/`libparallelproj` version
   and the same CUDA build. `conda search -c conda-forge "parallelproj=1.3.*"`
   lists the options; for example `parallelproj=1.3.5=cuda112_py311*` goes with
   `libparallelproj=1.3.5=cuda112*`. Do not mix a 1.x wrapper with a 2.0.x
   library, and CUDA 11 vs CUDA 13 builds are not interchangeable.
4. Install Python, the matched pair, PyTorch and the toolkit in **one** solve,
   then the app from the repo root:

   ```bash
   conda create -n ct-viewer python=3.11 -y
   conda activate ct-viewer
   conda install -c conda-forge python=3.11 \
     "parallelproj=1.3.5=cuda112_py311*" "libparallelproj=1.3.5=cuda112*" \
     pytorch cuda-toolkit -y
   pip install -e ".[dev]"
   ```

   Adjust the CUDA build to your driver/GPU; the example above is a known
   build combination, not a universal pin. Check the result with
   `conda list parallelproj libparallelproj pytorch` before moving on.
5. Verify the API the app actually imports (see [Verification](#verification)):
   `python -c "from parallelproj.projectors import ListmodePETProjector"`.

Three install traps seen in a real GPU setup:

- Letting the solver upgrade to Python 3.12 and `parallelproj` 2.0.x. That is a
  valid upstream combination, but it leaves the validated 1.x baseline and
  changes the diagnostic API (see [Verification](#verification)). Pin
  `python=3.11` to stay on the tested path.
- Installing `parallelproj=1.3.2=cuda11.1h1234567*`: those builds contain only
  C libraries and headers, so `import parallelproj` fails with
  `ModuleNotFoundError`. Use a `*_py311*` build.
- Installing a modern `libparallelproj` (e.g. 2.0.7/cuda130) next to an old
  `parallelproj` wrapper. The library and wrapper versions must match.

> **Known limitation:** the GPU route is not supported yet. Two independent
> failures were reproduced on 8× RTX A6000 (2026-11-19, 19 failed / 340 passed):
> (1) the projector calls `np.asarray` on CUDA LOR tensors → `TypeError: can't
> convert cuda:0 device type tensor to numpy` (audit finding #1); (2) a
> **GPU-built** parallelproj operator cannot run CPU input — with
> `CUDA_VISIBLE_DEVICES=""` the suite got worse (23 failed / 336 passed) with
> `RuntimeError: cudaSetDevice failed: no CUDA-capable device is detected`.
> Unticking **Use CUDA if available** is therefore **not** a reliable fallback
> in a GPU-built env. Only the CPU env from `environment.yml` is validated
> (388 passed, 0 skipped). Planned fix: **T-08-01**,
> `docs/superpowers/plans/2026-11-19-gpu-forward-projection.md`; the reproduced
> errors are recorded in
> `docs/superpowers/specs/2026-11-19-gpu-forward-projection-design.md`.

### CUDA in the test suite and helper scripts

CUDA is **not** enabled or validated by the tests:

- `tests/unit/test_parallelproj.py` and `tests/integration/test_projection_workflow.py`
  pass `use_cuda=False` explicitly. Other tests (most of
  `tests/unit/test_forward_project.py` and `test_dummy_measurement.py`) call
  `forward_project(...)` with its default `use_cuda=True`. On a GPU machine
  those take the CUDA path and hit the bug above — that is the source of the
  19 failures. There is no `conftest.py` fixture or environment variable that
  forces CPU, so the green 388/0 result only applies to the CPU env.
- `scripts/verify_forward_projection.py` and `scripts/forward_projection_plot.py`
  both hard-code `use_cuda=False`, so they check the CPU path. In a GPU-built
  parallelproj env that path can still fail with `cudaSetDevice`; use them in
  the CPU env from `environment.yml` for a meaningful check (T-08-01 adds an
  optional `--cuda` flag).
- In the app, **Use CUDA if available (forward projection only)** is ticked by
  default. Unticking it avoids the projector crash but does not fix a GPU-only
  parallelproj build — see the known limitation above.

---

#### Desktop shortcut (Windows)

`scripts\install_desktop_shortcut.ps1` installs the "double-click and it runs"
setup for the conda env:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_desktop_shortcut.ps1
```

It creates `CTBeamStudio.lnk` on your desktop, pointing at `run_app.cmd` with
`--server.headless false`, so a double-click activates `ct-viewer`, starts the
server on port 8501 and opens `http://localhost:8501` in your default browser.
It also writes `%USERPROFILE%\.streamlit\credentials.toml` if that file is
missing: with `headless = false` Streamlit otherwise stops at its first-run
email prompt, which reads stdin and never lets the server bind the port.

Use `-Name <shortcut name>` and `-RepoPath <repo root>` if the defaults (repo
root = parent of the script, name = `CTBeamStudio`) do not fit.

---

## Verification

### Verify parallelproj

Check the submodule this app imports, not just the top-level package: the
C-library-only builds do not provide a usable Python package at all.

```bash
python -c "import parallelproj, torch; from parallelproj.projectors import ListmodePETProjector; print('parallelproj OK'); print('CUDA available:', torch.cuda.is_available())"
```

On a working parallelproj **1.x** build these extra diagnostics also exist:

```python
print(parallelproj.cuda_present)              # False = CPU-only build
print(parallelproj.lib_parallelproj_c_fname)  # parallelproj_c.dll (Win) / .so (Linux)
```

Notes on API names:
- `parallelproj` has no `__version__` attribute; use
  `importlib.metadata.version("parallelproj")`.
- In 1.x there is no `parallelproj_core` Python module either. The two
  diagnostics above (`cuda_present`, `lib_parallelproj_c_fname`) are
  **1.x-only**; 2.0.x removed both (it depends on a separate
  `parallelproj-core` package instead).
- `parallelproj.projectors.ListmodePETProjector` exists in both 1.x and 2.x;
  the version choice matters for the Python version, the matching library and
  which diagnostics are available.
- `torch.cuda.is_available()` is what this app uses to decide whether to
  request CUDA, so check that — not `parallelproj.cuda_present`.

### Verify installation

```bash
# Should show no errors
python -c "import streamlit; import pydicom; import plotly; print('OK')"
```

For a source checkout, the full check is `python -m pytest -q -rs` from the
activated env: expect zero skips (387 passed on the CPU env).

---

## Troubleshooting

### "conda not found"
- Install [Miniforge](https://github.com/conda-forge/miniforge/releases/latest) (recommended) or [Miniconda](https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe)

### "repo.anaconda.com" unreachable / Miniconda download fails
Some networks resolve `repo.anaconda.com` to IPv6 addresses that do not
connect, while `conda.anaconda.org` and GitHub work fine. Use Miniforge from
GitHub instead — it is conda-compatible and defaults to conda-forge.

### "parallelproj is not installed in this environment"
The app is running on a plain pip/venv interpreter. parallelproj only exists on
conda-forge, so create and activate the `ct-viewer` env (Option 3) and start
Streamlit from it:
```bash
conda activate ct-viewer
python -c "from parallelproj.projectors import ListmodePETProjector; print('OK')"
streamlit run src/visualization/app.py
```

### `import parallelproj` fails although conda lists it
Check the build string: `conda list parallelproj libparallelproj`. Builds such
as `1.3.2=cuda11.1h1234567*` ship C libs only and have no Python module. Rebuild
the env with a `*_py311*` build of `parallelproj` 1.x and a matching
`libparallelproj` (see [Option 3c](#option-3c-manual-conda-install)). Also make
sure you are in the activated env — a bare interpreter will not see it.

### `AttributeError: module 'parallelproj' has no attribute 'cuda_present'`
The solver installed `parallelproj` 2.x (it requires Python 3.12). The
`projectors` submodule it still provides, but `cuda_present` and
`lib_parallelproj_c_fname` are gone; use `torch.cuda.is_available()` instead.
For the validated 1.x baseline, recreate the env on Python 3.11 with
`parallelproj=1.3.*=*py311*` instead of upgrading Python to make 2.x install.

### `ModuleNotFoundError: No module named 'parallelproj.projectors'`
The Python bindings are missing — most likely a C-library-only `parallelproj`
build (see above). `parallelproj` 2.x does provide `projectors`, so this is not
a version-2 symptom.

### `TypeError: can't convert cuda:0 device type tensor to numpy`
Forward projection on a GPU env hits the known bug in
`docs/audit-2026-11-13-findings.md` (finding 1). Two options today: use the
validated CPU env from `environment.yml`, or untick **Use CUDA if available**
and install a CPU-capable `libparallelproj` in that env. Unticking alone is not
enough with a GPU-only parallelproj build.

### `RuntimeError: cudaSetDevice failed: no CUDA-capable device is detected`
The installed `libparallelproj` is a GPU-only build and cannot run CPU input —
even with `CUDA_VISIBLE_DEVICES=""`. Rebuild the env with CPU kernels
(`environment.yml`) or wait for T-08-01, which makes the device handling and
the unsupported combination explicit.

### `pip install -e ./CTBeamStudio[dev]` says "does not appear to be a Python project"
`pyproject.toml` lives in the repository root. Run `cd CTBeamStudio` (or
`cd CTOrientationViewer`, depending on the clone name) before pip install;
the parent folder has no project metadata.

### `curl: (23) Failure writing output to destination` downloading Miniforge
The chosen temp directory is not writable. Download the installer into a
user-writable path such as `$HOME` and run it from there.

### CUDA not detected
- Ensure NVIDIA GPU drivers are installed
- Run `nvidia-smi` to verify
- Confirm the `parallelproj`/`libparallelproj` CUDA builds match (above)

### CPU-only mode for parallelproj
```bash
conda install -c conda-forge \
  "parallelproj=1.3.*=*py311*" "libparallelproj=1.3.*=*cpu*" "pytorch=*=cpu*"
```

### Port 8501 already in use
- Change port: `streamlit run src/visualization/app.py --server.port 8502`
- Or find and kill the process: `netstat -ano | findstr :8501`

### Import errors on Windows
- Install Visual C++ Redistributable
- Ensure path lengths are not too long (use `\\?\` prefix or move project to shorter path)

### Memory issues with large datasets
- Close other applications
- Reduce slice selection in sidebar
- Consider using 64-bit Python

---

## Optional Dependencies

Extras are pip's optional dependency groups from `pyproject.toml`, installed with
the `[extra]` suffix. Only two exist:

| Extra | Contains | Use for |
|---|---|---|
| `dev` | pytest, pytest-cov, flake8, black, isort, mypy, **nibabel** | running the tests and the lint tools |
| `nifti` | nibabel | loading `.nii`/`.nii.gz` sinograms at runtime only |

`dev` includes nibabel on purpose: the suite covers NIfTI loading, and without
nibabel those tests skip instead of running.

```bash
pip install -e ".[dev]"     # tests + lint (includes nibabel)
pip install -e ".[nifti]"   # runtime NIfTI support, no test tooling
```

There is deliberately **no** `cpu`/`gpu` extra — parallelproj cannot be installed
from PyPI (see below).

### For Forward Projection (parallelproj + PyTorch)

There is **no pip extra for this**, and there cannot be: `parallelproj` ships
compiled kernels and is published only on conda-forge. There is no `.[cpu]` or
`.[gpu]` extra — naming a non-existent extra makes pip install the base package
without any warning, so it looks like it worked. Use conda:

**CPU-only (no GPU required):**
```bash
conda activate ct-viewer
conda install -c conda-forge \
  "parallelproj=1.3.*=*py311*" "libparallelproj=1.3.*=*cpu*" "pytorch=*=cpu*"
```

**GPU (CUDA):** do not use a bare `conda install parallelproj pytorch
cuda-toolkit` — it can resolve to Python 3.12 / `parallelproj` 2.x, which is
outside the validated baseline. Follow
[GPU setup](#gpu-setup-nvidia-read-before-you-start) and pin a matched pair of
builds.

If the env was created from `environment.yml`, both are already installed and
there is nothing to do. PyTorch alone can also come from pip, but
`parallelproj` still has to come from conda, in that same environment:

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
conda install -c conda-forge \
  "parallelproj=1.3.*=*py311*" "libparallelproj=1.3.*=*cpu*"
```

**Verify installation** with the `from parallelproj.projectors import ...`
command in [Verification](#verification); a successful top-level import alone
does not prove the app can project.

### For documentation

```bash
pip install mkdocs
```

---

## Running Without Installation

You can run Streamlit directly without installing:

```bash
# Clone and navigate
git clone https://github.com/lhell/CTOrientationViewer.git
cd CTOrientationViewer

# Run without installing
python -m streamlit run src/visualization/app.py
```

Note: You'll need all dependencies installed in your environment.

---

## Docker Options

### With volume mount for local data

```bash
docker run -p 8501:8501 -v C:\data\ct:/data:ro ctbeamstudio:full
```

The container never writes to the mounted folder. The sidebar path field expects
the container path (`/data/...`), not the host path.

### Build with custom tag

```bash
docker build -t ctbeamstudio:full --target full .
docker build -t ctbeamstudio:1.0.0 --target full .
```

### Hand the image to a non-developer

```bash
docker save ctbeamstudio:1.0.0 -o ctbeamstudio-1.0.0-full.tar   # on your machine
docker load -i ctbeamstudio-1.0.0-full.tar                     # on the target machine
```

Full instructions: [docs/customer-docker-guide.md](docs/customer-docker-guide.md).

### Check container logs

```bash
docker logs ctbeamstudio
```

---

## System Requirements Details

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 8 GB | 16 GB |
| Storage | 2 GB | 10 GB |
| CPU | 4 cores | 8+ cores |
| GPU | Optional | NVIDIA 8GB+ VRAM |

### Windows-Specific

- Windows 10 version 1903+ or Windows 11
- WebView2 runtime (usually pre-installed)
- .NET Framework 4.7.2+ (for pywebview if desktop wrapper used)

### macOS-Specific

- macOS 10.15+
- Xcode command line tools: `xcode-select --install`

### Linux-Specific

- GTK3 or Qt5 for pywebview
- WebKitGTK for web-based features
