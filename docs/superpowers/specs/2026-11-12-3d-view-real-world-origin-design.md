# 3D View Real-World Placement — Design (T-94)

Date: 2026-11-12
Status: implemented

## Goal

The 3D volume view must draw the phantom in the **same world coordinate
system the forward projection uses** — real DICOM origin, real spacing —
so the geometry overlay (source path, detector planes, central beams) and
the rendered phantom agree with the simulated projections.

## Reported defect

After generating a dummy measurement and running the forward projection,
the 3D plot showed the central ray passing through the phantom centre,
while the simulated projection showed the phantom at the top of the
detector: the two views disagreed about where the phantom sits.

## Root cause

- `volume3d.create_volume_figure()` placed the volume mesh **schematically
  centred on the world origin** and ignored `Volume.origin` entirely.
- The forward projection places voxel `[0, 0, 0]` of the `(x, y, z)`-
  reordered grid at the volume's real `origin`
  (`backend.forward_project._forward_project_parallelproj`).
- With the demo default origin `(0, 0, 0)` the head sits in the
  `+x/+y/+z` octant: the projection sees the phantom above the rotation
  axis and the phantom lands at the top of the detector, while the 3D
  plot pretended it was centred — hence the inconsistency.

A second, smaller discrepancy: `volume3d.get_detector_position()` drew
the detector plane at `-sdd` from the isocenter, but the projector places
it at `-(sdd - sid)` (SDD is measured from the **source**, not from the
rotation axis — see `backend.parallelproj.geometry`). The drawn plane was
`sid` mm too far out and the central beams were longer than the real rays.

## Changes

All in `src/visualization/volume3d.py` unless noted:

1. `create_volume_figure(..., origin=None)`: `origin` is the world
   position `(x, y, z)` of the first voxel (the DICOM origin, same
   convention as `Volume.origin`). The mesh (iso mode) and voxel cloud
   (volume mode) are drawn at the real first-voxel position; the camera
   bounds frame the cell-centred grid (extent `n * spacing`, first voxel
   centre at `origin`). `None` keeps the legacy schematic centred
   placement so existing callers are unchanged.
2. Downsampling correctness: mean-pooling `factor` voxels into one moves
   the merged grid's first voxel centre `0.5 * (factor - 1)` source
   voxels in from the origin. The drawing paths (iso: total factor
   `downsample`; volume: total factor `downsample * ds`) apply that shift,
   so the drawn surface lands on the world positions the projector traces
   instead of half a block off. The legacy `origin=None` path keeps its
   previous behaviour byte-for-byte.
3. `get_volume_center(volume_array, spacing, origin=None)`: with an
   origin, returns the true voxel-grid centre (`origin + half extent`);
   `None` keeps the legacy `(0, 0, 0)`.
4. `get_detector_position()`: detector plane at `did = sdd - sid` from
   the isocenter, matching `backend.parallelproj.geometry`. Central beams
   now have the real length `sdd`.
5. `src/visualization/app.py` passes `volume.origin` through to
   `create_volume_figure()` and `get_volume_center()`. Volumes without an
   `origin` attribute fall back to the legacy centred view.

## Effect

- Demo volume (`origin = (0, 0, 0)`): the 3D view now shows the head in
  the `+x/+y/+z` octant with the central beam clipping its bottom edge —
  exactly what the simulated projection shows (phantom at the top of the
  detector). The inconsistency is visible instead of hidden.
- Dummy measurement volume (centred origin ≈ `(-95.6, -95.6, -94.5) mm`):
  the 3D view shows the head centred on the rotation axis — matching its
  projection, whose central rows pass through the head centre.

> Follow-up (T-95): the shared demo default is now centred as well, so the
> demo volume is centred in both the 3D view and the projection — the
> `+x/+y/+z`-octant case above applies only to volumes whose origin still
> parks them off-axis (e.g. arbitrary DICOM origins).

## Known limitation (out of scope)

The projector (`calculate_xray_beam_list`) models a **circular** scan:
it ignores `pitch`, `source_offset_z` and the helical table feed, while
the 3D plot draws a helix for non-zero pitch. Making the forward
projection helical is its own task; the plot is ahead of the projector
there, not behind.

## Tests

`tests/unit/test_volume3d.py` (5 tests): exact mesh placement at
`origin + index * spacing`, legacy centred placement unchanged,
downsampled mesh/marker clouds landing on the merged voxel centres
(iso and volume paths), and `get_volume_center` with and without an
origin. `tests/unit/test_geometry_trajectory.py`:
`test_get_detector_position` updated to the `sdd - sid` convention.
