"""Sinogram / projection-data loader core.

This module provides the foundational data model and selection-resolution
helpers for the sinogram loader. All output arrays are canonical
``(n_proj, n_rows, n_cols)``; selection is always expressed in canonical
order.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal, Optional

import numpy as np
import pydicom


@dataclass
class SelectionConfig:
    """Which detector rows/columns and projections to load.

    Each axis has a mode plus optional parameters:
      - "all":        use every index
      - "central":    a contiguous central band (uses *_range)
      - "range":      indices [start, end) (uses *_range)
      - "downsample": every Nth index (uses *_downsample)
      - "custom":     an explicit index list (uses *_custom)
    """

    # Detector rows (canonical axis 1)
    row_mode: Literal["all", "central", "range", "downsample", "custom"] = "all"
    row_range: Optional[tuple[int, int]] = None
    row_downsample: Optional[int] = None
    row_custom: Optional[list[int]] = None

    # Detector columns (canonical axis 2)
    col_mode: Literal["all", "central", "range", "downsample", "custom"] = "all"
    col_range: Optional[tuple[int, int]] = None
    col_downsample: Optional[int] = None
    col_custom: Optional[list[int]] = None

    # Projections (canonical axis 0)
    proj_mode: Literal["all", "central", "range", "downsample", "custom"] = "all"
    proj_range: Optional[tuple[int, int]] = None
    proj_downsample: Optional[int] = None
    proj_custom: Optional[list[int]] = None


def resolve_indices(
    mode: str,
    size: int,
    range_: Optional[tuple[int, int]] = None,
    downsample: Optional[int] = None,
    custom: Optional[list[int]] = None,
) -> list[int]:
    """Resolve a SelectionConfig axis (mode + params) to an index list.

    Args:
        mode: One of "all", "central", "range", "downsample", "custom".
        size: Length of the axis being selected.
        range_: (start, end) bounds used by "central" and "range".
        downsample: Step used by "downsample".
        custom: Explicit index list used by "custom".

    Returns:
        The resolved list of indices.

    Raises:
        ValueError: If the mode is unknown or the resolved selection is empty.
        IndexError: If any resolved index is out of range for ``size``.
    """
    if mode in ("central", "range"):
        if range_ is None:
            raise ValueError(f"mode '{mode}' requires range_")
        indices = list(range(*range_))
    elif mode == "all":
        indices = list(range(size))
    elif mode == "downsample":
        if downsample is None or downsample <= 0:
            raise ValueError("mode 'downsample' requires a positive downsample step")
        indices = list(range(0, size, downsample))
    elif mode == "custom":
        if custom is None:
            raise ValueError("mode 'custom' requires a custom index list")
        indices = list(custom)
    else:
        raise ValueError(f"Unknown selection mode: {mode!r}")

    if not indices:
        raise ValueError("Selection resolved to an empty result")

    if min(indices) < 0 or max(indices) >= size:
        raise IndexError(f"Selection indices {indices} out of range for size {size}")

    return indices


@dataclass
class SinogramData:
    """Loaded (or lazily-loadable) sinogram / projection data."""

    data: Optional[np.ndarray]  # canonical (n_proj, n_rows, n_cols); None if lazy
    geometry: Optional[object]
    selection: SelectionConfig  # always canonical (proj, row, col)
    original_shape: tuple[int, int, int]  # file's native shape
    source_axis_order: tuple[str, str, str]  # native order, e.g. ("proj", "row", "col")
    path: Optional[Path] = None
    format: str = "unknown"  # "numpy" | "nifti" | "dicom"
    lazy: bool = False
    # Exact files the load read: one path for .npy/.nii, the selected
    # projections' files for a DICOM folder. Lets the UI name its input.
    files: tuple[Path, ...] = ()
    _loader: Optional[Callable[[], np.ndarray]] = None
    # Raw array in the FILE's native order. Held only on a full load so the
    # axis_order change can re-derive in memory; else re-read from `path`.
    _raw_file_order: Optional[np.ndarray] = None
    # Backing field for the ``axis_order`` property; defaults to
    # ``source_axis_order``.
    _axis_order: Optional[tuple[str, str, str]] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._axis_order is None:
            self._axis_order = self.source_axis_order

    @property
    def axis_order(self) -> tuple[str, str, str]:
        """File axis order mapping raw array axes to (proj, row, col)."""
        return self._axis_order

    @axis_order.setter
    def axis_order(self, value: tuple[str, str, str]) -> None:
        """Change the axis mapping; re-derives data for the new order."""
        if not _is_permutation(value):
            raise ValueError(
                f"axis_order must be a permutation of ('proj', 'row', 'col'), got {value!r}"
            )
        self._axis_order = value
        self.source_axis_order = value
        if self._raw_file_order is not None:
            # full in-memory load: re-derive via transpose + re-select (no disk read)
            self.data = _apply_selection(self._raw_file_order, self.selection, value)
            self._loader = None
        else:
            # partial / lazy subset (no raw held): re-read from path with new order
            reloaded = load_sinogram(self.path, self.selection, self.geometry, value)
            self.data = reloaded.data
            self.files = reloaded.files
            self._loader = None

    def materialize(self) -> np.ndarray:
        """Load and cache canonical `data`, then return it."""
        if self.data is not None:
            return self.data
        if self._loader is None:
            raise ValueError("No data and no loader available to materialize")
        self.data = self._loader()
        return self.data


def _is_permutation(value: tuple[str, str, str]) -> bool:
    """Return True if ``value`` is a permutation of ("proj", "row", "col")."""
    if not isinstance(value, tuple) or len(value) != 3:
        return False
    return set(value) == {"proj", "row", "col"}


def _detect_format(path: Path) -> str:
    """Detect the sinogram file format from ``path``.

    Returns one of "dicom", "nifti", "numpy", or "unknown".
    """
    if path.is_dir():
        return "dicom"
    name = path.name
    if name.endswith(".nii.gz"):
        return "nifti"
    if name.endswith((".npy", ".npz")):
        return "numpy"
    if name.endswith(".nii"):
        return "nifti"
    if name.endswith((".dcm", ".dicom")):
        return "dicom"
    return "unknown"


def _apply_selection(raw, selection, axis_order):
    """Transpose raw to canonical (proj,row,col) and apply canonical selection."""
    canonical_tuple = tuple(axis_order.index(label) for label in ("proj", "row", "col"))
    transposed = raw.transpose(canonical_tuple)
    proj_idx = resolve_indices(
        selection.proj_mode,
        transposed.shape[0],
        selection.proj_range,
        selection.proj_downsample,
        selection.proj_custom,
    )
    row_idx = resolve_indices(
        selection.row_mode,
        transposed.shape[1],
        selection.row_range,
        selection.row_downsample,
        selection.row_custom,
    )
    col_idx = resolve_indices(
        selection.col_mode,
        transposed.shape[2],
        selection.col_range,
        selection.col_downsample,
        selection.col_custom,
    )
    return transposed[np.ix_(proj_idx, row_idx, col_idx)]


def _finish_sinogram(
    raw: np.ndarray,
    original_shape: tuple[int, int, int],
    path: Path,
    selection: SelectionConfig,
    axis_order: tuple[str, str, str],
    fmt: str,
    files: tuple[Path, ...] = (),
) -> SinogramData:
    """Transpose ``raw`` to canonical (proj, row, col), apply selection."""
    data = _apply_selection(raw, selection, axis_order)

    # A selection is "full" iff all three modes are "all". When full, hold the
    # raw file-order array so an axis_order change re-derives in memory; else
    # leave it as None so the change re-reads from `path`.
    is_full = (
        selection.row_mode == "all"
        and selection.col_mode == "all"
        and selection.proj_mode == "all"
    )
    raw_file_order = raw if is_full else None

    return SinogramData(
        data=data,
        geometry=None,
        selection=selection,
        original_shape=original_shape,
        source_axis_order=axis_order,
        path=path,
        format=fmt,
        lazy=False,
        _raw_file_order=raw_file_order,
        files=files,
    )


def _load_numpy(
    path: Path,
    selection: SelectionConfig,
    axis_order: tuple[str, str, str],
) -> SinogramData:
    """Load a ``.npy``/``.npz`` sine file into a canonical SinogramData."""
    if path.suffix == ".npz":
        with np.load(path) as zf:
            if "arr_0" in zf:
                raw = zf["arr_0"]
            else:
                raw = zf[zf.files[0]]
    else:
        raw = np.load(path)

    if raw.ndim != 3:
        raise ValueError(
            f"Expected a 3D sinogram array, got {raw.ndim}D array with shape "
            f"{raw.shape} from {path}"
        )

    original_shape = raw.shape
    return _finish_sinogram(
        raw, original_shape, path, selection, axis_order, "numpy", files=(path,)
    )


def _load_nifti(path, selection, axis_order, _on_read=None):
    try:
        import nibabel as nib
    except ImportError:
        raise ImportError(
            "nibabel is required for NIfTI loading. Install with: pip install nibabel"
        )
    img = nib.load(path)
    raw_shape = img.shape
    if len(raw_shape) != 3:
        raise ValueError(f"NIfTI sinogram must be 3D, got {len(raw_shape)}D")
    data = np.asarray(img.dataobj)
    if _on_read is not None:
        _on_read()
    return _finish_sinogram(
        data, raw_shape, path, selection, axis_order, "nifti", files=(path,)
    )


def scan_dicom_sinogram(dir_path: Path) -> dict:
    """Scan a DICOM projection-series directory (header-only, no pixel data).

    Returns a dict with ``n_proj``, ``n_rows``, ``n_cols`` and ``files``
    (sorted list of ``Path``). Raises ``ValueError`` if no DICOM files are
    found.
    """
    dir_path = Path(dir_path)
    # find .dcm/.dicom files in dir (top level)
    dicom_files = sorted(
        [f for f in dir_path.iterdir() if f.suffix.lower() in (".dcm", ".dicom")]
    )
    if not dicom_files:
        raise ValueError(f"No DICOM files found in {dir_path}")
    # read first header for rows/cols
    first = pydicom.dcmread(dicom_files[0], stop_before_pixels=True)
    n_rows = int(first.Rows)
    n_cols = int(first.Columns)
    n_proj = len(dicom_files)
    return {
        "n_proj": n_proj,
        "n_rows": n_rows,
        "n_cols": n_cols,
        "files": dicom_files,
    }


def _load_dicom(path, selection, geometry, axis_order):
    path = Path(path)
    info = scan_dicom_sinogram(path)
    files = info["files"]
    n_proj, n_rows, n_cols = info["n_proj"], info["n_rows"], info["n_cols"]
    # Resolve proj selection in canonical space first (cheap, header-only) and
    # read ONLY the selected projections' pixel arrays (lazy per-request).
    proj_canonical = resolve_indices(
        selection.proj_mode,
        n_proj,
        selection.proj_range,
        selection.proj_downsample,
        selection.proj_custom,
    )
    # Resolve row/col selection once (same per frame).
    row_idx = resolve_indices(
        selection.row_mode,
        n_rows,
        selection.row_range,
        selection.row_downsample,
        selection.row_custom,
    )
    col_idx = resolve_indices(
        selection.col_mode,
        n_cols,
        selection.col_range,
        selection.col_downsample,
        selection.col_custom,
    )
    frames = []
    for idx in proj_canonical:
        ds = pydicom.dcmread(files[idx])
        frame = np.asarray(ds.pixel_array).astype(np.float32)
        # Apply row/col selection to the 2D frame BEFORE stacking (canonical
        # (row, col) in each DICOM frame), then stack along axis 0.
        frame = frame[np.ix_(row_idx, col_idx)]
        frames.append(frame)
    raw = np.stack(frames, axis=0)  # canonical (n_sel_proj, n_sel_row, n_sel_col)

    return SinogramData(
        data=raw,
        geometry=geometry,
        selection=selection,
        original_shape=(n_proj, n_rows, n_cols),
        source_axis_order=("proj", "row", "col"),
        path=path,
        format="dicom",
        lazy=False,
        files=tuple(files[idx] for idx in proj_canonical),
    )


def load_sinogram(
    path,
    selection: Optional[SelectionConfig] = None,
    geometry: Optional[object] = None,
    axis_order: tuple[str, str, str] = ("proj", "row", "col"),
) -> SinogramData:
    """Load a sinogram from ``path``, dispatching on the detected format."""
    path = Path(path)
    fmt = _detect_format(path)

    if fmt == "numpy":
        return _load_numpy(path, selection or SelectionConfig(), axis_order)
    if fmt == "nifti":
        return _load_nifti(path, selection or SelectionConfig(), axis_order)
    if fmt == "dicom":
        return _load_dicom(path, selection or SelectionConfig(), geometry, axis_order)
    raise ValueError(f"Unknown sinogram format for {path}")
