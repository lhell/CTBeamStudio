"""NPY loader for CT volume data."""

import numpy as np
from pathlib import Path
from typing import Optional

from visualization.volume import Volume
from visualization.loaders.dicom import _detect_unit


def scan_npy_folder(root: Path) -> list[Path]:
    """Find all .npy files in a folder, sorted numerically.

    Args:
        root: Path to folder containing .npy files.

    Returns:
        List of paths to .npy files, sorted numerically by filename.

    Raises:
        ValueError: If no .npy files found.
    """
    npy_files = sorted(
        [f for f in root.iterdir() if f.suffix == ".npy"],
        key=lambda p: _natural_sort_key(p.name),
    )

    if not npy_files:
        raise ValueError(f"No .npy files found in {root}")

    return npy_files


def _natural_sort_key(s: str) -> tuple:
    """Sort key for natural sorting (slice_1, slice_2, slice_10)."""
    import re

    parts = re.split(r"(\d+)", s)
    return tuple(int(p) if p.isdigit() else p.lower() for p in parts)


def load_npy_series(
    files: list[Path],
    spacing: Optional[tuple[float, float, float]] = None,
    unit: Optional[str] = None,
) -> Volume:
    """Load multiple .npy files and stack into a volume.

    Handles both 2D and 3D input arrays:
    - 2D arrays (y, x) are stacked along z-axis
    - 3D arrays (z, y, x) are concatenated along z-axis

    Args:
        files: List of paths to .npy files.
        spacing: Tuple of (slice_spacing, row_spacing, col_spacing).
        unit: Unit of the data. If None, auto-detected.

    Returns:
        Volume object with stacked data.
    """
    if not files:
        raise ValueError("No files provided")

    if spacing is None:
        spacing = (1.0, 1.0, 1.0)

    arrays = []
    for f in files:
        arr = np.load(f)
        if arr.ndim == 2:
            # 2D -> add z dimension
            arr = arr[np.newaxis, :, :]
        elif arr.ndim == 3:
            # 3D -> keep as is
            pass
        else:
            raise ValueError(f"Expected 2D or 3D array, got {arr.ndim}D in {f.name}")
        arrays.append(arr)

    # Stack/concatenate all arrays
    array = np.concatenate(arrays, axis=0)

    # Detect or use forced unit
    if unit is None:
        detected_unit, detected_slope, detected_intercept, confidence = _detect_unit(array)
        print(f"[load_npy_series] Detected unit: {detected_unit} (confidence: {confidence})")
        print(f"  Data range: [{array.min()}, {array.max()}], dtype: {array.dtype}")
        unit = detected_unit
        rescale_slope = detected_slope
        rescale_intercept = detected_intercept
    else:
        if unit not in ("HU", "1/mm", "1/cm"):
            raise ValueError(f"Invalid unit: {unit}. Must be 'HU', '1/mm', or '1/cm'.")
        rescale_slope = 1.0
        rescale_intercept = -1024 if unit == "HU" else 0

    # Apply rescale
    array = array * rescale_slope + rescale_intercept

    meta = {
        "unit": unit,
        "source_files": [str(f) for f in files],
    }

    return Volume(
        array=array,
        spacing=spacing,
        origin=(0.0, 0.0, 0.0),
        meta=meta,
    )


def load_npy(
    path: Path,
    spacing: Optional[tuple[float, float, float]] = None,
    unit: Optional[str] = None,
) -> Volume:
    """Load a .npy file and return as Volume.

    Args:
        path: Path to .npy file containing 3D array (z, y, x).
        spacing: Tuple of (slice_spacing, row_spacing, col_spacing).
                 If None, defaults to (1.0, 1.0, 1.0).
        unit: Unit of the data. If None, auto-detected.
              Options: "HU", "1/mm", "1/cm".

    Returns:
        Volume object with the CT data.

    Raises:
        ValueError: If array is not 3D.
    """
    if not path.suffix == ".npy":
        raise ValueError(f"Expected .npy file, got {path.suffix}")

    array = np.load(path)

    if array.ndim == 2:
        # 2D -> treat as single slice
        array = array[np.newaxis, :, :]
    elif array.ndim != 3:
        raise ValueError(f"Expected 2D or 3D array, got {array.ndim}D")

    # Default spacing
    if spacing is None:
        spacing = (1.0, 1.0, 1.0)

    # Detect or use forced unit
    if unit is None:
        detected_unit, detected_slope, detected_intercept, confidence = _detect_unit(array)
        print(f"[load_npy] Detected unit: {detected_unit} (confidence: {confidence})")
        print(f"  Using: slope={detected_slope}, intercept={detected_intercept}")
        print(f"  Data range: [{array.min()}, {array.max()}], dtype: {array.dtype}")
        unit = detected_unit
        rescale_slope = detected_slope
        rescale_intercept = detected_intercept
    else:
        # Validate and use forced unit
        if unit not in ("HU", "1/mm", "1/cm"):
            raise ValueError(f"Invalid unit: {unit}. Must be 'HU', '1/mm', or '1/cm'.")
        rescale_slope = 1.0
        if unit == "HU":
            rescale_intercept = -1024
        else:
            rescale_intercept = 0

    # Apply rescale
    array = array * rescale_slope + rescale_intercept

    # Create metadata
    meta = {
        "unit": unit,
        "source_file": str(path),
    }

    return Volume(
        array=array,
        spacing=spacing,
        origin=(0.0, 0.0, 0.0),
        meta=meta,
    )
