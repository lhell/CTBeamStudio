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
        raise IndexError(
            f"Selection indices {indices} out of range for size {size}"
        )

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
        """Change the axis mapping; marks data stale and re-derives."""
        if not _is_permutation(value):
            raise ValueError(
                f"axis_order must be a permutation of ('proj', 'row', 'col'), got {value!r}"
            )
        self._axis_order = value
        # Data is now stale w.r.t. the new axis mapping; clear it and the
        # loader so materialize() re-reads / re-derives.
        self.data = None
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


def _finish_sinogram(
    raw: np.ndarray,
    original_shape: tuple[int, int, int],
    path: Path,
    selection: SelectionConfig,
    axis_order: tuple[str, str, str],
    fmt: str,
) -> SinogramData:
    """Transpose ``raw`` to canonical (proj, row, col), apply selection."""
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
    data = transposed[np.ix_(proj_idx, row_idx, col_idx)]

    return SinogramData(
        data=data,
        geometry=None,
        selection=selection,
        original_shape=original_shape,
        source_axis_order=axis_order,
        path=path,
        format=fmt,
        lazy=False,
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
    return _finish_sinogram(raw, original_shape, path, selection, axis_order, "numpy")


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
        raise NotImplementedError("NIFTI sinogram loading is not yet implemented")
    if fmt == "dicom":
        raise NotImplementedError("DICOM sinogram loading is not yet implemented")
    raise ValueError(f"Unknown sinogram format for {path}")
