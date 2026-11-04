# Projection Geometry Design Specification

**Date:** 2026-10-26  
**Status:** Draft  
**Author:** CTBeamStudio Team

## 1. Overview

This spec defines the `ProjectionGeometry` class for representing cone-beam CT projection geometry. The class will be used for loading projection data from DICOM/text files and providing geometry parameters for reconstruction algorithms.

### Goals

- Define a clear, consistent geometry model for cone-beam CT projection data
- Support both standard and offset geometries (source/detector misalignments)
- Provide easy-to-use interface for accessing all geometry parameters
- Enable loading from file formats (text summary + DICOM)

### Scope

- Create `ProjectionGeometry` dataclass in `src/visualization/geometry.py`
- Create loader to extract geometry from `.txt` files
- Integrate with existing volume visualization code

## 2. Coordinate System

### Axes

| Axis | Direction |
|------|-----------|
| **Z** | Table feed direction (patient longitudinal, head-to-feet) |
| **X** | Patient lateral (right/left when supine) |
| **Y** | Anterior/posterior (front/back of patient) |

### Source Rotation

- **Reference:** 0° = anterior (front of patient, +X direction)
- **Positive direction:** Counter-clockwise when viewed from above (+Z)

## 3. Class Design

### ProjectionGeometry Dataclass

```python
from dataclasses import dataclass
from typing import Optional

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
    
    pitch: float = 1.0
    """Table feed per gantry rotation / collimation width."""
    
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
    
    detector_shape: str = "flat"
    """Detector shape: 'flat' (planar) or 'curved' (cylindrical)."""
    
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
        
        # Validate pitch
        if self.pitch <= 0:
            raise ValueError("pitch must be positive")
        
        # Validate detector shape
        valid_shapes = ("flat", "curved")
        if self.detector_shape not in valid_shapes:
            raise ValueError(f"detector_shape must be one of {valid_shapes}")
    
    @property
    def sid(self) -> float:
        """Source-to-isocenter distance."""
        return self._sid
    
    @sid.setter
    def sid(self, value: float) -> None:
        """Set source-to-isocenter distance."""
        self._sid = value
    
    @property
    def collimation_width(self) -> float:
        """Total detector collimation width (mm)."""
        return self.n_det_rows * self.det_row_spacing_mm
    
    @property
    def fan_angle(self) -> float:
        """Total fan angle (degrees)."""
        return (self.n_det_cols * self.det_col_spacing_mm) / self.sdd * (180 / 3.14159265)
    
    @property
    def cone_angle(self) -> float:
        """Total cone angle (degrees)."""
        return (self.n_det_rows * self.det_row_spacing_mm) / self.sdd * (180 / 3.14159265)
```

## 4. File Loader

### Supported Formats

The loader supports both YAML and TXT formats:

- **YAML** (`.yaml`, `.yml`): Recommended for new files
- **TXT** (`.txt`): Backwards compatibility with Mayo Clinic format

### YAML Format

```yaml
# CT Projection Geometry
geometry_type: cone_beam
detector_shape: flat

# Distances (mm)
sdd: 1085.6
sid: 600.0

# Detector
n_det_cols: 736
n_det_rows: 64
det_col_spacing_mm: 1.2858
det_row_spacing_mm: 1.0947

# Angles (degrees)
source_angle: 0.0
detector_in_plane_angle: 0.0
detector_out_of_plane_angle: 0.0
detector_tilt_angle: 0.0

# Helical
pitch: 0.8

# Offsets (mm)
source_offset_x: 0.0
source_offset_y: 0.0
source_offset_z: 0.0
detector_offset_x: 0.0
detector_offset_y: 0.0
```

### TXT Format (Mayo Clinic)

The loader parses geometry from text files with the following format:

```
GANTRY GEOMETRY -------------------------------------------------
                       Detector Shape       CYLINDRICAL
          Type of Projection Geometry       FANBEAM
      Anode-to-detector Distance (mm)       1085.6
                  Number of Detector Rows   64
               Number of Detector Columns   736
            Detector Row Width (mm)         1.0947
         Detector Column Width (mm)         1.2858
     Detector Central Elements (Col, Row)  (369.625, 32.5)

ACQUISITION -----------------------------------------------------
                                      Pitch  0.8
                         Rotation Time (ms)  500
```

### Loader Functions

```python
def load_geometry(path: Path) -> ProjectionGeometry:
    """Load projection geometry from file (auto-detects format).
    
    Args:
        path: Path to geometry file (.yaml, .yml, or .txt)
        
    Returns:
        ProjectionGeometry object with extracted parameters
    """
    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        return load_geometry_from_yaml(path)
    elif suffix == ".txt":
        return load_geometry_from_txt(path)
    else:
        raise ValueError(f"Unsupported geometry file format: {suffix}")


def load_geometry_from_yaml(yaml_path: Path) -> ProjectionGeometry:
    """Load projection geometry from YAML file."""
    import yaml
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    return ProjectionGeometry(**data)


def load_geometry_from_txt(txt_path: Path) -> ProjectionGeometry:
    """Load projection geometry from text summary file."""
    # Parse key-value pairs from file
    # Map to ProjectionGeometry fields
    # Return geometry object
```

## 5. Integration

### File Structure

```
src/visualization/
├── geometry.py          # NEW: ProjectionGeometry class
├── loaders/
│   ├── dicom.py         # Existing DICOM loader
│   ├── npy.py           # Existing NumPy loader
│   └── projection.py    # NEW: Projection data loader
```

### Usage Example

```python
from src.visualization.geometry import ProjectionGeometry

# Create from file
geometry = load_geometry_from_txt(Path("geometry.txt"))

# Access properties
print(f"SDD: {geometry.sdd} mm")
print(f"Fan angle: {geometry.fan_angle:.2f}°")
print(f"Cone angle: {geometry.cone_angle:.2f}°")

# Create manually
geometry = ProjectionGeometry(
    source_angle=45.0,
    sdd=1085.6,
    sid=600.0,
    n_det_cols=736,
    n_det_rows=64,
    det_col_spacing_mm=1.2858,
    det_row_spacing_mm=1.0947,
    pitch=0.8
)
```

## 6. Acceptance Criteria

1. **ProjectionGeometry class** can be instantiated with default or custom values
2. **Validation** catches invalid parameters (negative distances, etc.)
3. **Computed properties** (collimation_width, fan_angle, cone_angle) work correctly
4. **Text loader** parses the sample geometry file correctly
5. **Documentation** in `docs/geometry.md` matches the implementation
6. **Backwards compatibility** with existing geometry handling in volume3d.py

## 7. Out of Scope

- DICOM private tag parsing (future enhancement)
- Reconstruction algorithms (separate project)
- Projection data visualization (future enhancement)
- Multiple geometry support per scan (future enhancement)
- Curved detector geometry (future enhancement)

## 8. Future: Curved Detector Support

Future enhancement to support cylindrical/curved detectors:

### Changes Needed

1. **New field**: `detector_radius` — curvature radius (mm), only used when `detector_shape = "curved"`

2. **Computed changes**:
   - `fan_angle` computed from arc length: `n_det_cols * det_col_spacing_mm / detector_radius`
   - `cone_angle` computed from arc length: `n_det_rows * det_row_spacing_mm / detector_radius`

3. **Position calculations**:
   - Detector positions computed using cylindrical coordinates
   - Need to handle conversion between flat and curved detector geometries

### Example Curved Geometry

```python
geometry = ProjectionGeometry(
    sdd=1085.6,
    sid=600.0,
    n_det_cols=736,
    n_det_rows=64,
    det_col_spacing_mm=1.2858,
    det_row_spacing_mm=1.0947,
    detector_shape="curved",
    detector_radius=538.0,  # ~half of SDD for curved detector
)
```
