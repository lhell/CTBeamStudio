"""Tests for the 3D volume figure's world-coordinate placement (T-94).

The 3D view must draw the volume in the same world frame the forward
projection uses — real DICOM origin and spacing, rotation axis through the
world origin — so the geometry overlay (source path, detector, central
beams) agrees with the simulated projections.
"""

import numpy as np
import pytest

from visualization.volume3d import create_volume_figure, get_volume_center

SPACING = (2.0, 1.0, 1.0)  # (z, y, x) mm
ORIGIN = (10.0, 20.0, 30.0)  # (x, y, z) DICOM mm


def _shell_cube(n: int, shell: int) -> np.ndarray:
    """Tissue block inside an air shell: a surface marching cubes finds."""
    vol = np.full((n, n, n), -1000, dtype=np.int16)
    vol[shell:-shell, shell:-shell, shell:-shell] = 1000
    return vol


def _mesh_bounds(fig):
    """(min, max) per axis over every Mesh3d vertex in the figure."""
    meshes = [t for t in fig.data if t.type == "mesh3d"]
    assert meshes, "iso figure has no Mesh3d traces"
    pts = np.concatenate([np.column_stack([m.x, m.y, m.z]) for m in meshes], axis=0)
    return pts.min(axis=0), pts.max(axis=0)


def _iso_figure(volume, spacing, downsample, origin):
    """Iso figure with a single isosurface at level 0 (the air/tissue edge)."""
    return create_volume_figure(
        volume,
        spacing=spacing,
        render_mode="iso",
        downsample=downsample,
        iso_threshold=(0.0, 0.0),
        n_iso_levels=1,
        origin=origin,
    )


def test_real_origin_places_the_mesh_at_the_projected_position():
    """With the DICOM origin the surface sits at origin + index * spacing —
    the same world positions the forward projection traces through."""
    fig = _iso_figure(_shell_cube(12, 2), SPACING, 1, ORIGIN)
    lo, hi = _mesh_bounds(fig)
    # Level 0 between the air shell (voxels 0-1) and the block (voxel 2)
    # crosses at voxel index 1.5 .. n - 2.5.
    assert lo == pytest.approx(
        [
            ORIGIN[0] + 1.5 * SPACING[2],
            ORIGIN[1] + 1.5 * SPACING[1],
            ORIGIN[2] + 1.5 * SPACING[0],
        ]
    )
    assert hi == pytest.approx(
        [
            ORIGIN[0] + 9.5 * SPACING[2],
            ORIGIN[1] + 9.5 * SPACING[1],
            ORIGIN[2] + 9.5 * SPACING[0],
        ]
    )


def test_origin_none_keeps_the_legacy_centred_placement():
    """Without an origin the volume stays centred on the rotation axis
    (the legacy schematic placement, unchanged)."""
    fig = _iso_figure(_shell_cube(12, 2), SPACING, 1, None)
    lo, hi = _mesh_bounds(fig)
    extent = (12 * SPACING[0], 12 * SPACING[1], 12 * SPACING[2])
    # Legacy: first drawn voxel at -extent / 2, surface at index 1.5 .. 8.5.
    assert lo == pytest.approx(
        [
            -extent[2] / 2 + 1.5 * SPACING[2],
            -extent[1] / 2 + 1.5 * SPACING[1],
            -extent[0] / 2 + 1.5 * SPACING[0],
        ]
    )
    assert hi == pytest.approx(
        [
            -extent[2] / 2 + 9.5 * SPACING[2],
            -extent[1] / 2 + 9.5 * SPACING[1],
            -extent[0] / 2 + 9.5 * SPACING[0],
        ]
    )


def test_downsampled_mesh_lands_on_the_merged_voxel_centres():
    """Mean-pooling moves the first drawn voxel centre 0.5 * (factor - 1)
    source voxels in from the origin — the mesh must follow, or the drawn
    phantom drifts half a block away from where the projector traces."""
    fig = _iso_figure(_shell_cube(24, 4), SPACING, 4, ORIGIN)
    lo, hi = _mesh_bounds(fig)
    # Merged voxel i centre = origin + (i*4 + 1.5) * s; the air/tissue edge
    # sits between merged voxels 0/1 and 4/5, i.e. at 3.5*s .. 19.5*s.
    assert lo == pytest.approx(
        [
            ORIGIN[0] + 3.5 * SPACING[2],
            ORIGIN[1] + 3.5 * SPACING[1],
            ORIGIN[2] + 3.5 * SPACING[0],
        ]
    )
    assert hi == pytest.approx(
        [
            ORIGIN[0] + 19.5 * SPACING[2],
            ORIGIN[1] + 19.5 * SPACING[1],
            ORIGIN[2] + 19.5 * SPACING[0],
        ]
    )


def test_volume_render_places_markers_at_the_merged_voxel_centres():
    """The voxel-cloud path (downsample * ds merged) draws its first marker
    at origin + 0.5 * (factor - 1) * spacing."""
    fig = create_volume_figure(
        np.full((32, 32, 32), 1000, dtype=np.int16),
        spacing=SPACING,
        render_mode="volume",
        downsample=4,
        origin=ORIGIN,
    )
    scatters = [t for t in fig.data if t.type == "scatter3d"]
    assert scatters, "volume figure has no voxel cloud"
    pts = np.concatenate([np.column_stack([t.x, t.y, t.z]) for t in scatters], axis=0)
    # Total factor 4 * 4 = 16: first centre at 7.5*s, second at 23.5*s.
    assert pts.min(axis=0) == pytest.approx(
        [
            ORIGIN[0] + 7.5 * SPACING[2],
            ORIGIN[1] + 7.5 * SPACING[1],
            ORIGIN[2] + 7.5 * SPACING[0],
        ]
    )
    assert pts.max(axis=0) == pytest.approx(
        [
            ORIGIN[0] + 23.5 * SPACING[2],
            ORIGIN[1] + 23.5 * SPACING[1],
            ORIGIN[2] + 23.5 * SPACING[0],
        ]
    )


def test_get_volume_center_uses_the_real_origin():
    """The centre of the voxel grid in world coordinates is
    origin + half the voxel-centre extent."""
    center = get_volume_center(
        np.zeros((12, 12, 12), dtype=np.int16), SPACING, origin=ORIGIN
    )
    assert center == pytest.approx(
        (
            ORIGIN[0] + 5.5 * SPACING[2],
            ORIGIN[1] + 5.5 * SPACING[1],
            ORIGIN[2] + 5.5 * SPACING[0],
        )
    )
    # Legacy: no origin -> the volume is assumed centred on the axis.
    assert get_volume_center(np.zeros((12, 12, 12), dtype=np.int16), SPACING) == (
        0.0,
        0.0,
        0.0,
    )
