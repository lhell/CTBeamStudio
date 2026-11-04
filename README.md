# CTBeamStudio

A web-based tool for exploring CT scanner geometry and generating **simulated projections** from 3D volume data — for the purpose of comparing them against **measured** projections.

**Core utility:** load a CT volume together with a cone-beam projection geometry, forward-project the volume to produce *simulated* projections, and compare them directly against *measured* projection data. This simulated-vs-measured comparison (quantitative metrics plus side-by-side / difference visualization) is the central workflow of the tool — e.g. to validate scanner geometry parameters against real acquisitions.

## Features

### Core Workflow

- **DICOM Loading** — Read CT volumes from DICOM series (`.dcm`, `.ima`), plus NumPy volumes; the input to the forward-projection pipeline
- **Projection Geometry** — Define, load, and visualize cone-beam CT geometry (source/detector positions, distances `SDD`/`SID`, fan & cone angle, detector size/shape, offsets, and helical parameters). Geometry can be loaded from YAML or Mayo Clinic–style text files.
- **3D Geometry Visualization** — Interactive 3D view of the volume with the source path, detector, and full gantry trajectory overlaid, plus manual control of SID, gantry angle, and isocenter.

### Visualization & Data Handling

- **3D Volume Visualization** — Interactive iso-surface / PyVista volume rendering with source and detector positioning
- **Multi-Planar Reconstruction (MPR)** — Axial, coronal, and sagittal slices with isotropic resampling
- **Windowing** — Presets for lung, abdomen, bone, and brain imaging plus manual center/width control
- **HU Values** — Native Hounsfield Unit handling
- **Demo Phantom** — Built-in synthetic phantom for testing without real patient data

## Roadmap

Forward projection and simulated-vs-measured comparison are the long-term core utility of the tool. Parts are implemented in the backend; surfacing them in the app UI and the comparison workflow are planned next.

- **Forward Projection Engine** *(backend done, UI planned)* — Generate simulated projections from a 3D volume for a given geometry, using [parallelproj](https://github.com/gschramm/parallelproj)'s cone-beam ray tracing (Joseph 3D). Supports CUDA when available, and partial detector row/column/projection selection.
- **Simulated vs. Measured Comparison** *(planned)* — Compare forward-projected (simulated) projections against measured projection data with quantitative metrics (MAE, RMSE, SSIM, correlation) and side-by-side / difference visualization — the central utility of the tool for validating scanner geometry against real acquisitions.

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

> Forward projection and simulated-vs-measured comparison (the core utility) are on the roadmap — see [Roadmap](#roadmap) above.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Third-Party Licenses

See [NOTICE](NOTICE) for information about third-party components.

## Security

See [SECURITY.md](SECURITY.md) for our security policy and best practices.

## Citation

If you use this software in your research, please cite:

> CTBeamStudio: A visualization tool for CT orientation. 2026.

If you use AAPM Challenge data, please also cite the original challenge.
