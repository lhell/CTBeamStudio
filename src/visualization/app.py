"""Streamlit app for CT Orientation Viewer."""

import sys
import time
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import streamlit as st

from visualization.loaders.dicom import scan_series, load_dicom_series
from visualization.windowing import apply_window, WINDOW_PRESETS
from visualization.volume import Volume


def main():
    st.set_page_config(
        page_title="CT Orientation Viewer",
        page_icon="🏥",
        layout="wide"
    )
    
    st.title("🏥 CT Orientation Viewer")
    
    # Sidebar: Data selection
    st.sidebar.header("Data")
    
    # Folder picker using text input
    data_path = st.sidebar.text_input(
        "DICOM Folder Path",
        value=r"C:\Users\hellwege\AAPMLowDose\1mm B30-selected\full_1mm\L067\full_1mm",
        help="Enter path to DICOM folder"
    )
    
    # Show file count and options only if nothing loaded yet
    if data_path and Path(data_path).exists() and 'volume' not in st.session_state:
        file_count = len(list(Path(data_path).iterdir()))
        st.sidebar.markdown(f"**Files in directory:** {file_count}")
        
        slice_option = st.sidebar.radio(
            "Slices to load:",
            ["All slices", "Custom number"],
            key="slice_option_init"
        )
        
        n_slices = None
        if slice_option == "Custom number":
            n_slices = st.sidebar.number_input(
                "Number of slices (max " + str(file_count) + ")",
                min_value=1,
                max_value=file_count,
                value=100,
                step=1
            )
        
        st.sidebar.markdown("---")
    else:
        n_slices = None
    
    # Scan button
    scan_button = st.sidebar.button("Scan Directory")
    
    series_list = []
    
    # Check if path exists
    if data_path and Path(data_path).exists() and scan_button:
        try:
            # Show progress bar for scanning
            scan_progress = st.progress(0)
            scan_status = st.empty()
            scan_status.text("Scanning directory...")
            
            # Run scan in background and animate progress
            import threading
            result = [None]
            
            def do_scan():
                result[0] = scan_series(Path(data_path))
            
            scan_thread = threading.Thread(target=do_scan)
            scan_thread.start()
            
            # Animate progress bar while scanning (loop forward only)
            p = 10
            while scan_thread.is_alive():
                scan_progress.progress(p)
                p += 10
                if p > 90:
                    p = 10
                time.sleep(0.3)
            
            scan_thread.join()
            series_list = result[0]
            
            scan_progress.progress(100)
            scan_status.text(f"Scan complete! Found {len(series_list)} series")
            
            if series_list:
                st.sidebar.subheader("Available Series")
                
                # Create selection options
                series_options = [
                    f"{s.series_description or 'Unknown'} - {s.n_slices} slices ({s.dose_class})"
                    for s in series_list
                ]
                selected_idx = st.sidebar.selectbox(
                    "Select Series",
                    range(len(series_options)),
                    format_func=lambda i: series_options[i]
                )
                
                selected_series = series_list[selected_idx]
                
                # Display series info
                st.sidebar.markdown("---")
                st.sidebar.markdown(f"**Patient:** {selected_series.patient_id}")
                st.sidebar.markdown(f"**Slices:** {selected_series.n_slices}")
                st.sidebar.markdown(f"**Dose:** {selected_series.dose_class}")
                
                # Load options
                st.sidebar.markdown("---")
                
                # Show file count
                all_files_in_dir = list(Path(data_path).iterdir())
                file_count = len(all_files_in_dir)
                st.sidebar.markdown(f"**Files in directory:** {file_count}")
                
                st.sidebar.subheader("Load Options")
                
                slice_option = st.sidebar.radio(
                    "Slices to load:",
                    ["All slices", "Custom number"],
                    key="slice_option_load"
                )
                
                n_slices = None
                if slice_option == "Custom number":
                    n_slices = st.sidebar.number_input(
                        "Number of slices (max " + str(file_count) + ")",
                        min_value=1,
                        max_value=file_count,
                        value=100,
                        step=1
                    )
                
                # Load button
                if st.sidebar.button("Load Series"):
                    with st.spinner("Loading DICOM series..."):
                        # Show progress bar
                        # Get files, optionally limited
                        all_files = list(Path(data_path).iterdir())
                        total_files = len(all_files)
                        if n_slices:
                            files = all_files[:n_slices]
                        else:
                            files = all_files
                        
                        # Show progress bar with X/max
                        progress_bar = st.progress(0)
                        
                        # Progress text below bar
                        progress_text = st.container()
                        with progress_text:
                            st.markdown(f"### {len(files)}/{total_files}")
                        
                        status_text = st.empty()
                        status_text.text(f"Loading {len(files)} files...")
                        
                        progress_bar.progress(50)
                        
                        volume = load_dicom_series(files)
                        
                        # Update to show completion
                        progress_bar.progress(100)
                        with progress_text:
                            st.markdown(f"### {len(files)}/{total_files} ✓")
                        status_text.text("Done!")
                        
                        # Show all loaded files in scrollable list
                        st.sidebar.markdown("---")
                        st.sidebar.subheader("Loaded Files")
                        
                        # Create scrollable list using HTML
                        file_list = "<div style='height: 200px; overflow-y: scroll; border: 1px solid #ccc; padding: 5px;'>"
                        for f in files:
                            file_list += f"<div>{f.name}</div>"
                        file_list += "</div>"
                        st.sidebar.markdown(file_list, unsafe_allow_html=True)
                        
                        st.session_state['volume'] = volume
                        st.session_state['series'] = selected_series
                        
                    st.success(f"Loaded {len(files)} slices!")
                
            else:
                st.sidebar.warning("No series found in directory")
                
        except Exception as e:
            st.sidebar.error(f"Error: {str(e)}")
    else:
        st.sidebar.info("Enter a valid folder path")
    
    # Main area
    if 'volume' in st.session_state:
        volume = st.session_state['volume']
        series = st.session_state['series']
        
        st.markdown(f"### {series.series_description or 'CT Scan'}")
        
        # Controls
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Windowing
            window_preset = st.selectbox(
                "Window Preset",
                options=list(WINDOW_PRESETS.keys()),
                index=1  # abdomen default
            )
            center, width = WINDOW_PRESETS[window_preset]
        
        with col2:
            # Slice selector
            slice_idx = st.slider(
                "Slice",
                min_value=0,
                max_value=volume.n_slices - 1,
                value=volume.n_slices // 2
            )
        
        with col3:
            # Display info
            st.markdown(f"**Shape:** {volume.shape}")
            st.markdown(f"**Spacing:** {volume.spacing}")
        
        # Display image
        if slice_idx < volume.array.shape[0]:
            slice_data = volume.array[slice_idx]
            
            # Apply windowing
            windowed = apply_window(slice_data, center, width)
            
            st.image(
                windowed,
                caption=f"Slice {slice_idx + 1}/{volume.n_slices}",
                clamp=True
            )
            
            # Show HU at center
            center_y = volume.array.shape[1] // 2
            center_x = volume.array.shape[2] // 2
            hu_value = volume.array[slice_idx, center_y, center_x]
            st.caption(f"HU at center: {hu_value}")
    
    else:
        # Welcome screen / Demo mode
        st.info("👈 Select a DICOM folder to get started")
        
        st.markdown("""
        ## Features
        
        - **DICOM Loading** - Read CT scans from DICOM files
        - **Windowing** - Presets for lung, abdomen, bone, brain
        - **MPR** - Multi-planar reconstruction (coming soon)
        - **3D View** - Volume visualization (coming soon)
        
        ## Demo Mode
        
        Use the demo phantom to test without real data.
        """)
        
        if st.button("Load Demo Phantom"):
            # TODO: Implement demo phantom
            st.info("Demo phantom coming soon!")


if __name__ == "__main__":
    main()
