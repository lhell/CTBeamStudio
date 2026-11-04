"""Volume dataclass for CT data exchange."""

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class Volume:
    """Container for CT volume data in HU or attenuation values.

    Supports:
    - 2D (single slice): (y, x)
    - 3D (volume): (z, y, x)

    Attributes:
        array: 2D or 3D numpy array with attenuation values (HU or linear).
        spacing: Pixel spacing in mm. Must match array dimensions:
            - 2D: (row_spacing, col_spacing)
            - 3D: (z_spacing, row_spacing, col_spacing)
        origin: DICOM origin coordinates (x, y, z) or (x, y) for 2D.
        meta: Optional metadata dictionary. Use meta["unit"] to store the unit
            (e.g., "HU", "1/mm", "1/cm").

    Note:
        Volume is unit-agnostic (HU, attenuation, or other).
        Loaders are responsible for correct unit conversion and validation.
    """

    array: np.ndarray
    spacing: tuple[float, ...]
    origin: tuple[float, ...]
    meta: Optional[dict] = None

    def __post_init__(self) -> None:
        """Validate volume after initialization."""
        ndim = self.array.ndim

        # Validate array dimensions (2D or 3D only)
        if ndim not in (2, 3):
            raise ValueError(f"array must be 2D or 3D, got {ndim}D")

        # Validate array dtype (CT attenuation values)
        allowed_dtypes = (np.int16, np.uint16, np.float32)
        if self.array.dtype not in allowed_dtypes:
            raise ValueError(
                f"array must be int16, uint16, or float32, got {self.array.dtype}"
            )

        # Note: Negative values are allowed (e.g., HU for air = -1000).
        # Volume is unit-agnostic; loaders handle validation.

        # Validate spacing matches array dimensions
        if len(self.spacing) != ndim:
            raise ValueError(
                f"spacing length ({len(self.spacing)}) must match array "
                f"dimensions ({ndim})"
            )

        # Validate spacing values are positive and finite
        for i, s in enumerate(self.spacing):
            if s <= 0:
                raise ValueError(f"spacing[{i}] must be positive, got {s}")
            if not np.isfinite(s):
                raise ValueError(f"spacing[{i}] must be finite, got {s}")

        # Validate origin matches array dimensions
        if len(self.origin) != ndim:
            raise ValueError(
                f"origin length ({len(self.origin)}) must match array "
                f"dimensions ({ndim})"
            )

    @property
    def shape(self) -> tuple[int, ...]:
        """Return array shape."""
        return tuple(self.array.shape)

    @property
    def ndim(self) -> int:
        """Return number of dimensions."""
        return self.array.ndim

    @property
    def n_slices(self) -> int:
        """Return number of axial slices (3D only)."""
        if self.array.ndim == 2:
            return 1
        return self.array.shape[0]
