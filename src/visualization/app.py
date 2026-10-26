"""Streamlit app for CT Orientation Viewer."""

import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("app.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Add project root to path for imports
# Use resolve() to get absolute path
app_path = Path(__file__).resolve()
src_path = app_path.parent.parent  # src/visualization -> src -> project root
sys.path.insert(0, str(src_path.resolve()))  # Add src/ to path

# Debug: log where modules are loaded from
import visualization.mpr as _mpr

logging.getLogger(__name__).info("mpr loaded from %s", _mpr.__file__)

import numpy as np
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from visualization.loaders.dicom import load_dicom_series, scan_series
from visualization.mpr import extract_slice
from visualization.volume3d import (
    add_source_detector_figure,
    create_volume_figure,
    get_volume_center,
)
from visualization.windowing import WINDOW_PRESETS, apply_window


# Cache for loaded volumes (survives refresh within same server)
@st.cache_data(ttl=3600)
def load_volume_cached(file_paths_str: list, unit: str = None):
    """Load volume from file paths with caching."""
    from pathlib import Path

    files = [Path(p) for p in file_paths_str]
    return load_dicom_series(files, unit=unit)


# File to store last loaded paths for auto-load on refresh
CACHE_FILE = Path("data/.last_loaded.json")


def save_last_loaded(files: list):
    """Save last loaded file paths to cache file."""
    import json

    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {"files": [str(f) for f in files]}
    CACHE_FILE.write_text(json.dumps(data))


def load_last_loaded() -> list | None:
    """Load last saved file paths from cache file."""
    import json

    if not CACHE_FILE.exists():
        return None
    try:
        data = json.loads(CACHE_FILE.read_text())
        files = [Path(f) for f in data.get("files", [])]
        if files and all(f.exists() for f in files):
            return files
    except Exception:
        pass
    return None


def clear_last_loaded():
    """Clear the cache file."""
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()


def clamp_slice_state(key: str, max_idx: int) -> None:
    """Keep a slider's session-state value inside [0, max_idx]."""
    if key in st.session_state:
        st.session_state[key] = int(max(0, min(st.session_state[key], max_idx)))
    else:
        st.session_state[key] = max_idx // 2


def to_isotropic(img: np.ndarray, spacing: tuple[float, float]) -> np.ndarray:
    """Resample image to isotropic voxels based on spacing.

    Args:
        img: 2D numpy array (the slice)
        spacing: (row_spacing, col_spacing) in mm

    Returns:
        Resampled image with square pixels
    """
    from scipy.ndimage import zoom

    row_sp, col_sp = spacing
    if abs(row_sp - col_sp) < 1e-6:
        return img  # Already isotropic
    # Scale to make voxels square
    scale_factor = row_sp / col_sp
    return zoom(img, (scale_factor, 1.0), order=1)


def main():
    st.set_page_config(
        page_title="CT Orientation Viewer", page_icon="🏥", layout="wide"
    )

    # Sidebar: Title and Data selection
    st.sidebar.title("🏥 CT Orientation Viewer")

    # Data section in sidebar
    st.sidebar.header("Data")

    # Folder picker using text input
    data_path = st.sidebar.text_input(
        "DICOM Folder Path",
        value=r"C:\Users\hellwege\AAPMLowDose\1mm B30-selected\full_1mm\L067\full_1mm",
    )

    path_ok = bool(data_path and Path(data_path).exists())

    # Clear stale state when path changes
    if st.session_state.get("last_path") != data_path:
        st.session_state["last_path"] = data_path
        for k in ("series_list", "volume", "series", "loaded_files"):
            st.session_state.pop(k, None)

    if not path_ok:
        st.sidebar.warning("Enter a valid folder path")
    else:
        # Scan: persist result in session state so it survives reruns
        if st.sidebar.button("Scan Directory"):
            with st.spinner("Scanning directory..."):
                st.session_state["series_list"] = scan_series(Path(data_path))

        series_list = st.session_state.get("series_list") or []
        if series_list:
            series_options = [
                f"{s.patient_id} - {s.series_description or 'Unknown'} - {s.n_slices} slices"
                for s in series_list
            ]
            selected_idx = st.sidebar.selectbox(
                "Select Series",
                range(len(series_options)),
                format_func=lambda i: series_options[i],
            )
            selected_series = series_list[selected_idx]
            st.sidebar.markdown("---")

            # Use n_slices from selected series
            file_count = selected_series.n_slices
            slice_option = st.sidebar.radio(
                "Slices to load:",
                ["All slices", "Custom number"],
                key="slice_option",
            )
            n_slices = None
            if slice_option == "Custom number":
                n_slices = st.sidebar.number_input(
                    f"Number of slices (max {file_count})",
                    min_value=1,
                    max_value=file_count,
                    value=100,
                    key="n_slices_input",
                )

            if st.sidebar.button("Load Series"):
                # Use files from selected_series if available, otherwise scan folder
                if selected_series.files:
                    files = (
                        selected_series.files[:n_slices]
                        if n_slices
                        else selected_series.files
                    )
                else:
                    files = (
                        list(Path(data_path).iterdir())[:n_slices]
                        if n_slices
                        else list(Path(data_path).iterdir())
                    )

                with st.spinner("Loading DICOM series..."):
                    # Convert Path objects to strings for cache key
                    file_paths_str = [str(f) for f in files]
                    volume = load_volume_cached(file_paths_str)

                st.session_state["volume"] = volume
                st.session_state["series"] = selected_series
                st.session_state["loaded_files"] = files
                # Clear old slice indices so clamp_slice_state will center them
                for k in ("axial_slice", "coronal_slice", "sagittal_slice"):
                    st.session_state.pop(k, None)

                logger.info(
                    "Loaded %d slices, shape=%s", len(files), volume.array.shape
                )
                st.toast(f"Loaded {len(files)} slices!")
                save_last_loaded(files)

    # Auto-load from cache file on refresh (silent)
    if "volume" not in st.session_state:
        cached_files = load_last_loaded()
        if cached_files:
            file_paths_str = [str(f) for f in cached_files]
            volume = load_volume_cached(file_paths_str)
            st.session_state["volume"] = volume
            st.session_state["loaded_files"] = cached_files
            st.session_state["series"] = type(
                "S",
                (),
                {
                    "series_description": "CT Orientation Viewer",
                    "patient_id": "Unknown",
                    "n_slices": len(cached_files),
                },
            )()

    # Clear cache button
    if st.sidebar.button("🗑️ Clear Cache"):
        # Clear session state
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        # Clear Streamlit cache
        st.cache_data.clear()
        # Clear cache file
        clear_last_loaded()
        st.rerun()

    # Main area
    if "volume" in st.session_state:
        volume = st.session_state["volume"]

        # Reserve visual slot for 3D plot FIRST
        plot_slot = st.container()

        # 3D controls in expander (appears BELOW the plot)
        with st.expander("3D Options", expanded=False):
            col3d_1, col3d_2 = st.columns(2)

            with col3d_1:
                render_mode = st.selectbox(
                    "Render Mode",
                    ["iso", "volume", "pyvista"],
                    format_func=lambda x: "Iso-Surface" if x == "iso" else ("PyVista" if x == "pyvista" else "Plotly Volume"),
                    key="3d_render_mode",
                )

            with col3d_2:
                camera_preset = st.selectbox(
                    "Camera",
                    options=["iso", "front", "back", "left", "right", "top", "bottom"],
                    index=0,
                    format_func=lambda x: x.capitalize(),
                    key="3d_camera",
                )

            col_transp_1, col_transp_2 = st.columns(2)
            with col_transp_1:
                volume_opacity = st.slider(
                    "Volume Opacity",
                    min_value=0.05,
                    max_value=1.0,
                    value=0.05,
                    key="3d_volume_opacity",
                )
            with col_transp_2:
                surface_opacity = st.slider(
                    "Surface Opacity",
                    min_value=0.05,
                    max_value=1.0,
                    value=0.7,
                    key="3d_surface_opacity",
                )

            # Iso-surface controls (shown when iso mode selected)
            if render_mode == "iso":
                col_iso_1, col_iso_2 = st.columns(2)
                with col_iso_1:
                    n_iso_levels = st.slider(
                        "Iso-Surface Levels",
                        min_value=1,
                        max_value=10,
                        value=5,
                        key="3d_n_levels",
                    )
                with col_iso_2:
                    try:
                        v_min = int(np.min(volume.array))
                        v_max = int(np.max(volume.array))
                    except Exception:
                        v_min, v_max = -1000, 1000
                    iso_threshold = st.slider(
                        "Iso Threshold (HU)",
                        min_value=v_min,
                        max_value=v_max,
                        value=(v_min + 200, v_max - 200),
                        key="3d_iso_threshold",
                    )
            else:
                n_iso_levels = 5
                iso_threshold = None

            col_geo_1, col_geo_2 = st.columns(2)
            with col_geo_1:
                show_geometry = st.checkbox(
                    "Show Source/Detector", value=True, key="3d_show_geometry"
                )
            with col_geo_2:
                downsample = st.selectbox(
                    "Downsample",
                    options=[1, 2, 4],
                    index=2,
                    format_func=lambda x: f"{x}x",
                    key="3d_downsample",
                )

            col_sid, col_angle = st.columns(2)
            with col_sid:
                sid = st.number_input(
                    "SID (mm)", value=1000.0, step=100.0, key="3d_sid"
                )
            with col_angle:
                gantry_angle = st.number_input(
                    "Gantry Angle (°)", value=0.0, step=15.0, key="3d_gantry"
                )

            col_iso_auto_1, col_iso_auto_2 = st.columns(2)
            with col_iso_auto_1:
                auto_isocenter = st.checkbox(
                    "Auto Isocenter", value=True, key="3d_auto_iso"
                )
            with col_iso_auto_2:
                auto_geo = st.checkbox(
                    "Auto Source/Detector", value=True, key="3d_auto_geo"
                )

            if not auto_isocenter:
                col_x, col_y, col_z = st.columns(3)
                with col_x:
                    iso_x = st.number_input(
                        "Iso X", value=0.0, step=10.0, key="3d_iso_x"
                    )
                with col_y:
                    iso_y = st.number_input(
                        "Iso Y", value=0.0, step=10.0, key="3d_iso_y"
                    )
                with col_z:
                    iso_z = st.number_input(
                        "Iso Z", value=0.0, step=10.0, key="3d_iso_z"
                    )
                isocenter = (iso_x, iso_y, iso_z)
            else:
                isocenter = None

            if not auto_geo:
                col_src, col_det = st.columns(2)
                with col_src:
                    src_x = st.number_input(
                        "Source X", value=-500.0, step=50.0, key="3d_src_x"
                    )
                    src_y = st.number_input(
                        "Source Y", value=0.0, step=50.0, key="3d_src_y"
                    )
                    src_z = st.number_input(
                        "Source Z", value=0.0, step=50.0, key="3d_src_z"
                    )
                    source_pos = (src_x, src_y, src_z)
                with col_det:
                    det_x = st.number_input(
                        "Detector X", value=500.0, step=50.0, key="3d_det_x"
                    )
                    det_y = st.number_input(
                        "Detector Y", value=0.0, step=50.0, key="3d_det_y"
                    )
                    det_z = st.number_input(
                        "Detector Z", value=0.0, step=50.0, key="3d_det_z"
                    )
                    detector_pos = (det_x, det_y, det_z)
            else:
                source_pos = None
                detector_pos = None

        # Generate 3D plot and render into reserved slot
        try:
            spacing = volume.spacing
        except AttributeError:
            spacing = (1.0, 1.0, 1.0)

        # Handle PyVista rendering separately
        if render_mode == "pyvista":
            from visualization.volume3d import create_pyvista_volume

            pyvista_result = create_pyvista_volume(
                volume.array,
                spacing=spacing,
                opacity=volume_opacity,
                colormap="bone",
                downsample=downsample,
                camera_preset=camera_preset,
            )
            # Display the PyVista screenshot
            st.image(pyvista_result["screenshot"], caption=f"PyVista Volume | Voxel spacing: ({pyvista_result['spacing'][0]:.2f}, {pyvista_result['spacing'][1]:.2f}, {pyvista_result['spacing'][2]:.2f}) mm")
        else:
            fig = create_volume_figure(
                volume.array,
                spacing=spacing,
                render_mode=render_mode,
                opacity=volume_opacity,
                surface_opacity=surface_opacity,
                colormap="bone",
                downsample=downsample,
                camera_preset=camera_preset,
                n_iso_levels=n_iso_levels,
                iso_threshold=iso_threshold,
            )

            # Add source/detector if enabled
            if show_geometry:
                if isocenter is None:
                    isocenter = get_volume_center(volume.array, spacing)

                fig = add_source_detector_figure(
                    fig,
                    volume_array=volume.array,
                    spacing=spacing,
                    isocenter=isocenter,
                    sid=sid,
                    sdd=sid,
                    gantry_angle=gantry_angle,
                    show_source=True,
                    show_detector=True,
                    source_pos=source_pos,
                    detector_pos=detector_pos,
                )

            # Render into the reserved slot
            with plot_slot:
                st.plotly_chart(fig, use_container_width=True, key="plotly_3d")

        # Get dimensions for each plane (needed for slice sliders)
        axial_max = volume.array.shape[0] - 1
        coronal_max = volume.array.shape[1] - 1
        sagittal_max = volume.array.shape[2] - 1

        # Clamp slice indices in session state BEFORE creating sliders
        clamp_slice_state("axial_slice", axial_max)
        clamp_slice_state("coronal_slice", coronal_max)
        clamp_slice_state("sagittal_slice", sagittal_max)

        # Slice options in expander
        with st.expander("Slice Options", expanded=False):
            # Windowing controls
            col_preset, col_center, col_width = st.columns(3)

            with col_preset:
                window_preset = st.selectbox(
                    "Preset",
                    options=list(WINDOW_PRESETS.keys()),
                    index=1,  # abdomen default
                )

            with col_center:
                center = st.slider(
                    "Center (HU)",
                    min_value=-1000,
                    max_value=3000,
                    value=WINDOW_PRESETS[window_preset][0],
                )

            with col_width:
                width = st.slider(
                    "Width (HU)",
                    min_value=1,
                    max_value=4000,
                    value=WINDOW_PRESETS[window_preset][1],
                )

            # Slice selection sliders
            col_axial, col_coronal, col_sagittal = st.columns(3)

            with col_axial:
                axial_idx = st.slider("Axial Slice", 0, axial_max, key="axial_slice")

            with col_coronal:
                coronal_idx = st.slider(
                    "Coronal Slice", 0, coronal_max, key="coronal_slice"
                )

            with col_sagittal:
                sagittal_idx = st.slider(
                    "Sagittal Slice", 0, sagittal_max, key="sagittal_slice"
                )

        # MPR Display - 3 columns
        axial_col, coronal_col, sagittal_col = st.columns(3)

        # Axial view
        with axial_col:
            st.markdown("**Axial**")
            axial_slice, axial_spacing = extract_slice(volume, "axial", axial_idx)
            axial_windowed = apply_window(axial_slice, center, width)
            st.caption(
                f"Slice {axial_idx + 1}/{axial_max + 1} | Spacing: ({axial_spacing[0]:.8f}, {axial_spacing[1]:.8f})"
            )
            st.image(axial_windowed, clamp=True, use_column_width=True)

        # Coronal view
        with coronal_col:
            st.markdown("**Coronal**")
            coronal_slice, coronal_spacing = extract_slice(
                volume, "coronal", coronal_idx
            )
            coronal_windowed = apply_window(coronal_slice, center, width)
            # Resample to isotropic for correct aspect ratio
            coronal_resampled = to_isotropic(coronal_windowed, coronal_spacing)
            st.caption(
                f"Slice {coronal_idx + 1}/{coronal_max + 1} | Spacing: ({coronal_spacing[0]:.8f}, {coronal_spacing[1]:.8f})"
            )
            st.image(coronal_resampled, clamp=True, use_column_width=True)

        # Sagittal view
        with sagittal_col:
            st.markdown("**Sagittal**")
            sagittal_slice, sagittal_spacing = extract_slice(
                volume, "sagittal", sagittal_idx
            )
            sagittal_windowed = apply_window(sagittal_slice, center, width)
            # Resample to isotropic for correct aspect ratio
            sagittal_resampled = to_isotropic(sagittal_windowed, sagittal_spacing)
            st.caption(
                f"Slice {sagittal_idx + 1}/{sagittal_max + 1} | Spacing: ({sagittal_spacing[0]:.8f}, {sagittal_spacing[1]:.8f})"
            )
            st.image(sagittal_resampled, clamp=True, use_column_width=True)

    else:
        # Welcome screen / Demo mode
        st.info("👈 Select a DICOM folder to get started")

        st.markdown("""
        ## Features

        - **DICOM Loading** - Read CT scans from DICOM files
        - **Windowing** - Presets for lung, abdomen, bone, brain + manual controls
        - **MPR** - Multi-planar reconstruction (axial, coronal, sagittal)
        - **3D View** - Volume visualization (coming soon)

        ## Demo Mode

        Use the demo phantom to test without real data.
        """)

        if st.button("Load Demo Phantom"):
            # TODO: Implement demo phantom
            st.info("Demo phantom coming soon!")


if __name__ == "__main__":
    main()
