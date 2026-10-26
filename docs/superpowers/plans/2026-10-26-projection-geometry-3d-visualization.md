# Projection Geometry 3D Visualization Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Load projection geometry from user files and visualize the source/detector in the 3D surface plot.

**Architecture:** Extend the existing 3D visualization in volume3d.py to accept ProjectionGeometry and render source/detector based on the loaded geometry parameters (angles, offsets, detector size).

**Tech Stack:** Python, PyVista/Plotly for 3D, existing ProjectionGeometry class

**Spec:** `docs/superpowers/specs/2026-10-26-projection-geometry-design.md`, `docs/geometry.md`

---

## Global Constraints

- Use existing ProjectionGeometry class from src/visualization/geometry.py
- Source angle 0° = anterior, positive = CCW
- Detector default: perpendicular to source ray
- All angles in degrees, distances in mm

---

## Review Focus

- **Multiple projections:** 51,326 projections - must downsample for performance
- **Downsample dropdown:** N = 1000, 100, 10, 1 (show every Nth projection)
- **Coordinate transformation:** sourceAngle rotates around Z, offsets move source relative to central beam
- **Detector sizing:** Use n_det_cols, n_det_rows, det_col_spacing_mm, det_row_spacing_mm
- **Curved detector:** Currently flat only - for curved data, use flat approximation or skip
- **Helical source_z:** Compute from pitch and source angle

---

## Task 1: Create Geometry Loader for User Files

**Files:**
- Create: `src/visualization/loaders/projection.py`
- Modify: `src/visualization/loaders/__init__.py` (if exists)

**Interfaces:**
- Produces: `load_projection_geometry(txt_path) -> ProjectionGeometry`

> Note: The TXT file contains all geometry info. DICOM loading is out of scope.

- [ ] **Step 1: Create loader module**

```python
# src/visualization/loaders/projection.py
from pathlib import Path
from visualization.geometry import ProjectionGeometry, load_geometry_from_txt


def load_projection_geometry(txt_path: Path) -> ProjectionGeometry:
    """Load projection geometry from text file.
    
    Args:
        txt_path: Path to geometry text file
        
    Returns:
        ProjectionGeometry object
    """
    # Use existing TXT loader for geometry
    geometry = load_geometry_from_txt(txt_path)
    return geometry
```

- [ ] **Step 2: Test the loader**

```python
# Test with user's files
from pathlib import Path
from visualization.loaders.projection import load_projection_geometry

txt = Path("O:/imageDataCT/Laura/data_lowDose_aapm/projection_data/L506/DICOM-CT-PD_QD/L506_4L_100kv_quarterdose1.txt")

geo = load_projection_geometry(txt)
print(f"SDD: {geo.sdd}, SID: {geo.sid}")
print(f"Detector: {geo.n_det_cols} x {geo.n_det_rows}")
```

- [ ] **Step 3: Commit**

```bash
git add src/visualization/loaders/projection.py
git commit -m "feat: add projection geometry loader"
```

---

## Task 2: Add Geometry-Based Source/Detector to 3D Plot

**Files:**
- Modify: `src/visualization/volume3d.py`

**Interfaces:**
- Consumes: `ProjectionGeometry` from Task 1, source_angle value
- Produces: Updated 3D visualization showing source/detector from geometry

- [ ] **Step 1: Add function to calculate source position from ProjectionGeometry**

```python
def get_source_position(geometry: ProjectionGeometry, source_angle: float = 0.0) -> tuple[float, float, float]:
    """Calculate source position from ProjectionGeometry.
    
    Args:
        geometry: ProjectionGeometry object
        source_angle: Current source angle in degrees
        
    Returns:
        (x, y, z) source position in mm
    """
    import math
    angle_rad = math.radians(source_angle)
    
    # Base position: on circle at SID distance, at anterior (0°) = +X direction
    base_x = geometry.sid * math.cos(angle_rad)
    base_y = geometry.sid * math.sin(angle_rad)
    base_z = 0.0
    
    # Apply source offsets
    x = base_x + geometry.source_offset_x
    y = base_y + geometry.source_offset_y
    z = base_z + geometry.source_offset_z
    
    return (x, y, z)
```

