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

For detailed installation instructions, see [INSTALLATION.md](INSTALLATION.md).

### Quick Start

**Docker (Recommended):**
```bash
docker build -t ct-viewer .
docker run -p 8501:8501 ct-viewer
```

**Local with pip:**
```bash
pip install -e .
streamlit run src/visualization/app.py
```

**Local with Conda (for GPU forward projection):**
```bash
conda env create -f environment.yml
conda activate ct-viewer
streamlit run src/visualization/app.py
```

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
