# Installation Guide

This guide covers all installation options for CTBeamStudio.

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

### Option 3: Conda (Required for parallelproj GPU support)

parallelproj requires conda-forge for the compiled GPU backend.

#### Option 3a: Using environment.yml (recommended)

```bash
# Install Miniconda if not present:
# https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe

# Create environment from yml
conda env create -f environment.yml
conda activate ct-viewer
```

#### Option 3b: Manual conda install

```bash
# Create new conda environment
conda create -n ct-viewer python=3.11 -y
conda activate ct-viewer

# Install parallelproj + PyTorch + CUDA from conda-forge
conda install -c conda-forge parallelproj pytorch cuda-toolkit -y

# Install remaining dependencies with pip
pip install streamlit pydicom numpy plotly pytest pyyaml scipy scikit-image array-api-compat

# Run the app
streamlit run src/visualization/app.py
```

---

## Verification

### Verify parallelproj GPU support

```python
import parallelproj
print(parallelproj.__version__)

import parallelproj_core
print(parallelproj_core.cuda_enabled)  # 1 = GPU, 0 = CPU
```

### Verify installation

```bash
# Should show no errors
python -c "import streamlit; import pydicom; import plotly; print('OK')"
```

---

## Troubleshooting

### "conda not found"
- Install [Miniconda](https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe)

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

### For development

```bash
pip install -e ".[dev]"
```

Includes: pytest, black, isort, flake8, mypy

### For Forward Projection (parallelproj + PyTorch)

**CPU-only (keine GPU erforderlich):**
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -e ".[cpu]"
```

**GPU (CUDA 12.1):**
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install -e ".[gpu]"
```

**Verify installation:**
```python
import parallelproj
import torch
print(f"parallelproj: {parallelproj.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
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
