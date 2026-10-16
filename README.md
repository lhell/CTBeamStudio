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

## Installation

### Option 1: Docker (Recommended)

```bash
docker build -t ct-viewer .
docker run -p 8501:8501 ct-viewer
```

### Option 2: Local

```bash
# Clone the repository
git clone https://github.com/your-org/CTOrientationViewer.git
cd CTOrientationViewer

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies (using pyproject.toml)
pip install -e .

# Run the app
streamlit run app.py
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
