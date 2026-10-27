# CT-Viewer

A web-based visualization tool for CT orientation and 3D volume rendering, designed for medical imaging research.

## Features

- **DICOM Loading** — Read CT scans from DICOM files (`.dcm`, `.ima`)
- **3D Volume Visualization** — Interactive 3D view with source and detector positioning (parallelproj: Z-axis rotation)
- **Multi-Planar Reconstruction (MPR)** — Axial, coronal, and sagittal slices
- **Windowing** — Presets for lung, abdomen, bone, and brain imaging
- **HU Values** — Native Hounsfield Unit handling
- **Demo Phantom** — Built-in synthetic phantom for testing without real patient data

## Supported Data

- **AAPM Low-Dose CT Challenge 2016** — [Download data here](https://aapm.app.box.com/s/eaw4jddb53keg1bptavvvd1sf4x3pe9h/folder/144226105715) 
- **Generic DICOM** — Any CT dataset with valid HU values
- **NumPy** — `.npy` files with shape `(z, y, x)` and `int16` dtype

> **Note:** This project does NOT distribute patient data. Users must register separately for the AAPM challenge and use their own licensed data.

> **⚠️ Disclaimer:** This software is intended for **research and educational purposes only**. It is **not** a medical device and has not been reviewed or approved by the FDA, CE, or any regulatory body. Do not use this software for clinical diagnosis, treatment decisions, or any purpose that could affect patient care.

## Installation

### Option 1: Docker (Recommended)

```bash
docker build -t ct-viewer .
docker run -p 8501:8501 ct-viewer
```

### Option 2: Local with pip

```bash
# Clone the repository
git clone https://github.com/your-org/CTOrientationViewer.git
cd CTOrientationViewer

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -e .

# Run the app
streamlit run src/visualization/app.py
```

### Option 3: Local with Conda (for parallelproj GPU support)

**parallelproj requires conda-forge** for the compiled GPU backend. This option is required for forward projection features.

```bash
# Clone the repository
git clone https://github.com/your-org/CTOrientationViewer.git
cd CTOrientationViewer

# --- Option 3a: Using environment.yml (recommended) ---

# Install Miniconda if not present:
# https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe

# Create environment from yml
conda env create -f environment.yml
conda activate ct-viewer

# Install parallelproj with GPU (from conda-forge)
conda install -c conda-forge parallelproj pytorch cuda-toolkit -y

# --- Option 3b: Manual conda install ---

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

#### Verify parallelproj GPU support

```python
import parallelproj
print(parallelproj.__version__)

import parallelproj_core
print(parallelproj_core.cuda_enabled)  # 1 = GPU, 0 = CPU
```

#### Troubleshooting

- **"conda not found"**: Install [Miniconda](https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe)
- **CUDA not detected**: Ensure NVIDIA GPU drivers are installed
- **CPU-only mode**: `conda install -c conda-forge parallelproj "libparallelproj=*=cpu*"`

## Usage

1. **Start the app:** `streamlit run app.py`
2. **Load data:**
   - Use the folder picker to select a DICOM series
   - Or start without data to use the demo phantom
3. **Navigate:** Use the slider to scroll through slices
4. **Adjust window:** Select presets (lung, abdomen, bone) or set custom center/width
5. **3D View:** Switch to 3D mode for volume visualization with source/detector

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Third-Party Licenses

See [NOTICE](NOTICE) for information about third-party components.

## Security

See [SECURITY.md](SECURITY.md) for our security policy and best practices.

## Citation

If you use this software in your research, please cite:

> CT-Viewer: A visualization tool for CT orientation. 2026.

If you use AAPM Challenge data, please also cite the original challenge.
