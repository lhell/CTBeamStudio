"""Streamlit app for CTBeamStudio."""

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

from backend.loaders.dicom import load_dicom_series, scan_series
from visualization.mpr import extract_slice
from visualization.volume3d import (
    add_source_detector_figure,
    create_volume_figure,
    get_volume_center,
)

# Import caching functions from volume_cache module
from visualization.volume_cache import clear_last_loaded
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
        page_title="CTBeamStudio", page_icon="🏥", layout="wide"
    )

    # Show demo mode banner if applicable
    if st.session_state.get("demo_mode"):
        st.info(
            "🏥 **Demo Mode** — Using synthetic Shepp-Logan phantom. "
            "Enter a DICOM folder path in the sidebar to load real data.",
            icon="ℹ️",
        )

    # Render sidebar and get values
    from visualization.sidebar import render_sidebar

    volume, projection_geometry, n_projections, trajectory_downsample = render_sidebar()

    # Main area
    if "volume" in st.session_state:
        volume = st.session_state["volume"]

        # Reserve visual slot for 3D plot FIRST
        plot_slot = st.container()

        # 3D controls in expander (appears BELOW the plot)
        with st.expander("3D Options", expanded=True):
            col3d_1, col3d_2 = st.columns(2)

            with col3d_1:
                render_mode = st.selectbox(
                    "Render Mode",
                    ["iso", "pyvista"],
                    format_func=lambda x: "Iso-Surface" if x == "iso" else "PyVista",
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

            # Volume downsample for performance
            volume_downsample = st.selectbox(
                "Downsample",
                options=[1, 2, 4, 8],
                index=2,
                format_func=lambda x: f"{x}x",
                key="3d_volume_downsample",
            )
            # Update session state for rendering
            st.session_state["volume_downsample"] = volume_downsample

            # Trajectory toggle
            show_trajectory = st.checkbox(
                "Show Trajectory",
                value=projection_geometry is not None,
                key="3d_show_trajectory",
            )

            # Single opacity slider
            opacity = st.slider(
                "Opacity",
                min_value=0.1,
                max_value=1.0,
                value=0.6,
                key="3d_opacity",
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

            # Projection geometry controls (using sidebar values)
            show_geometry = True

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

        # Use downsample from UI (set by selectbox above)
        volume_downsample = st.session_state.get("volume_downsample", 4)

        # Handle PyVista rendering separately
        if render_mode == "pyvista":
            from visualization.volume3d import create_pyvista_volume

            pyvista_result = create_pyvista_volume(
                volume.array,
                spacing=spacing,
                opacity=opacity,
                colormap="bone",
                downsample=volume_downsample,
                camera_preset=camera_preset,
            )
            # Display the PyVista screenshot
            st.image(
                pyvista_result["screenshot"],
                caption=f"PyVista Volume | Voxel spacing: ({pyvista_result['spacing'][0]:.2f}, {pyvista_result['spacing'][1]:.2f}, {pyvista_result['spacing'][2]:.2f}) mm",
            )
        else:
            fig = create_volume_figure(
                volume.array,
                spacing=spacing,
                render_mode=render_mode,
                opacity=opacity,
                surface_opacity=opacity,
                colormap="bone",
                downsample=volume_downsample,
                camera_preset=camera_preset,
                n_iso_levels=n_iso_levels,
                iso_threshold=iso_threshold,
            )

            # Add source/detector if enabled
            if show_geometry:
                if isocenter is None:
                    isocenter = get_volume_center(volume.array, spacing)

                # Add trajectory if enabled and projection geometry is loaded
                if show_trajectory and projection_geometry is not None:
                    from visualization.volume3d import (
                        add_trajectory_to_figure,
                        get_trajectory_positions,
                    )

                    src_positions, det_positions = get_trajectory_positions(
                        projection_geometry, n_projections
                    )
                    fig = add_trajectory_to_figure(
                        fig,
                        src_positions,
                        det_positions,
                        trajectory_downsample,
                        geometry=projection_geometry,
                    )
                else:
                    # Use legacy single source/detector
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
        with st.expander("Slice Options", expanded=True):
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
