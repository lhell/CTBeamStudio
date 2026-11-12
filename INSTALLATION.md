# Installation Guide

This guide covers all installation options for CTBeamStudio.

> **Working on this repo? Use the conda env.** All development commands — the
> app, the test suite, and the lint tools — run inside the conda env `ct-viewer`.
> See [AGENTS.md](AGENTS.md) for the agent-facing rules and
> [docs/local-environment.md](docs/local-environment.md) for this workstation's
> exact paths. The pip/venv option below is for running the viewer only; it
> cannot run the parallelproj forward projection or the full test suite.

## Prerequisites

- **Python 3.11+** (3.12 recommended for best compatibility)
- **Operating System**: Windows 10/11, macOS, or Linux
- **Minimum 8GB RAM** (16GB+ recommended for large CT datasets)

## Quick Start

### Option 1: Docker (Recommended for quick setup)

> Release tagging and registry conventions: see [docs/versioning.md](docs/versioning.md).

```bash
# Build the image
docker build -t ct-viewer .

# Run the container
docker run -p 8501:8501 ct-viewer
```

Open http://localhost:8501 in your browser.

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

```bash
conda create -n ct-viewer python=3.11 -y
conda activate ct-viewer

# CPU-only (no NVIDIA GPU)
conda install -c conda-forge parallelproj "libparallelproj=*=cpu*" -y

# Or with GPU support (NVIDIA GPU + drivers required)
# conda install -c conda-forge parallelproj pytorch cuda-toolkit -y

# Install the app and remaining dependencies with pip
pip install -e ".[dev]"

# Run the app
streamlit run src/visualization/app.py
```

---

## Verification

### Verify parallelproj GPU support

```python
import parallelproj  # prints the C-lib path and CUDA status on import
print(parallelproj.cuda_present)          # False = CPU-only build
print(parallelproj.lib_parallelproj_c_fname)  # path to parallelproj_c.dll
```

Two corrections to the API names people commonly guess:
- `parallelproj` has **no** `__version__` attribute (`AttributeError`); use
  `importlib.metadata.version("parallelproj")`.
- There is **no** `parallelproj_core` module; the CUDA flag is
  `parallelproj.cuda_present`.

### Verify installation

```bash
# Should show no errors
python -c "import streamlit; import pydicom; import plotly; print('OK')"
```

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
python -c "import parallelproj; print(parallelproj.cuda_present)"
streamlit run src/visualization/app.py
```

### CUDA not detected
- Ensure NVIDIA GPU drivers are installed
- Run `nvidia-smi` to verify

### CPU-only mode for parallelproj
```bash
conda install -c conda-forge parallelproj "libparallelproj=*=cpu*"
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
conda install -c conda-forge parallelproj "libparallelproj=*=cpu*" "pytorch=*=cpu*"
```

**GPU (CUDA):**
```bash
conda activate ct-viewer
conda install -c conda-forge parallelproj pytorch cuda-toolkit
```

If the env was created from `environment.yml`, both are already installed and
there is nothing to do. PyTorch alone can also come from pip (below), but
`parallelproj` still has to come from conda, in that same environment:

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
conda install -c conda-forge parallelproj "libparallelproj=*=cpu*"
```

**Verify installation:**
```python
import parallelproj
import torch
print(f"CUDA available: {torch.cuda.is_available()}")
print(parallelproj)  # prints the C-lib and CUDA status on import
```

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
docker run -p 8501:8501 -v C:\data\ct:/data ct-viewer
```

### Build with custom tag

```bash
docker build -t ct-viewer:1.0.0 .
```

### Check container logs

```bash
docker logs ct-viewer
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
