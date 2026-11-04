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
