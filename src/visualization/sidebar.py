"""Sidebar controls for CTBeamStudio."""

import logging
import tempfile
import uuid
from pathlib import Path

import streamlit as st

from backend.loaders.dicom import scan_series
from backend.loaders.projection import load_projection_geometry
from visualization.background_load import reset_job
from visualization.geometry_cache import (
    clear_cached_geometry,
    default_geometry,
    save_cached_geometry,
)
from visualization.projection_panel import (
    clear_geometry_edit_state,
    render_measurement_sidebar,
)
from visualization.volume_cache import load_volume_cached

logger = logging.getLogger(__name__)


def _series_stub(description: str, patient_id: str, n_slices: int):
    """Minimal stand-in for a DICOM series description."""
    return type(
        "S",
        (),
        {
            "series_description": description,
            "patient_id": patient_id,
            "n_slices": n_slices,
        },
    )()


def render_sidebar():
    """Render the sidebar with data loading and geometry controls.

    Returns:
        tuple: (volume, projection_geometry, n_projections, downsample)
    """
    st.sidebar.title("🏥 CTBeamStudio")

    if st.sidebar.button("🗑️ Clear Cache"):
        # The job registry lives outside session state, so a finished or failed
        # startup job must be dropped explicitly: otherwise the next start would
        # silently no-op and the viewer would stay empty. Read the name before
        # the session-state wipe below removes its token.
        reset_job(startup_job_name())
        # Clear session state. The app then renders its empty state, exactly as
        # on a fresh start: nothing is auto-loaded.
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        # Clear Streamlit cache
        st.cache_data.clear()
        # Clear cache files
        from visualization.volume_cache import clear_last_loaded

        clear_last_loaded()
        clear_cached_geometry()
        st.rerun()

    volume, projection_geometry = _render_image_section()

    projection_geometry, n_projections, downsample = _render_geometry_section(
        projection_geometry
    )

    # Measurements loader (sinogram / projection data)
    render_measurement_sidebar()

    return volume, projection_geometry, n_projections, downsample


def _render_image_section():
    """Render the image/DICOM loading section as a collapsible block.

    Returns:
        tuple: (volume, projection_geometry)
    """
    volume = st.session_state.get("volume")
    projection_geometry = st.session_state.get("projection_geometry")

    with st.sidebar.expander("Image", expanded=True):
        # DICOM folder path
        data_path = st.text_input(
            "DICOM Folder",
            placeholder=r"Your DICOM folder...",
            key="data_path",
        )

        # Initialize session state for series list
        if "series_list" not in st.session_state:
            st.session_state["series_list"] = []
        if "last_scanned_path" not in st.session_state:
            st.session_state["last_scanned_path"] = ""

        # Initial data loading happens in the background (see
        # visualization.background_load), started from app.main() once the
        # shell has been rendered. Loading it here would block the first paint.

        if data_path and Path(data_path).exists():
            # Auto-scan when path changes (Enter key)
            if data_path != st.session_state.get("last_scanned_path"):
                st.session_state["last_scanned_path"] = data_path
                try:
                    with st.spinner("Scanning for DICOM series..."):
                        st.session_state["series_list"] = scan_series(Path(data_path))
                except ValueError as e:
                    if "No DICOM files found" in str(e):
                        st.warning(
                            f"⚠️ No DICOM files found in the selected folder.\n\n"
                            f"**Supported formats:** `.dcm`, `.ima`\n\n"
                            f"**Tip:** Make sure the folder contains DICOM files directly, "
                            f"not just subdirectories."
                        )
                        st.session_state["series_list"] = []
                    else:
                        raise

            series_list = st.session_state.get("series_list") or []
            if series_list:
                series_options = [
                    f"{s.patient_id} - {s.series_description or 'Unknown'} - "
                    f"{s.n_slices} slices"
                    for s in series_list
                ]
                selected_idx = st.selectbox(
                    "Select Series",
                    range(len(series_options)),
                    format_func=lambda i: series_options[i],
                )
                selected_series = series_list[selected_idx]

                # Use n_slices from selected series
                file_count = selected_series.n_slices
                slice_option = st.radio(
                    "Slices to load:",
                    ["All slices", "Custom number"],
                    key="slice_option",
                )
                n_slices = None
                if slice_option == "Custom number":
                    n_slices = st.number_input(
                        f"Number of slices (max {file_count})",
                        min_value=1,
                        max_value=file_count,
                        value=100,
                        key="n_slices_input",
                    )

                if st.button("Load Series"):
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

                    from visualization.volume_cache import save_last_loaded

                    with st.spinner("Loading DICOM series..."):
                        # Convert Path objects to strings for cache key
                        file_paths_str = [str(f) for f in files]

                        # Create progress bar
                        progress_bar = st.progress(0)
                        status_text = st.empty()

                        def update_progress(current: int, total: int):
                            progress_bar.progress(current / total)
                            status_text.text(f"Loading {current}/{total} slices...")

                        # Load with progress callback
                        volume = load_volume_cached(
                            file_paths_str, _progress_callback=update_progress
                        )

                        # Clear progress UI
                        progress_bar.empty()
                        status_text.empty()

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

    return volume, projection_geometry


