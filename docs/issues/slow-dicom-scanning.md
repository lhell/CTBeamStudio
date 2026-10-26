# Slow DICOM Directory Scanning

## Problem
Scanning DICOM directories is significantly slower than the original version that runs on localhost:8501.

## Symptoms
- Scanning takes a long time even for directories that previously loaded quickly
- The slowdown appears to happen before or during the scan process

## What Was Tried
1. Changed from button-click to auto-scan on Enter key press
2. Modified scan_series() to use different directory traversal methods
3. Removed columns layout, simplified UI
4. Restored original sidebar code from git (f9220ea)
5. The scan_series function uses `root.glob()` + `root.glob("*/")` (one level deep), not recursive rglob

## Relevant Files
- `src/visualization/sidebar.py` - Contains the scanning logic and Enter-to-scan
- `src/visualization/loaders/dicom.py` - Contains scan_series() function

## Possible Causes
1. Something in the sidebar rendering is slow before scanning starts
2. The Enter-to-scan trigger might be causing multiple scans or other overhead
3. Session state initialization might be slow
4. Import statements might be slower now

## Original Working Code (f9220ea)
- Sidebar had manual "Scan Directory" button
- scan_series used `root.glob(ext)` + `root.glob(f"*/{ext}")`
- No auto-scan on Enter

## Test Path
`O:\imageDataCT\Laura\data_lowDose_aapm\1mm B30-selected`
