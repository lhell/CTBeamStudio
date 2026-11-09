"""Projection geometry for cone-beam CT data.

This module provides the ProjectionGeometry dataclass for representing
cone-beam CT projection geometry, including loading from YAML and text files.
"""

from dataclasses import dataclass
from math import pi
from pathlib import Path

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    yaml = None  # type: ignore
    YAML_AVAILABLE = False


@dataclass
class ProjectionGeometry:
    """Geometry parameters for cone-beam CT projection data.

    The geometry consists of:
    - Source position (angle + optional offset from central beam)
    - Detector position (defined by central beam + optional independent offset)
    - Detector angles (tilt within/out of plane)

    When source has an offset, the detector follows (stays connected by central beam).
    When detector has an offset, it moves independently of the source.
    """

    # === Angles (degrees) ===

    source_angle: float = 0.0
    """Source position around Z-axis. 0° = anterior, positive = CCW."""

    detector_in_plane_angle: float = 0.0
    """Detector rotation within its plane, stays perpendicular to source ray."""

    detector_out_of_plane_angle: float = 0.0
    """Detector tilt right/left from perpendicular to central beam."""

    detector_tilt_angle: float = 0.0
    """Detector backwards tilt from perpendicular. Positive = tilt backwards."""

    # === Distances (mm) ===

    sdd: float = 1000.0
    """Source-to-detector distance."""

    sid: float = 500.0
    """Source-to-isocenter distance (mm)."""

    # === Detector Properties ===

    n_det_cols: int = 512
    """Number of detector columns."""

    n_det_rows: int = 64
    """Number of detector rows."""

    det_col_spacing_mm: float = 1.0
    """Detector column spacing (mm) - center to center distance."""

    det_row_spacing_mm: float = 1.0
    """Detector row spacing (mm) - center to center distance."""

    detector_shape: str = "flat"
    """Detector shape: 'flat' (planar) or 'curved' (cylindrical)."""

    # === Helical Scan Parameters ===

    pitch: float = 0.0
    """Table feed per gantry rotation / collimation width.

    ``0.0`` means a circular (cone-beam) scan with no table movement, which is
    the default. A non-zero pitch produces a helical trajectory.
    """

    projections_per_rotation: int = 2304
    """Number of projections per 360° gantry rotation."""

    # === Source Offsets (detector FOLLOWS when source moves) ===

    source_offset_x: float = 0.0
    """Source lateral offset (mm) in X direction."""

    source_offset_y: float = 0.0
    """Source longitudinal offset (mm), perpendicular to table."""

    source_offset_z: float = 0.0
    """Source Z offset (mm), table feed direction."""

    # === Detector Offsets (moves INDEPENDENTLY of source) ===

    detector_offset_x: float = 0.0
    """Detector lateral offset (mm), independent of source."""

    detector_offset_y: float = 0.0
    """Detector longitudinal offset (mm), independent of source."""

    # === Metadata ===

    geometry_type: str = "cone_beam"
    """Geometry type: 'cone_beam', 'parallel', 'fan_beam'."""

    source: str = "unknown"
    """Scanner source/manufacturer."""

    def __post_init__(self) -> None:
        """Validate geometry parameters."""
        # Validate distances
        if self.sdd <= 0:
            raise ValueError("sdd must be positive")
        if self.sid <= 0:
            raise ValueError("sid must be positive")
        if self.sid >= self.sdd:
            raise ValueError("sid must be less than sdd")

        # Validate detector properties
        if self.n_det_cols <= 0:
            raise ValueError("n_det_cols must be positive")
        if self.n_det_rows <= 0:
            raise ValueError("n_det_rows must be positive")
        if self.det_col_spacing_mm <= 0:
            raise ValueError("det_col_spacing_mm must be positive")
        if self.det_row_spacing_mm <= 0:
            raise ValueError("det_row_spacing_mm must be positive")

        # Validate pitch. Zero is a circular (cone-beam) scan with no table
        # movement, which is the default; only negative pitch is meaningless.
        if self.pitch < 0:
            raise ValueError("pitch must not be negative")

        # Validate detector shape
        valid_shapes = ("flat", "curved")
        if self.detector_shape not in valid_shapes:
            raise ValueError(f"detector_shape must be one of {valid_shapes}")

    @property
    def collimation_width(self) -> float:
        """Total detector collimation width (mm)."""
        return self.n_det_rows * self.det_row_spacing_mm

    @property
    def fan_angle(self) -> float:
        """Total fan angle (degrees)."""
        return (self.n_det_cols * self.det_col_spacing_mm) / self.sdd * (180 / pi)

    @property
    def cone_angle(self) -> float:
        """Total cone angle (degrees)."""
        return (self.n_det_rows * self.det_row_spacing_mm) / self.sdd * (180 / pi)