def _render_geometry_section(projection_geometry):
    """Render the projection-geometry section as a collapsible block.

    Args:
        projection_geometry: Currently active geometry, or None.

    Returns:
        tuple: (projection_geometry, n_projections, downsample)
    """
    with st.sidebar.expander("Projection Geometry", expanded=False):
        geometry_file = st.file_uploader(
            "Geometry file (.txt / .yaml)",
            type=["txt", "yaml", "yml"],
            key="sidebar_geometry_file",
        )

        # Load projection geometry (cache in session state, reload on new upload)
        if geometry_file is not None:
            upload_key = (
                getattr(geometry_file, "name", None),
                getattr(geometry_file, "size", None),
            )
            if st.session_state.get("last_loaded_geometry_key") != upload_key:
                content = geometry_file.read().decode("utf-8")
                suffix = Path(geometry_file.name).suffix.lower() or ".txt"

                # Create temp file with the original suffix so the loader can
                # auto-detect TXT vs YAML.
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=suffix, delete=False
                ) as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name

                try:
                    projection_geometry = load_projection_geometry(tmp_path)
                    st.session_state["projection_geometry"] = projection_geometry
                    st.session_state["geometry_loaded_original"] = projection_geometry
                    st.session_state["last_loaded_geometry_key"] = upload_key
                    st.session_state["geometry_is_default"] = False
                    save_cached_geometry(projection_geometry)
                    clear_geometry_edit_state()
                    st.success("Geometry loaded!")
                except Exception as e:
                    st.error(f"Failed to load geometry: {e}")
                finally:
                    import os

                    os.unlink(tmp_path)
            else:
                projection_geometry = st.session_state.get("projection_geometry")
        else:
            projection_geometry = st.session_state.get("projection_geometry")

        # Always show a geometry: restore the cached one or use the defaults.
        if projection_geometry is None:
            projection_geometry = default_geometry()
            st.session_state["projection_geometry"] = projection_geometry
            st.session_state["geometry_loaded_original"] = projection_geometry
            st.session_state["geometry_is_default"] = True
            st.caption("No geometry file loaded — showing the default geometry.")

        # One full rotation by default: a circular scan acquires exactly
        # ``projections_per_rotation`` views. The widget has a key, so its
        # value must be seeded through session state to make the geometry the
        # default rather than a hardcoded number.
        if "sidebar_n_projections" not in st.session_state:
            st.session_state["sidebar_n_projections"] = int(
                projection_geometry.projections_per_rotation
            )

        n_projections = st.number_input(
            "Projections",
            min_value=1,
            step=100,
            key="sidebar_n_projections",
        )
        downsample_options = [10, 50, 100, 200, 500]
        downsample = st.selectbox(
            "Trajectory Downsample",
            options=downsample_options,
            # Default 1/100: one marker and one detector plane per hundred
            # projections. At 1/10 the ring turns into a dense band of ~230
            # planes, which hides the volume and costs a trace per plane.
            index=downsample_options.index(100),
            format_func=lambda x: f"1/{x}",
            key="sidebar_downsample",
        )

    return projection_geometry, n_projections, downsample


def startup_job_name() -> str:
    """Return this session's startup job name.

    The registry is process-global, so a single fixed name would make every
    session after the first observe the previous session's finished job and
    skip loading entirely. Each session therefore gets its own job, which is
    also what it needs: the resulting volume lives in that session's state.
    """
    token = st.session_state.get("startup_job_token")
    if token is None:
        token = uuid.uuid4().hex
        st.session_state["startup_job_token"] = token
    return f"startup-{token}"


def create_demo_volume_job():
    """Return a callable that builds the demo phantom.

    Kept free of Streamlit calls so it can run in a worker thread: the caller
    stores the returned ``Volume`` in session state from the main script.
    """
    from visualization.phantom import create_demo_volume

    def build():
        return create_demo_volume()

    return build


def should_startup_load() -> bool:
    """Whether the app loads data automatically on start.

    Always ``False``: startup shows the empty state and the user picks image
    data or the demo phantom. Kept as a function so the policy lives in one
    place and has a test.
    """
    return False


def load_demo_volume():
    """Load the synthetic demo phantom into session state."""
    from visualization.phantom import create_demo_volume

    volume = create_demo_volume()
    st.session_state["volume"] = volume
    st.session_state["demo_mode"] = True
    st.session_state["series"] = _series_stub(
        "Demo Phantom (Shepp-Logan)", "Demo", volume.n_slices
    )
    st.toast("Loaded demo phantom!")
    return volume
