"""DICOM loader for CT scans.

This module provides functions to load CT scan data from DICOM files,
convert pixel values to Hounsfield Units (HU), and handle various DICOM
metadata including gantry tilt warnings.

Note:
    Gantry-tilt is not currently corrected. This is a v1 limitation.
    Parallelproj uses Z-axis rotation (unlike RTK which uses Y-axis).

Example:
    >>> from pathlib import Path
    >>> from src.visualization.loaders import scan_series, load_dicom_series
    >>>
    >>> # Scan directory for series
    >>> series_list = scan_series(Path("path/to/dicom/dir"))
    >>>
    >>> # Load first series
    >>> if series_list:
    ...     volume = load_dicom_series([...list of file paths...])
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pydicom
from pydicom.dataset import Dataset

from visualization.volume import Volume


@dataclass
class SeriesInfo:
    """Information about a DICOM series.

    Attributes:
        series_instance_uid: Unique identifier for the series (SeriesInstanceUID).
        patient_id: Patient identifier (PatientID).
        series_description: Description of the series (SeriesDescription).
        n_slices: Number of slices in the series.
        dose_class: Classification of dose ("full", "quarter", "half", "unknown").
    """

    series_instance_uid: str
    patient_id: str
    series_description: str
    n_slices: int
    dose_class: str


def classify_dose(series_description: str) -> str:
    """Classify dose from series description.

    Args:
        series_description: The SeriesDescription from DICOM header.

    Returns:
        "quarter" for quarter-dose scans,
        "half" for half-dose scans,
        "full" for full-dose or standard scans,
        "unknown" otherwise.
    """
    if not series_description:
        return "unknown"

    desc_lower = series_description.lower()

    if "quarter" in desc_lower:
        return "quarter"
    elif "half" in desc_lower:
        return "half"
    elif "full" in desc_lower or "standard" in desc_lower:
        return "full"
    else:
        return "unknown"


def _check_gantry_tilt(ds: Dataset) -> bool:
    """Check if gantry tilt is present.

    Checks both GantryDetectorTilt and ImageOrientationPatient for signs
    of gantry tilt.

    Args:
        ds: pydicom Dataset.

    Returns:
        True if gantry tilt is detected, False otherwise.
    """
    # Check GantryDetectorTilt attribute
    if hasattr(ds, "GantryDetectorTilt") and ds.GantryDetectorTilt != 0:
        return True

    # Check ImageOrientationPatient for non-axial orientation
    # Standard axial: [1, 0, 0, 0, 1, 0] (row along X, col along Y)
    if hasattr(ds, "ImageOrientationPatient"):
        orientation = ds.ImageOrientationPatient
        # Allow small tolerance for floating point
        expected = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        tolerance = 1e-6
        for actual, exp in zip(orientation, expected):
            if abs(actual - exp) > tolerance:
                return True

    return False


def _calculate_normal_from_orientation(orientation: list[float]) -> np.ndarray:
    """Calculate normal vector from ImageOrientationPatient.

    The normal is the cross product of the row direction cosine and
    the column direction cosine.

    Args:
        orientation: ImageOrientationPatient [row_x, row_y, row_z, col_x, col_y, col_z].

    Returns:
        Normal vector as numpy array.
    """
    row_direction = np.array(orientation[:3])
    col_direction = np.array(orientation[3:])
    normal = np.cross(row_direction, col_direction)
    return normal


def _read_dicom_slice(file_path: Path) -> tuple[Dataset, np.ndarray, np.ndarray]:
    """Read a DICOM slice and extract necessary metadata.

    Args:
        file_path: Path to DICOM file.

    Returns:
        Tuple of (dataset, pixel_array, position).
    """
    ds = pydicom.dcmread(file_path)
    pixel_array = ds.pixel_array.astype(np.float32)

    # Get ImagePositionPatient [x, y, z]
    position = np.array(ds.ImagePositionPatient)

    return ds, pixel_array, position


def scan_series(root: Path) -> list[SeriesInfo]:
    """Scan a directory for DICOM series.

    Groups DICOM files by SeriesInstanceUID and returns information
    about each series found.

    Args:
        root: Path to directory containing DICOM files.

    Returns:
        List of SeriesInfo objects, one per series found.

    Raises:
        ValueError: If directory is empty or contains no valid DICOM files.
    """
    # Find all DICOM files in directory
    dicom_files = []
    for ext in ("*.dcm", "*.ima"):
        dicom_files.extend(root.glob(f"**/{ext}"))

    # Remove duplicates (same file might be found via multiple patterns)
    dicom_files = list(set(dicom_files))

    if not dicom_files:
        raise ValueError(f"No DICOM files found in {root}")

    # Group by SeriesInstanceUID
    series_dict: dict[str, list[Path]] = {}

    for file_path in dicom_files:
        try:
            ds = pydicom.dcmread(file_path)
            if hasattr(ds, "SeriesInstanceUID"):
                uid = ds.SeriesInstanceUID
                if uid not in series_dict:
                    series_dict[uid] = []
                series_dict[uid].append(file_path)
        except Exception:
            # Skip invalid DICOM files
            continue

    if not series_dict:
        raise ValueError(f"No valid DICOM series found in {root}")

    # Build SeriesInfo for each series
    series_list = []
    for uid, files in series_dict.items():
        # Read first file to get metadata
        ds = pydicom.dcmread(files[0])

        patient_id = getattr(ds, "PatientID", "UNKNOWN")
        series_description = getattr(ds, "SeriesDescription", "")

        dose_class = classify_dose(series_description)

        series_info = SeriesInfo(
            series_instance_uid=uid,
            patient_id=patient_id,
            series_description=series_description,
            n_slices=len(files),
            dose_class=dose_class,
        )
        series_list.append(series_info)

    return series_list


def load_dicom_series(files: list[Path]) -> Volume:
    """Load a DICOM series and return as Volume.

    Sorts slices by their position along the scan axis, validates
    slice spacing consistency, converts pixel values to Hounsfield Units,
    and returns a Volume object.

    Args:
        files: List of paths to DICOM files in the series.

    Returns:
        Volume object with the CT data in HU.

    Raises:
        ValueError: If slice spacing varies by more than 1%.
        UserWarning: If gantry tilt is detected (warning only, does not abort).
    """
    if not files:
        raise ValueError("No files provided")

    # Read all slices and collect metadata
    slices: list[tuple[Dataset, np.ndarray, np.ndarray, Path]] = []

    for file_path in files:
        ds, pixel_array, position = _read_dicom_slice(file_path)

        # Check for gantry tilt
        if _check_gantry_tilt(ds):
            warnings.warn(
                f"Gantry tilt detected in {file_path.name}. "
                "Gantry tilt correction is not implemented in v1. "
                "This may cause inaccurate positioning.",
                UserWarning,
                stacklevel=2,
            )

        slices.append((ds, pixel_array, position, file_path))

    # Get orientation from first slice to calculate normal
    first_ds = slices[0][0]
    if not hasattr(first_ds, "ImageOrientationPatient"):
        raise ValueError("ImageOrientationPatient not found in DICOM")

    orientation = first_ds.ImageOrientationPatient
    normal = _calculate_normal_from_orientation(orientation)

    # Sort slices by position projected onto normal (ascending)
    def get_projected_position(item: tuple) -> float:
        _, _, position, _ = item
        return float(np.dot(position, normal))

    slices.sort(key=get_projected_position)

    # Extract pixel arrays and positions
    pixel_arrays = [s[1] for s in slices]
    positions = [s[2] for s in slices]

    # Calculate slice spacing from sorted positions
    n_slices = len(positions)
    if n_slices > 1:
        # Project differences onto normal
        spacing_values = []
        for i in range(1, n_slices):
            diff = positions[i] - positions[i - 1]
            spacing = abs(np.dot(diff, normal))
            spacing_values.append(spacing)

        # Check spacing consistency (>1% variance)
        mean_spacing = np.mean(spacing_values)
        if mean_spacing > 0:
            max_deviation = max(abs(s - mean_spacing) for s in spacing_values)
            relative_error = max_deviation / mean_spacing

            if relative_error > 0.01:
                raise ValueError(
                    f"Slice spacing inconsistent: {relative_error*100:.2f}% variance "
                    f"(mean={mean_spacing:.3f}mm). Maximum allowed is 1%."
                )

        # Use mean spacing
        slice_spacing = float(mean_spacing)
    else:
        # Single slice - use default spacing
        slice_spacing = 1.0

    # Get pixel spacing from first slice (in-plane)
    first_ds = slices[0][0]
    pixel_spacing = first_ds.PixelSpacing  # [row, col] = [y, x]
    row_spacing = float(pixel_spacing[0])
    col_spacing = float(pixel_spacing[1])

    # Stack pixel arrays into volume (z, y, x)
    array = np.stack(pixel_arrays, axis=0)

    # Convert to HU: hu = pixel_value * RescaleSlope + RescaleIntercept
    rescale_slope = getattr(first_ds, "RescaleSlope", 1)
    rescale_intercept = getattr(first_ds, "RescaleIntercept", -1024)

    array = array * rescale_slope + rescale_intercept

    # Ensure correct dtype
    if array.dtype != np.int16:
        array = array.astype(np.int16)

    # Get origin from first slice position
    # DICOM position is (x, y, z), Volume expects (x, y, z)
    origin = tuple(positions[0])

    # Build spacing tuple (z, y, x)
    spacing = (slice_spacing, row_spacing, col_spacing)

    # Create metadata
    meta = {
        "unit": "HU",
        "series_instance_uid": getattr(first_ds, "SeriesInstanceUID", ""),
        "patient_id": getattr(first_ds, "PatientID", ""),
    }

    return Volume(
        array=array,
        spacing=spacing,
        origin=origin,
        meta=meta,
    )
