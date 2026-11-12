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


def render_empty_state() -> None:
    """Show the "nothing loaded yet" state.

    Reached on a fresh start and after Clear Cache. Nothing is loaded
    automatically: the user either picks image data in the sidebar or asks for
    the demo phantom.
    """
    st.info(
        "Nothing to show — load image data in the sidebar, or use the demo phantom."
    )

    if st.button("Load Demo Phantom", key="empty_load_demo"):
        from visualization.sidebar import load_demo_volume

        with st.spinner("Loading demo phantom..."):
            load_demo_volume()
        st.rerun()


# Shared height for the two viewer columns, so the MPR stack and the 3D canvas
# end on one baseline. Both the container and the Plotly figure read this, so
# they cannot drift apart. 700px matches a typical laptop viewport, so the whole
# viewer sits above the fold; a taller canvas pushed the 3D scene out of view.
VIEWER_HEIGHT_PX = 700

# The 3D scene is anchored toward the top of its canvas. Plotly centres a 3D
# scene in its domain, so a centred cube in a tall canvas drops below the fold.
SCENE_DOMAIN_Y = [0.2, 1]

# A column ratio of 0.0001 renders at exactly 0 px, which is how the view
# switcher collapses one side. A literal 0 is rejected by st.columns
# (StreamlitInvalidColumnSpecError: widths must be positive).
COLLAPSED_COLUMN = 0.0001

VIEWER_VIEWS = ("All", "2D", "3D")
VIEWER_COLUMN_SPECS = {
    "All": [1, 2],
    "2D": [1, COLLAPSED_COLUMN],
    "3D": [COLLAPSED_COLUMN, 1],
}


def viewer_column_spec(view: str) -> list[float]:
    """Column widths for a view. Unknown views fall back to the split."""
    return VIEWER_COLUMN_SPECS.get(view, VIEWER_COLUMN_SPECS["All"])


def viewer_has_mpr(view: str) -> bool:
    """3D mode collapses the MPR column entirely."""
    return view != "3D"


def viewer_has_3d(view: str) -> bool:
    """2D mode collapses the 3D column entirely."""
    return view != "2D"


