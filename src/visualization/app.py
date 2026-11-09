"""Streamlit app for CTBeamStudio."""

import logging
import sys
import time
import uuid
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

from visualization.background_load import (
    STATUS_DONE,
    STATUS_FAILED,
    effective_status,
    job_state,
    reset_job,
    start_job,
)
from visualization.display_units import (
    DISPLAY_UNIT_HU,
    DISPLAY_UNIT_MU,
    DISPLAY_UNITS,
    to_display_units,
    unit_label,
    window_in_display_units,
    window_limits,
)
from visualization.mpr import extract_slice
from visualization.projection_panel import (
    render_comparison_tab,
    render_geometry_tab,
)
from visualization.volume3d import (
    add_geometry_toggle,
    add_source_detector_figure,
    create_volume_figure,
    get_volume_center,
)
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


def render_viewer_tab(
    volume, projection_geometry, n_projections: int, trajectory_downsample: int
) -> None:
    """Render the 3D volume and MPR views."""
    if volume is None:
        if st.session_state.get("startup_polling"):
            # Loading in progress: the status block stands in for the 3D plot,
            # so the layout does not jump when the volume arrives.
            render_startup_status()
            return

        if st.session_state.get("startup_failed"):
            # Rendered on the normal script path, not inside the fragment, so
            # the recovery button still exists after polling has stopped.
            _render_startup_failure()
            return

        # Welcome screen / Demo mode
        st.info("👈 Select a DICOM folder to get started")

        st.markdown("""
        ## Features

        - **DICOM Loading** - Read CT scans from DICOM files
        - **Windowing** - Presets for lung, abdomen, bone, brain + manual controls
        - **MPR** - Multi-planar reconstruction (axial, coronal, sagittal)
        - **3D View** - Volume visualization

        ## Demo Mode

        Use the demo phantom to test without real data.
        """)

        if st.button("Load Demo Phantom"):
            from visualization.sidebar import load_demo_volume

            with st.spinner("Loading demo phantom..."):
                load_demo_volume()
            st.rerun()
        return

    # Reserve visual slot for 3D plot FIRST
    plot_slot = st.container()

    # 3D controls in expander (appears BELOW the plot)
    with st.expander("3D Options", expanded=True):
        col3d_1, col3d_2 = st.columns(2)

        with col3d_1:
            # PyVista is shelved for now (see plan.md T-82): it rendered a
            # static PNG, so it could not host the interactive geometry
            # toggle. Only the Plotly iso-surface path remains.
            render_mode = st.selectbox(
                "Render Mode",
                ["iso"],
                format_func=lambda x: "Iso-Surface",
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

        col_sid, col_angle = st.columns(2)
        with col_sid:
            sid = st.number_input("SID (mm)", value=1000.0, step=100.0, key="3d_sid")
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
                iso_x = st.number_input("Iso X", value=0.0, step=10.0, key="3d_iso_x")
            with col_y:
                iso_y = st.number_input("Iso Y", value=0.0, step=10.0, key="3d_iso_y")
            with col_z:
                iso_z = st.number_input("Iso Z", value=0.0, step=10.0, key="3d_iso_z")
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

    # PyVista rendering is shelved for now (see plan.md T-82): it produced a
    # static PNG and could not host the interactive geometry toggle. The
    # renderer itself stays in volume3d.create_pyvista_volume() for later.
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

    # Traces added from here on belong to the geometry overlay: the in-plot
    # slider toggles everything after this point (see add_geometry_toggle).
    n_base_traces = len(fig.data)

    if isocenter is None:
        isocenter = get_volume_center(volume.array, spacing)

    # Add the trajectory whenever a geometry is loaded; without one there is
    # no path to draw, so fall back to the single source/detector pair. The
    # in-plot "Projection Geometry" control switches the overlay on and off,
    # so no second show/hide checkbox is needed here.
    if projection_geometry is not None:
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

    fig = add_geometry_toggle(fig, n_base_traces)

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
        # Display unit: HU or energy-dependent linear attenuation
        col_unit, col_energy = st.columns(2)

        with col_unit:
            display_unit = st.selectbox(
                "Display Unit",
                options=list(DISPLAY_UNITS),
                index=0,
                key="display_unit",
            )

        energy_kev = 70.0
        with col_energy:
            if display_unit == DISPLAY_UNIT_MU:
                energy_kev = float(
                    st.slider(
                        "Energy (keV)",
                        min_value=30,
                        max_value=150,
                        value=70,
                        step=5,
                        key="display_energy",
                    )
                )
            else:
                st.caption("Attenuation mode uses a monoenergetic energy.")

        # Windowing controls
        col_preset, col_center, col_width = st.columns(3)

        with col_preset:
            window_preset = st.selectbox(
                "Preset",
                options=list(WINDOW_PRESETS.keys()),
                index=1,  # abdomen default
            )

        limits = window_limits(display_unit, energy_kev)
        default_center, default_width = window_in_display_units(
            window_preset, display_unit, energy_kev
        )
        slider_unit = unit_label(display_unit)
        slider_format = "%.0f" if display_unit == DISPLAY_UNIT_HU else "%.4f"

        with col_center:
            center = st.slider(
                f"Center ({slider_unit})",
                min_value=float(limits["center_min"]),
                max_value=float(limits["center_max"]),
                value=float(default_center),
                step=float(limits["step"]),
                format=slider_format,
            )

        with col_width:
            width = st.slider(
                f"Width ({slider_unit})",
                min_value=float(limits["width_min"]),
                max_value=float(limits["width_max"]),
                value=float(default_width),
                step=float(limits["step"]),
                format=slider_format,
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
        axial_display = to_display_units(axial_slice, display_unit, energy_kev)
        axial_windowed = apply_window(axial_display, center, width)
        st.caption(
            f"Slice {axial_idx + 1}/{axial_max + 1} | Spacing: "
            f"({axial_spacing[0]:.8f}, {axial_spacing[1]:.8f})"
        )
        st.image(axial_windowed, clamp=True, use_column_width=True)

    # Coronal view
    with coronal_col:
        st.markdown("**Coronal**")
        coronal_slice, coronal_spacing = extract_slice(volume, "coronal", coronal_idx)
        coronal_display = to_display_units(coronal_slice, display_unit, energy_kev)
        coronal_windowed = apply_window(coronal_display, center, width)
        # Resample to isotropic for correct aspect ratio
        coronal_resampled = to_isotropic(coronal_windowed, coronal_spacing)
        st.caption(
            f"Slice {coronal_idx + 1}/{coronal_max + 1} | Spacing: "
            f"({coronal_spacing[0]:.8f}, {coronal_spacing[1]:.8f})"
        )
        st.image(coronal_resampled, clamp=True, use_column_width=True)

    # Sagittal view
    with sagittal_col:
        st.markdown("**Sagittal**")
        sagittal_slice, sagittal_spacing = extract_slice(
            volume, "sagittal", sagittal_idx
        )
        sagittal_display = to_display_units(sagittal_slice, display_unit, energy_kev)
        sagittal_windowed = apply_window(sagittal_display, center, width)
        # Resample to isotropic for correct aspect ratio
        sagittal_resampled = to_isotropic(sagittal_windowed, sagittal_spacing)
        st.caption(
            f"Slice {sagittal_idx + 1}/{sagittal_max + 1} | Spacing: "
            f"({sagittal_spacing[0]:.8f}, {sagittal_spacing[1]:.8f})"
        )
        st.image(sagittal_resampled, clamp=True, use_column_width=True)


STARTUP_FAILURE_MESSAGE = (
    "No cached image data found. Select image data in the sidebar or "
    "load the demo phantom."
)


def _startup_job_name() -> str:
    """This session's job name (helper lives in sidebar to avoid a cycle)."""
    from visualization.sidebar import startup_job_name

    return startup_job_name()


@st.fragment(run_every="1s")
def render_startup_status() -> None:
    """Poll the startup job and render its progress in the viewer area.

    Runs as a fragment so only this block re-executes: the rest of the page
    stays interactive while a series is being read. ``run_every`` cannot be
    switched off from inside the fragment, so the ``startup_polling`` flag is
    the stop switch for the terminal states.
    """
    if not st.session_state.get("startup_polling"):
        return

    job_name = _startup_job_name()
    started_at = st.session_state.get("startup_started_at", time.time())
    status, result, error = job_state(job_name)
    status = effective_status(status, started_at, time.time())

    if status == "running":
        st.status("Lade Daten …", expanded=True)
        return

    # Terminal state: stop the loop whatever happened below.
    st.session_state["startup_polling"] = False
    reset_job(job_name)

    if status == STATUS_DONE:
        st.session_state["startup_failed"] = False
        # An explicit "Load Series" may have finished while the job ran; that
        # volume wins, and the background result is discarded.
        if st.session_state.get("volume") is None:
            st.session_state["volume"] = result
            st.toast("Daten geladen", icon="✅")
        st.rerun()
        return

    st.session_state["startup_failed"] = True
    if error is not None:
        logger.warning("Background startup load failed: %s", error)
    # Rerun so the failure panel is rendered by the normal script path, where
    # its button survives polling having stopped.
    st.rerun()


def _render_startup_failure() -> None:
    """Show the failure notice and its recovery button.

    Rendered outside the polling branch so the button survives long enough to
    be clicked.
    """
    st.error(STARTUP_FAILURE_MESSAGE)
    if st.button("Load Demo Phantom", key="startup_load_demo"):
        from visualization.sidebar import create_demo_volume_job

        st.session_state["volume"] = create_demo_volume_job()()
        st.session_state["demo_mode"] = True
        st.session_state["startup_failed"] = False
        st.rerun()


def main():
    st.set_page_config(page_title="CTBeamStudio", page_icon="🏥", layout="wide")

    # Render a lightweight shell first: it is streamed to the browser before
    # the (potentially slow) data loading below, so the page appears instantly.
    shell = st.empty()
    shell.info("⏳ Initialisiere Oberfläche …")

    # Render sidebar and get values
    from visualization.sidebar import render_sidebar, startup_loader

    volume, projection_geometry, n_projections, trajectory_downsample = render_sidebar()

    if volume is None and not st.session_state.get("startup_failed"):
        # The read happens in a worker thread so this script run does not block:
        # sidebar expanders and tabs stay usable while data loads. The viewer
        # area polls the job and fills itself in when the volume is ready.
        # A failed startup is not retried automatically, or every rerun would
        # start another attempt and the failure panel would never be seen.
        loader = startup_loader(
            has_data_path=bool(st.session_state.get("data_path")),
            auto_load_cache=st.session_state.get("auto_load_cache", True),
        )
        if loader is not None and start_job(_startup_job_name(), loader):
            st.session_state["startup_polling"] = True
            st.session_state["startup_started_at"] = time.time()

    # Show demo mode banner if applicable
    if st.session_state.get("demo_mode"):
        st.info(
            "🏥 **Demo Mode** — Using synthetic Shepp-Logan phantom. "
            "Enter a DICOM folder path in the sidebar to load real data.",
            icon="ℹ️",
        )

    shell.empty()

    tab_view, tab_geometry, tab_compare = st.tabs(
        ["🩻 Viewer", "📐 Geometry", "⚡ Real vs Simulated"]
    )

    with tab_view:
        render_viewer_tab(
            volume, projection_geometry, n_projections, trajectory_downsample
        )

    with tab_geometry:
        render_geometry_tab(projection_geometry)

    with tab_compare:
        render_comparison_tab(volume, projection_geometry)


if __name__ == "__main__":
    main()
