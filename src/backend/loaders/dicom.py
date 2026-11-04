"""DICOM loader for CT scans.

This module provides functions to load CT scan data from DICOM files,
convert pixel values to Hounsfield Units (HU), and handle various DICOM
metadata including gantry tilt warnings.

Note:
    Gantry-tilt is not currently corrected. This is a v1 limitation.
    Parallelproj uses Z-axis rotation (unlike RTK which uses Y-axis).

Example:
    >>> from pathlib import Path
    >>> from backend.loaders import scan_series, load_dicom_series
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
from typing import Callable

import numpy as np
import pydicom
from pydicom.dataset import Dataset

from backend.volume import Volume


@dataclass
class SeriesInfo:
    """Information about a DICOM series.

    Attributes:
        series_instance_uid: Unique identifier for the series (SeriesInstanceUID).
        patient_id: Patient identifier (PatientID).
        series_description: Description of the series (SeriesDescription).
        n_slices: Number of slices in the series.
        dose_class: Classification of dose ("full", "quarter", "half", "unknown").
        files: Optional list of file paths (for fast loading).
    """

    series_instance_uid: str
    patient_id: str
    series_description: str
    n_slices: int
    dose_class: str
    files: list[Path] | None = None


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
    # Handle case where attribute is missing
    try:
        position = np.array(ds.ImagePositionPatient)
    except (AttributeError, TypeError):
        # Use zero position as fallback
        position = np.array([0.0, 0.0, 0.0])

    return ds, pixel_array, position


def scan_series(root: Path) -> list[SeriesInfo]:
    """Scan a directory for DICOM series.

    Groups DICOM files by subdirectory (fast) or returns single series.

    Args:
        root: Path to directory containing DICOM files.

    Returns:
        List of SeriesInfo objects, one per series found.
    """
    # Find all DICOM files - non-recursive, just top level
    dicom_files = []
    for ext in ("*.dcm", "*.ima"):
        dicom_files.extend(root.glob(ext))
        dicom_files.extend(root.glob(f"*/{ext}"))  # one level deep

    # Remove duplicates
    dicom_files = list(set(dicom_files))

    if not dicom_files:
        raise ValueError(f"No DICOM files found in {root}")

    # If files are in subdirectories, group by subdirectory
    subdirs: dict[str, list[Path]] = {}
    for f in dicom_files:
        subdir = f.parent.name if f.parent != root else "root"
        if subdir not in subdirs:
            subdirs[subdir] = []
        subdirs[subdir].append(f)

    # Build SeriesInfo - without reading DICOM files
    series_list = []
    for subdir, files in subdirs.items():
        # Use subdir name as series description, or "All Files" for root
        desc = subdir if subdir != "root" else "DICOM Series"
        info = SeriesInfo(
            patient_id="Unknown",
            series_description=desc,
            series_instance_uid=f"local:{subdir}",
            n_slices=len(files),
            dose_class="unknown",
            files=sorted(files),
        )
        series_list.append(info)

    return series_list


def _detect_unit(arrays: np.ndarray) -> tuple[str, float, float, str]:
    """Detect if data is HU or attenuation.

    Returns:
        tuple: (unit, slope, intercept, confidence)
            - unit: "HU" or "1/mm"
            - slope: rescale slope
            - intercept: rescale intercept
            - confidence: "high" or "low"
    """
    min_val = float(arrays.min())
    max_val = float(arrays.max())

    # HU: int16/int32 with large positive values
    if arrays.dtype in (np.int16, np.int32) and max_val > 100:
        return ("HU", 1.0, -1024, "high")

    # Attenuation: float, all positive, max < 10
    if arrays.dtype == np.float32 and min_val >= 0 and max_val < 10:
        return ("1/mm", 1.0, 0, "high")

    # Attenuation: float, all positive, max < 1
    if arrays.dtype == np.float32 and min_val >= 0 and max_val < 1:
        return ("1/mm", 1.0, 0, "high")

    # Default: assume HU with standard CT values
    return ("HU", 1.0, -1024, "low")


def load_dicom_series(
    files: list[Path],
    unit: str = None,
    progress: Callable[[int, int], None] = None,
) -> Volume:
    """Load a DICOM series and return as Volume.

    Sorts slices by their position along the scan axis, validates
    slice spacing consistency, converts pixel values to Hounsfield Units,
    and returns a Volume object.

    Args:
        files: List of paths to DICOM files in the series.
        unit: Optional unit override ("HU", "1/mm", "1/cm").
        progress: Optional callback function(current, total) for progress updates.

    Returns:
        Volume object with the CT data in HU.

    Raises:
        ValueError: If slice spacing varies by more than 1%.
        UserWarning: If gantry tilt is detected (warning only, does not abort).
    """
    if not files:
        raise ValueError("No files provided")

    total_files = len(files)

    # Read all slices and collect metadata
    slices: list[tuple[Dataset, np.ndarray, np.ndarray, Path]] = []

    for i, file_path in enumerate(files, start=1):
        ds, pixel_array, position = _read_dicom_slice(file_path)

        # Report progress
        if progress:
            progress(i, total_files)

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
    try:
        orientation = first_ds.ImageOrientationPatient
    except (AttributeError, TypeError):
        # Default to standard axial orientation
        orientation = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]

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
                    f"Slice spacing inconsistent: {relative_error * 100:.2f}% variance "
                    f"(mean={mean_spacing:.3f}mm). Maximum allowed is 1%."
                )

        # Use mean spacing
        slice_spacing = float(mean_spacing)
    else:
        # Single slice - use default spacing
        slice_spacing = 1.0

    # Get pixel spacing from first slice (in-plane)
    first_ds = slices[0][0]
    try:
        pixel_spacing = first_ds.PixelSpacing  # [row, col] = [y, x]
        row_spacing = float(pixel_spacing[0])
        col_spacing = float(pixel_spacing[1])
    except (AttributeError, TypeError):
        # Default to 1mm pixel spacing
        row_spacing = 1.0
        col_spacing = 1.0

    # Stack pixel arrays into volume (z, y, x)
    array = np.stack(pixel_arrays, axis=0)

    # Detect or use forced unit
    if unit is None:
        detected_unit, detected_slope, detected_intercept, _confidence = _detect_unit(
            array
        )
        unit = detected_unit
        rescale_slope = detected_slope
        rescale_intercept = detected_intercept
    else:
        # Validate and use forced unit
        if unit not in ("HU", "1/mm", "1/cm"):
            raise ValueError(f"Invalid unit: {unit}. Must be 'HU', '1/mm', or '1/cm'.")
        # Use DICOM tags if available, otherwise defaults
        rescale_slope = getattr(first_ds, "RescaleSlope", 1)
        if unit == "HU":
            rescale_intercept = getattr(first_ds, "RescaleIntercept", -1024)
        else:
            rescale_intercept = getattr(first_ds, "RescaleIntercept", 0)

    array = array * rescale_slope + rescale_intercept

    # Ensure correct dtype
    if unit == "HU" and array.dtype != np.int16:
        array = array.astype(np.int16)

    # Get origin from first slice position
    # DICOM position is (x, y, z), Volume expects (x, y, z)
    origin = tuple(positions[0])

    # Build spacing tuple (z, y, x)
    spacing = (slice_spacing, row_spacing, col_spacing)

    # Create metadata
    meta = {
        "unit": unit,
        "series_instance_uid": getattr(first_ds, "SeriesInstanceUID", ""),
        "patient_id": getattr(first_ds, "PatientID", ""),
    }

    return Volume(
        array=array,
        spacing=spacing,
        origin=origin,
        meta=meta,
    )