def render_viewer_tab(
    volume, projection_geometry, n_projections: int, trajectory_downsample: int
) -> None:
    """Render the 3D volume and MPR views."""
    if volume is None:
        if st.session_state.get("startup_polling"):
            # Loading in progress: the status box stands in for the 3D plot so
            # the layout does not jump when the volume arrives. The box is
            # rendered here, on the normal script path, not inside the polling
            # fragment: elements drawn by the fragment linger after polling
            # stops (a stale "Loading data …" box stayed on screen next to the
            # loaded volume).
            st.status("Loading data …", expanded=True)
            render_startup_status()
            return

        if st.session_state.get("startup_failed"):
            st.error(STARTUP_FAILURE_MESSAGE)

        render_empty_state()
        return

    # Dimension bounds and slot clamping happen before any widget is created:
    # a resized volume otherwise leaves a stale slice key outside the new
    # range and the slider raises a widget-key error on creation.
    axial_max = volume.array.shape[0] - 1
    coronal_max = volume.array.shape[1] - 1
    sagittal_max = volume.array.shape[2] - 1

    clamp_slice_state("axial_slice", axial_max)
    clamp_slice_state("coronal_slice", coronal_max)
    clamp_slice_state("sagittal_slice", sagittal_max)

    # The switcher must sit OUTSIDE the columns: inside a collapsed column it
    # would be unreachable and the user could not switch back.
    view = st.radio(
        "View",
        options=VIEWER_VIEWS,
        index=0,
        horizontal=True,
        key="viewer_view",
        label_visibility="collapsed",
    )

    col_mpr, col_3d = st.columns(viewer_column_spec(view))

    with col_3d:
        # A popover floats over the view, so opening it does not push the
        # canvas down. Its body executes on every rerun, so the control values
        # are available to the figure build below.
        with st.popover("⚙️ 3D Options", use_container_width=True):
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

        # In 2D mode the 3D column is collapsed to 0 px. Building the figure
        # means marching cubes over the whole volume, so skip it when there is
        # nowhere to show it. The widgets above still run, so their values
        # survive a trip through 2D and back.
        if viewer_has_3d(view):
            # Generate 3D plot
            try:
                spacing = volume.spacing
            except AttributeError:
                spacing = (1.0, 1.0, 1.0)

            # The 3D view draws the volume in the same world frame the
            # forward projection uses: the real DICOM origin, so the
            # geometry overlay (source path, central beams at the world
            # origin) and the rendered phantom agree with the simulated
            # projections. Volumes without an origin attribute fall back to
            # the legacy schematic centred view.
            origin = getattr(volume, "origin", None)

            # Use downsample from UI (set by selectbox above)
            volume_downsample = st.session_state.get("volume_downsample", 4)

            # PyVista rendering is shelved for now (see plan.md T-82): it
            # produced a static PNG and could not host the interactive geometry
            # toggle. The renderer itself stays in
            # volume3d.create_pyvista_volume() for later.
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
                origin=origin,
            )

            # Traces added from here on belong to the geometry overlay: the
            # in-plot buttons toggle everything after this point (see
            # add_geometry_toggle). Keep this immediately after
            # create_volume_figure and before every overlay trace.
            n_base_traces = len(fig.data)

            if isocenter is None:
                isocenter = get_volume_center(volume.array, spacing, origin=origin)

            # Add the trajectory whenever a geometry is loaded; without one
            # there is no path to draw, so fall back to the single
            # source/detector pair. The in-plot "Projection Geometry" control
            # switches the overlay on and off, so no second show/hide checkbox
            # is needed here.
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

            # Height is shared with the MPR container so both columns end on
            # one baseline. The top-anchored scene domain keeps the cube above
            # the fold (Plotly otherwise centres it in the tall canvas and half
            # of it lands below the viewport). update_layout merges into the
            # scene the figure already defines, so axes, camera and background
            # survive.
            fig.update_layout(
                height=VIEWER_HEIGHT_PX,
                scene=dict(domain=dict(x=[0, 1], y=SCENE_DOMAIN_Y)),
            )

            st.plotly_chart(fig, use_container_width=True, key="plotly_3d")

    # Each plane is extracted once up front: the spacing is needed by the
    # readout inside Slice Options, and the same array feeds the image below.
    raw_slices = {}
    for plane in ("axial", "coronal", "sagittal"):
        index = st.session_state[f"{plane}_slice"]
        raw, plane_spacing = extract_slice(volume, plane, index)
        raw_slices[plane] = (raw, plane_spacing, index)

    with col_mpr:
        # A popover floats over the view, so opening it does not reflow the
        # MPR images.
        with st.popover("⚙️ Slice Options", use_container_width=True):
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

            # The per-plane readout lives here, not under each image: it is
            # diagnostic text and it cost 25 px of height per plane.
            st.divider()
            for label, maximum, (_, spacing, index) in (
                ("Axial", axial_max, raw_slices["axial"]),
                ("Coronal", coronal_max, raw_slices["coronal"]),
                ("Sagittal", sagittal_max, raw_slices["sagittal"]),
            ):
                st.caption(
                    f"**{label}** — slice {index + 1}/{maximum + 1} | "
                    f"spacing ({spacing[0]:.4f}, {spacing[1]:.4f}) mm"
                )

        # The planes need the window settings, so they are windowed after the
        # popover body has run.
        images = {}
        for plane, (raw, plane_spacing, index) in raw_slices.items():
            display = to_display_units(raw, display_unit, energy_kev)
            windowed = apply_window(display, center, width)
            if plane != "axial":
                # Resample to isotropic for correct aspect ratio
                windowed = to_isotropic(windowed, plane_spacing)
            images[plane] = windowed

        # The 3D column being collapsed must not stop the planes rendering, so
        # they are gated on the view rather than on column existence.
        if viewer_has_mpr(view):
            if view == "2D":
                # 2D-only: a 2x2 grid uses the full width better than a stack
                # of three planes. The fourth cell stays empty.
                row1 = st.columns(2)
                row2 = st.columns(2)
                targets = [row1[0], row1[1], row2[0]]
            else:
                # Split view: a compact vertical stack in a fixed-height
                # container, so an anisotropic coronal/sagittal plane scrolls
                # instead of stretching the page.
                container = st.container(height=VIEWER_HEIGHT_PX, border=False)
                targets = [container] * 3

            for name, plane, target in zip(
                ("Axial", "Coronal", "Sagittal"),
                ("axial", "coronal", "sagittal"),
                targets,
            ):
                with target:
                    st.markdown(f"**{name}**")
                    st.image(images[plane], clamp=True, use_column_width=True)


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
        return

    # Terminal state: stop the loop and hand over to the main script.
    #
    # This fragment deliberately renders no elements. Anything it drew would
    # linger in the page after polling stops, because the fragment is not
    # called again once `startup_polling` is false (observed in the browser:
    # a stale loading box stayed on screen next to the loaded volume). The
    # visible status box is rendered by the main script instead.
    st.session_state["startup_polling"] = False
    reset_job(job_name)

    if status == STATUS_DONE:
        st.session_state["startup_failed"] = False
        # An explicit "Load Series" may have finished while the job ran; that
        # volume wins, and the background result is discarded.
        if st.session_state.get("volume") is None:
            st.session_state["volume"] = result
            st.toast("Data loaded", icon="✅")
        st.rerun()
        return

    st.session_state["startup_failed"] = True
    if error is not None:
        logger.warning("Background startup load failed: %s", error)
    # Rerun so the failure panel is rendered by the normal script path, where
    # its button survives polling having stopped.
    st.rerun()


def main():
    st.set_page_config(page_title="CTBeamStudio", page_icon="🏥", layout="wide")

    # Render a lightweight shell first: it is streamed to the browser before
    # the (potentially slow) data loading below, so the page appears instantly.
    shell = st.empty()
    shell.info("⏳ Initialising interface …")

    # Render sidebar and get values
    from visualization.sidebar import render_sidebar

    volume, projection_geometry, n_projections, trajectory_downsample = render_sidebar()

    # Nothing is loaded automatically: the viewer shows the empty state and the
    # user picks image data or the demo phantom. Clear Cache therefore lands in
    # exactly the same state as a fresh start.

    # Show demo mode banner if applicable
    if st.session_state.get("demo_mode"):
        st.info(
            "🏥 **Demo Mode** — Using synthetic Shepp-Logan phantom. "
            "Enter a DICOM folder path in the sidebar to load real data.",
            icon="ℹ️",
        )

    shell.empty()

    tab_view, tab_geometry, tab_compare = st.tabs(
        ["🩻 Viewer", "📐 Geometry", "🔍 Sinogram Inspection"]
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
