"""Sidebar controls for CT Orientation Viewer."""

import logging
import tempfile
from pathlib import Path

import streamlit as st

from visualization.loaders.dicom import scan_series
from visualization.loaders.projection import load_projection_geometry

logger = logging.getLogger(__name__)


def render_sidebar():
    """Render the sidebar with data loading and geometry controls.

    Returns:
        tuple: (volume, projection_geometry, n_projections, downsample)
    """
    st.sidebar.title("🏥 CT Orientation Viewer")

    st.sidebar.header("Data")

    # DICOM folder path
    data_path = st.sidebar.text_input(
        "DICOM Folder",
        placeholder=r"O:\imageDataCT\projects\...",
        key="data_path",
    )

    # Initialize session state for series list
    if "series_list" not in st.session_state:
        st.session_state["series_list"] = []

    projection_geometry = st.session_state.get("projection_geometry")
    n_projections = st.session_state.get("sidebar_n_projections", 51326)
    downsample = st.session_state.get("sidebar_downsample", 10)
    volume = st.session_state.get("volume")

    if data_path and Path(data_path).exists():
        if st.sidebar.button("Scan Directory"):
            with st.spinner("Scanning for DICOM series..."):
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

                from visualization.volume_cache import (
                    load_volume_cached,
                    save_last_loaded,
                )

                with st.spinner("Caching volume..."):
                    # Convert Path objects to strings for cache key
                    file_paths_str = [str(f) for f in files]

                    # Create progress bar
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    def update_progress(current: int, total: int):
                        progress_bar.progress(current / total)
                        status_text.text(f"Loading {current}/{total} slices...")

                    # Load with progress callback
                    volume = load_volume_cached(file_paths_str, _progress_callback=update_progress)

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

    # Projection geometry file (sidebar)
    st.sidebar.markdown("---")
    st.sidebar.subheader("Projection Geometry")
    geometry_file = st.sidebar.file_uploader(
        "Geometry TXT file", type=["txt"], key="sidebar_geometry_file"
    )

    # Load projection geometry (cache in session state)
    # Check if we already have cached geometry
    if st.session_state.get("projection_geometry") is not None:
        # Use cached geometry
        projection_geometry = st.session_state.get("projection_geometry")
    elif geometry_file is not None:
        # Save uploaded file to temporary path
        content = geometry_file.read().decode("utf-8")

        # Create temp file for loader
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            projection_geometry = load_projection_geometry(tmp_path)
            st.session_state["projection_geometry"] = projection_geometry
            st.sidebar.success("Geometry loaded!")
        except Exception as e:
            st.sidebar.error(f"Failed to load geometry: {e}")
            projection_geometry = None
        finally:
            import os

            os.unlink(tmp_path)

    n_projections = st.sidebar.number_input(
        "Projections",
        min_value=1,
        value=51326,
        step=1000,
        key="sidebar_n_projections",
    )
    trajectory_downsample = st.sidebar.selectbox(
        "Trajectory Downsample",
        options=[1, 10, 100, 1000],
        index=1,
        format_func=lambda x: f"1/{x}",
        key="sidebar_trajectory_downsample",
    )

    # Clear cache button
    st.sidebar.markdown("---")
    if st.sidebar.button("🗑️ Clear Cache"):
        # Clear session state
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        # Clear Streamlit cache
        st.cache_data.clear()
        # Clear cache file
        from visualization.volume_cache import clear_last_loaded

        clear_last_loaded()
        st.rerun()

    return volume, projection_geometry, n_projections, trajectory_downsample