- [ ] **Step 2: Add function to calculate detector position**

```python
def get_detector_position(geometry: ProjectionGeometry, source_angle: float = 0.0) -> tuple[float, float, float]:
    """Calculate detector position from ProjectionGeometry.
    
    Args:
        geometry: ProjectionGeometry object
        source_angle: Current source angle in degrees
        
    Returns:
        (x, y, z) detector position in mm
    """
    import math
    angle_rad = math.radians(source_angle)
    
    # Detector is opposite to source on the central beam
    base_x = -geometry.sid * math.cos(angle_rad)
    base_y = -geometry.sid * math.sin(angle_rad)
    base_z = 0.0
    
    # Apply detector offsets (independent of source)
    x = base_x + geometry.detector_offset_x
    y = base_y + geometry.detector_offset_y
    # Detector doesn't have Z offset (comes from source_offset_z)
    
    return (x, y, base_z)
```

- [ ] **Step 3: Add function to generate all trajectory positions**

```python
def get_trajectory_positions(geometry: ProjectionGeometry, n_projections: int) -> tuple[list, list]:
    """Generate source and detector positions for all projections.
    
    Args:
        geometry: ProjectionGeometry object
        n_projections: Total number of projections in the scan
        
    Returns:
        (source_positions, detector_positions) as lists of (x,y,z) tuples
    """
    source_positions = []
    detector_positions = []
    
    # Each projection is at a different angle
    # Total angle covered depends on scan (could be multiple rotations)
    # For now, assume uniform distribution over total angle
    
    for i in range(n_projections):
        # Calculate angle for this projection
        # (in real data, this would come from DICOM or be calculated)
        source_angle = (i / n_projections) * 360.0  # degrees
        
        src = get_source_position(geometry, source_angle)
        det = get_detector_position(geometry, source_angle)
        
        source_positions.append(src)
        detector_positions.append(det)
    
    return source_positions, detector_positions
```

- [ ] **Step 3: Update add_source_detector_to_plotly to accept ProjectionGeometry**

Modify the existing `add_source_detector_to_plotly` function to accept either:
- Legacy mode: current x, y, z parameters
- Geometry mode: ProjectionGeometry object + source_angle

- [ ] **Step 4: Test locally**

```bash
# Run app and verify geometry visualization works
streamlit run app.py
```

- [ ] **Step 5: Commit**

```bash
git add src/visualization/volume3d.py
git commit -m "feat: add geometry-based source/detector visualization"
```

---

## Task 3: Add UI for Loading Projection Geometry in App

**Files:**
- Modify: `src/visualization/app.py`

**Interfaces:**
- Consumes: ProjectionGeometry from Task 1
- Produces: UI controls to load geometry file and adjust downsampling

- [ ] **Step 1: Add file uploader for geometry TXT file**

In the 3D controls section, add an option to load projection geometry file.

- [ ] **Step 2: Add downsample dropdown**

Dropdown options: N = 1000, 100, 10, 1 (show every Nth projection)
- 1000: ~51 points
- 100: ~513 points  
- 10: ~5,132 points
- 1: ~51,326 points (might be slow)

- [ ] **Step 3: Generate all positions and downsample**

Calculate source/detector positions for all projections, then downsample based on selection.

- [ ] **Step 4: Pass all positions to 3D plot**

Update the 3D plot to show all (downsampled) source and detector positions as scatter points.

**Visual styling:**
- Source positions: small point marker, red or orange color
- Detector positions: small point marker, **turquoise** color

- [ ] **Step 4: Commit**

```bash
git add src/visualization/app.py
git commit -m "feat: add projection geometry UI to app"
```

---

## Summary

| Task | Description |
|------|-------------|
| 1 | Create projection geometry loader (projection.py) |
| 2 | Add geometry-based source/detector to 3D plot (volume3d.py) |
| 3 | Add UI for loading geometry in app (app.py) |

---

## Out of Scope (Future)

- Loading actual projection images (not just geometry)
- Curved detector rendering
- Animation of helical trajectory
- Multiple projection views at once
