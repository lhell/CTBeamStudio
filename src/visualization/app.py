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

import streamlit as st
import streamlit.components.v1 as components

import numpy as np
from scipy.ndimage import zoom

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
    row_sp, col_sp = spacing
    if abs(row_sp - col_sp) < 1e-6:
        return img  # Already isotropic
    # Scale to make voxels square
    scale_factor = row_sp / col_sp
    return zoom(img, (scale_factor, 1.0), order=1)


def setup_image_interaction() -> None:
    """Click image -> focus its slider; arrows/Home/End/Tab navigate slices."""
    js = """
    <script>
    (function () {
      const win = window.parent, doc = win.document;
      const S = (win.__mpr = win.__mpr || { plane: null });
      const ORDER = ['axial', 'coronal', 'sagittal'];
      const COL = '[data-testid="stColumn"], [data-testid="column"]';

      // tear down listeners/observer owned by the PREVIOUS iframe instance
      if (win.__mprCleanup) { try { win.__mprCleanup(); } catch (e) {} }

      function planes() {
        const m = {};
        doc.querySelectorAll('.mpr-anchor[data-plane]').forEach(a => {
          const c = a.closest(COL);
          if (c) m[a.dataset.plane] = c;
        });
        return m;
      }
      const thumbOf = (col) => col && col.querySelector('div[role="slider"]');
      function planeOf(el) {
        const p = planes();
        return ORDER.find(k => p[k] && p[k].contains(el)) || null;
      }

      function paint() {
        const p = planes();
        Object.entries(p).forEach(([name, col]) => {
          const img = col.querySelector('[data-testid="stImage"] img');
          if (img) img.style.outline = (name === S.plane) ? '2px solid #ff4b4b' : 'none';
        });
      }

      function focusPlane(name) {
        const t = thumbOf(planes()[name]);
        if (!t) return false;
        S.plane = name;
        t.focus({ preventScroll: true });
        paint();
        return doc.activeElement === t;
      }

      const onDown = (e) => {
        const img = e.target.closest && e.target.closest('[data-testid="stImage"] img');
        if (!img) return;
        const name = planeOf(img);
        if (!name) return;
        e.preventDefault();          // keep Streamlit from blurring the thumb
        focusPlane(name);
      };

      const onKey = (e) => {
        const name = planeOf(doc.activeElement) || (doc.activeElement === doc.body ? S.plane : null);
        if (!name) return;
        if (e.key === 'Home' || e.key === 'End') {
          const btns = planes()[name].querySelectorAll('[data-testid="stButton"] button');
          const b = e.key === 'Home' ? btns[0] : btns[1];
          if (b) { e.preventDefault(); S.plane = name; b.click(); }
        } else if (e.key === 'Tab') {
          e.preventDefault();
          const step = e.shiftKey ? ORDER.length - 1 : 1;
          focusPlane(ORDER[(ORDER.indexOf(name) + step) % ORDER.length]);
        }
        // arrows: handled natively by the slider thumb
      };

      doc.addEventListener('mousedown', onDown, true);
      doc.addEventListener('keydown', onKey, true);

      let t;
      const obs = new MutationObserver(() => {
        paint();
        clearTimeout(t);
        t = setTimeout(() => {
          if (!S.plane) return;
          const ae = doc.activeElement;
          const parked = !ae || ae === doc.body || ae.tagName === 'HTML'
                      || ae.closest('[data-testid="stButton"]');   // after Home/End click
          if (parked) focusPlane(S.plane);
        }, 60);
      });
      obs.observe(doc.body, { childList: true, subtree: true });

      win.__mprCleanup = () => {
        doc.removeEventListener('mousedown', onDown, true);
        doc.removeEventListener('keydown', onKey, true);
        obs.disconnect();
        clearTimeout(t);
      };

      paint();
      if (S.plane) requestAnimationFrame(() => focusPlane(S.plane));   // survive rerun
    })();
    </script>
    """
    components.html(js, height=0)


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
                    files = selected_series.files[:n_slices] if n_slices else selected_series.files
                else:
                    files = list(Path(data_path).iterdir())[:n_slices] if n_slices else list(Path(data_path).iterdir())

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

        col_preset, col_center, col_width, col_coords = st.columns(4)

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

        with col_coords:
            show_coords = st.checkbox("Show coords", value=False, disabled=True, help="Coords shown on hover")

        # MPR Display - 3 columns
        st.markdown("---")
        st.subheader("MPR Views")

        # Enable hover coordinates (always on now)
        setup_image_interaction()

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
            b_min.button("⏮", key=f"{key}_min", use_container_width=True,
                         on_click=lambda: st.session_state.update({key: 0}))
            b_max.button("⏭", key=f"{key}_max", use_container_width=True,
                         on_click=lambda: st.session_state.update({key: max_idx}))
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
            st.image(axial_windowed, clamp=True, use_container_width=True)

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
            st.image(coronal_resampled, clamp=True, use_container_width=True)

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
            st.image(sagittal_resampled, clamp=True, use_container_width=True)

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
