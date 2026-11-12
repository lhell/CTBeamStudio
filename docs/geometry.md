# Projection Geometry Definition

This document defines the coordinate system and geometry parameters used in CTBeamStudio for cone-beam CT projection data.

## Coordinate System

- **Z-axis**: Patient longitudinal axis (table feed direction)
- **X-axis**: Patient lateral direction (right/left when supine)
- **Y-axis**: Anterior/posterior (front/back of patient)
- **Source rotation**: Around the Z-axis in the transverse plane
- **Source angle reference**: 0° = **anterior** (front of patient)
- **Positive rotation direction**: Counter-clockwise when viewed from above

## Geometry Parameters

### Angles

| Parameter | Description | Sign Convention |
|-----------|-------------|-----------------|
| `sourceAngle` | Source position around Z-axis | 0° = anterior, positive = CCW (viewed from above) |
| `detectorInPlaneAngle` | Detector rotates in its own plane, stays perpendicular to source | Rotates within detector plane |
| `detectorOutOfPlaneAngle` | Detector tilts right/left from perpendicular to central beam | Tilts perpendicular to source rotation |
| `detectorTiltAngle` | Backwards tilt from perpendicular to source | Positive = tilt backwards |

### Detector Angle Details

- **detectorInPlaneAngle**: The detector rotates within its own plane but remains perpendicular to the source ray. This adjusts the fan angle orientation.

- **detectorOutOfPlaneAngle**: The detector tilts away from being perpendicular to the central beam. This is used to reduce the effective cone angle in cone-beam CT.

- **detectorTiltAngle**: The detector tilts backwards from the perpendicular to the source ray (positive = tilt backwards).

### Distances

| Parameter | Description |
|-----------|-------------|
| `sdd` | Source-to-detector distance (mm) |
| `sid` | Source-to-isocenter distance (mm) |

### Detector Properties

| Parameter | Description |
|-----------|-------------|
| `n_det_cols` | Number of detector columns |
| `n_det_rows` | Number of detector rows |
| `det_col_spacing_mm` | Detector column spacing (mm), center to center |
| `det_row_spacing_mm` | Detector row spacing (mm), center to center |
| `detector_shape` | Detector shape: "flat" (default) or "curved" (future) |

### Helical Scanning

| Parameter | Description |
|-----------|-------------|
| `pitch` | Table feed per gantry rotation / collimation width |

Pitch is defined as:
```
pitch = table_feed_per_rotation / collimation_width
```

Where:
- `collimation_width = n_det_rows × det_row_spacing_mm`

**Pitch values:**
- 1.0 = no overlap, no gaps
- < 1.0 = overlapping scans
- > 1.0 = gaps between scans

## Offsets

### Source Offsets (Detector Follows)

When the source moves with an offset, the detector **follows** (stays connected by the central beam):

| Parameter | Description |
|-----------|-------------|
| `sourceOffsetX` | Source lateral offset (mm) |
| `sourceOffsetY` | Source longitudinal offset, perpendicular to table (mm) |
| `sourceOffsetZ` | Source Z offset (table feed direction) — for helical scanning |

The relationship for helical scanning:
```
sourceOffsetZ = (sourceAngle / 360°) × pitch × collimation_width
```

### Detector Offsets (Independent Movement)

The detector can move **independently** of the source (detector shifts from its ideal position on the central beam):

| Parameter | Description |
|-----------|-------------|
| `detectorOffsetX` | Detector lateral offset (mm) |
| `detectorOffsetY` | Detector longitudinal offset (mm) |

## Default Orientation

- **Detector default**: Perpendicular to the source ray (facing the source)
- **Detector shape**: "flat" (planar detector)
- **Geometry type**: Cone-beam
- **Source offsets**: All default to 0
- **Detector offsets**: All default to 0

> **Note:** Curved detector support is planned for a future version.

## Volume Placement in World Coordinates

The forward projection and the 3D volume view share one world frame:

- **Rotation axis**: runs through the world origin (`0, 0, 0`), along **Z**.
- **Source at 0°**: `(sid, 0, 0)` (anterior, `+x`), rotating counter-clockwise seen from `+z`.
- **Detector**: opposite the source at `sdd - sid` from the isocenter (SDD is measured from the source, not from the rotation axis).
- **Volume**: voxel `[0, 0, 0]` of the `(x, y, z)`-reordered grid sits at
  `Volume.origin` (DICOM `(x, y, z)`), voxel centres at `origin + index * spacing`.
  A volume with origin `(0, 0, 0)` therefore sits entirely in the `+x/+y/+z`
  octant — the central ray (z = 0 plane) clips its bottom edge, and the
  phantom lands at the top of the detector.

The 3D view (`src/visualization/volume3d.py`) draws the volume at its real
origin in this frame, so what the plot shows is what the forward projection
computes.

## Source Data Example

For Siemens SOMATOM cone-beam helical CT data:

| Parameter | Value |
|-----------|-------|
| SDD (Source-to-Detector Distance) | 1085.6 mm |
| Detector Type (in data) | Cylindrical/curved |
| Number of Detector Rows | 64 |
| Number of Detector Columns | 736 |
| Detector Row Spacing | 1.0947 mm |
| Detector Column Spacing | 1.2858 mm |
| Detector Shape | "flat" (current), "curved" (future) |
| Pitch | 0.8 |

## Angle Reference Diagram

```
        +Y (left)
         |
         |
    +----+----+  <-- Source rotation circle
    |         |
    |    +    |  <-- Patient (center)
    |    |    |
    |    | Z  |  <-- Z-axis (into page)
    |    |    |
    +----+----+
         |
         +-- +X (anterior/front) = sourceAngle = 0°
```
