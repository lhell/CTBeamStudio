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
import streamlit as st
import streamlit.components.v1 as components
from streamlit_image_coordinates import streamlit_image_coordinates

from visualization.loaders.dicom import load_dicom_series, scan_series
from visualization.mpr import extract_slice
from visualization.windowing import WINDOW_PRESETS, apply_window


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

    st.title("🏥 CT Orientation Viewer")

    # Sidebar: Data selection
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
                f"{s.series_description or 'Unknown'} - {s.n_slices} slices ({s.dose_class})"
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

                progress_bar = st.progress(0, text="Loading DICOM series...")

                def report(done, total):
                    progress_bar.progress(
                        done / total, text=f"Loaded {done}/{total} slices"
                    )

                volume = load_dicom_series(files, progress=report)
                progress_bar.empty()  # Clear progress bar

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

    # Show loaded files expander (persists across reruns)
    loaded = st.session_state.get("loaded_files")
    if loaded:
        with st.sidebar.expander(f"Loaded Files ({len(loaded)})"):
            for f in loaded:
                st.text(f.name)

    # Main area
    if "volume" in st.session_state:
        volume = st.session_state["volume"]
        series = st.session_state["series"]

        st.markdown(f"### {series.series_description or 'CT Scan'}")

        # Windowing controls (common for all planes)
        st.markdown("---")
        st.subheader("Windowing")

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

        # MPR Display - 3 columns
        st.markdown("---")
        st.subheader("MPR Views")

        # Click instruction
        st.caption("💡 Click on an image to navigate the other planes (crosshair)")

        axial_col, coronal_col, sagittal_col = st.columns(3)

        # Get dimensions for each plane
        axial_max = volume.array.shape[0] - 1
        coronal_max = volume.array.shape[1] - 1
        sagittal_max = volume.array.shape[2] - 1

        # Clamp slice indices in session state BEFORE creating sliders
        clamp_slice_state("axial_slice", axial_max)
        clamp_slice_state("coronal_slice", coronal_max)
        clamp_slice_state("sagittal_slice", sagittal_max)

        # Helper function for slider with anchor and jump buttons
        def slice_slider(plane: str, key: str, max_idx: int):
            st.markdown(
                f'<div class="mpr-anchor" data-plane="{plane}"></div>',
                unsafe_allow_html=True,
            )
            idx = st.slider("Slice", 0, max_idx, key=key, label_visibility="collapsed")
            b_min, b_max = st.columns(2)
            b_min.button(
                "⏮",
                key=f"{key}_min",
                use_container_width=True,
                on_click=lambda: st.session_state.update({key: 0}),
            )
            b_max.button(
                "⏭",
                key=f"{key}_max",
                use_container_width=True,
                on_click=lambda: st.session_state.update({key: max_idx}),
            )
            return idx

        # Axial view
        with axial_col:
            st.markdown("**Axial**")
            axial_idx = slice_slider("axial", "axial_slice", axial_max)
            axial_slice, axial_spacing = extract_slice(volume, "axial", axial_idx)
            axial_windowed = apply_window(axial_slice, center, width)
            st.caption(
                f"Slice {axial_idx + 1}/{axial_max + 1} | Spacing: ({axial_spacing[0]:.8f}, {axial_spacing[1]:.8f})"
            )
            axial_coords = streamlit_image_coordinates(
                axial_windowed, key="axial_click", use_column_width="auto"
            )
            # Crosshair: clicking axial updates coronal and sagittal
            if axial_coords:
                y, x = axial_coords["x"], axial_coords["y"]
                # Convert to slice indices (approximate)
                new_coronal = int(x * coronal_max / axial_windowed.shape[1])
                new_sagittal = int(y * sagittal_max / axial_windowed.shape[0])
                st.session_state["coronal_slice"] = max(
                    0, min(new_coronal, coronal_max)
                )
                st.session_state["sagittal_slice"] = max(
                    0, min(new_sagittal, sagittal_max)
                )

        # Coronal view
        with coronal_col:
            st.markdown("**Coronal**")
            coronal_idx = slice_slider("coronal", "coronal_slice", coronal_max)
            coronal_slice, coronal_spacing = extract_slice(
                volume, "coronal", coronal_idx
            )
            coronal_windowed = apply_window(coronal_slice, center, width)
            # Resample to isotropic for correct aspect ratio
            coronal_resampled = to_isotropic(coronal_windowed, coronal_spacing)
            st.caption(
                f"Slice {coronal_idx + 1}/{coronal_max + 1} | Spacing: ({coronal_spacing[0]:.8f}, {coronal_spacing[1]:.8f})"
            )
            coronal_coords = streamlit_image_coordinates(
                coronal_resampled,
                key="coronal_click",
                use_column_width="auto",
            )
            # Crosshair: clicking coronal updates axial and sagittal
            if coronal_coords:
                y, x = coronal_coords["x"], coronal_coords["y"]
                # axial uses row (y), sagittal uses col (x)
                new_axial = int(y * axial_max / coronal_resampled.shape[0])
                new_sagittal = int(x * sagittal_max / coronal_resampled.shape[1])
                st.session_state["axial_slice"] = max(0, min(new_axial, axial_max))
                st.session_state["sagittal_slice"] = max(
                    0, min(new_sagittal, sagittal_max)
                )

        # Sagittal view
        with sagittal_col:
            st.markdown("**Sagittal**")
            sagittal_idx = slice_slider("sagittal", "sagittal_slice", sagittal_max)
            sagittal_slice, sagittal_spacing = extract_slice(
                volume, "sagittal", sagittal_idx
            )
            sagittal_windowed = apply_window(sagittal_slice, center, width)
            # Resample to isotropic for correct aspect ratio
            sagittal_resampled = to_isotropic(sagittal_windowed, sagittal_spacing)
            st.caption(
                f"Slice {sagittal_idx + 1}/{sagittal_max + 1} | Spacing: ({sagittal_spacing[0]:.8f}, {sagittal_spacing[1]:.8f})"
            )
            sagittal_coords = streamlit_image_coordinates(
                sagittal_resampled,
                key="sagittal_click",
                use_column_width="auto",
            )
            # Crosshair: clicking sagittal updates axial and coronal
            if sagittal_coords:
                y, x = sagittal_coords["x"], sagittal_coords["y"]
                # axial uses row (y), coronal uses col (x)
                new_axial = int(y * axial_max / sagittal_resampled.shape[0])
                new_coronal = int(x * coronal_max / sagittal_resampled.shape[1])
                st.session_state["axial_slice"] = max(0, min(new_axial, axial_max))
                st.session_state["coronal_slice"] = max(
                    0, min(new_coronal, coronal_max)
                )

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