def load_geometry(path: Path) -> ProjectionGeometry:
    """Load projection geometry from file (auto-detects format).

    Args:
        path: Path to geometry file (.yaml, .yml, or .txt)

    Returns:
        ProjectionGeometry object with extracted parameters

    Raises:
        ValueError: If the file format is not supported
    """
    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        return load_geometry_from_yaml(path)
    elif suffix == ".txt":
        return load_geometry_from_txt(path)
    else:
        raise ValueError(f"Unsupported geometry file format: {suffix}")


def load_geometry_from_yaml(yaml_path: Path) -> ProjectionGeometry:
    """Load projection geometry from YAML file.

    Args:
        yaml_path: Path to YAML file

    Returns:
        ProjectionGeometry object with extracted parameters

    Raises:
        ImportError: If PyYAML is not installed
    """
    if not YAML_AVAILABLE:
        raise ImportError(
            "PyYAML is required for YAML loading. Install with: pip install pyyaml"
        )
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    return ProjectionGeometry(**data)


def load_geometry_from_txt(txt_path: Path) -> ProjectionGeometry:
    """Load projection geometry from Mayo Clinic format text file.

    Args:
        txt_path: Path to text file

    Returns:
        ProjectionGeometry object with extracted parameters
    """
    # Parse key-value pairs from file
    data = {}

    with open(txt_path) as f:
        content = f.read()

    # Parse the Mayo Clinic format
    # Key patterns like "Anode-to-detector Distance (mm)       1085.6"
    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("-" * 20):
            continue

        # Parse "Key    Value" patterns
        # The format uses spaces to separate key from value
        # Split on the last numeric or decimal value
        parts = line.rsplit(None, 1)
        if len(parts) != 2:
            continue

        key, value = parts

        # Clean up key
        key = key.strip()

        # Try to parse value
        try:
            # Handle tuples like "(369.625, 32.5)"
            if value.startswith("(") and value.endswith(")"):
                # For detector central elements, extract the column value
                inner = value[1:-1]
                vals = inner.split(",")
                if len(vals) == 2:
                    data["det_central_col"] = float(vals[0].strip())
                    data["det_central_row"] = float(vals[1].strip())
                continue

            # Check for string values
            if key.lower().endswith("shape") or key.lower().endswith("geometry"):
                data[key.lower()] = value.strip()
                continue

            # Try numeric
            data[key.lower()] = float(value)
        except ValueError:
            # Store string values as-is
            data[key.lower()] = value

    # Map to ProjectionGeometry fields
    kwargs = {}

    # Map distances
    if "anode-to-detector distance (mm)" in data:
        kwargs["sdd"] = data["anode-to-detector distance (mm)"]
    if "source-to-isocenter distance (mm)" in data:
        kwargs["sid"] = data["source-to-isocenter distance (mm)"]

    # Map detector properties
    if "number of detector rows" in data:
        kwargs["n_det_rows"] = int(data["number of detector rows"])
    if "number of detector columns" in data:
        kwargs["n_det_cols"] = int(data["number of detector columns"])
    if "detector row width (mm)" in data:
        kwargs["det_row_spacing_mm"] = data["detector row width (mm)"]
    if "detector column width (mm)" in data:
        kwargs["det_col_spacing_mm"] = data["detector column width (mm)"]

    # Map detector shape
    if "detector shape" in data:
        shape = data["detector shape"].lower()
        if "flat" in shape:
            kwargs["detector_shape"] = "flat"
        elif "cylind" in shape:
            kwargs["detector_shape"] = "curved"

    # Map geometry type
    if "type of projection geometry" in data:
        geom = data["type of projection geometry"].lower()
        if "cone" in geom:
            kwargs["geometry_type"] = "cone_beam"
        elif "fan" in geom:
            kwargs["geometry_type"] = "fan_beam"
        elif "parallel" in geom:
            kwargs["geometry_type"] = "parallel"

    # Map helical
    if "pitch" in data:
        kwargs["pitch"] = data["pitch"]

    # Map projections per rotation
    if "number of projections per rotation" in data:
        kwargs["projections_per_rotation"] = int(
            data["number of projections per rotation"]
        )

    return ProjectionGeometry(**kwargs)
