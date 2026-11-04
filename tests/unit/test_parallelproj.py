"""Tests for the parallelproj cone-beam forward projection chain.

These tests exercise the real joseph3d line tracer, which requires the
``parallelproj`` package. They are skipped automatically when parallelproj is
not installed (e.g. in the plain development environment on Python 3.13); run
them inside the ``ct-viewer`` conda environment.
"""

import numpy as np
import pytest

parallelproj = pytest.importorskip("parallelproj")

from backend.parallelproj import (
    from_parallelproj_batch,
    to_parallelproj_batch,
)
from backend.parallelproj.geometry import ConeBeamGeometry
from backend.parallelproj.projector import ConeBeamProjector


def _four_region_volume(n: int = 16) -> np.ndarray:
    """Volume ``(z, y, x)`` with four labelled quadrants in ``(z, y)``.

    Region values (constant over all x):
        1 -> low z, low y     (top-left when viewed from the source at 0°)
        2 -> low z, high y    (top-right)
        3 -> high z, low y    (bottom-left)
        4 -> high z, high y   (bottom-right)
    """
    vol = np.zeros((n, n, n), dtype=np.float32)
    vol[0 : n // 2, 0 : n // 2, :] = 1.0
    vol[0 : n // 2, n // 2 : n, :] = 2.0
    vol[n // 2 : n, 0 : n // 2, :] = 3.0
    vol[n // 2 : n, n // 2 : n, :] = 4.0
    return vol


def _default_projector(vol_zyx: np.ndarray) -> ConeBeamProjector:
    """Build a 0° cone-beam projector covering the full volume."""
    g = ConeBeamGeometry(
        sid=500.0,
        sdd=1000.0,
        n_projections=1,
        angular_inc_degree=90.0,
        n_det_rows=32,
        n_det_cols=32,
        det_row_spacing_mm=1.0,
        det_col_spacing_mm=1.0,
        first_angle=0.0,
    )
    pos_start, pos_end = g.calculate_xray_beam_list(dev="cpu")

    n = vol_zyx.shape[0]
    spacing_zyx = (1.0, 1.0, 1.0)
    origin_zyx = (-(n - 1) / 2.0, -(n - 1) / 2.0, -(n - 1) / 2.0)

    return ConeBeamProjector(
        pos_start,
        pos_end,
        img_shape_zyx=vol_zyx.shape,
        spacing_zyx=spacing_zyx,
        origin_zyx=origin_zyx,
        n_det_rows=g.n_det_rows,
        n_det_cols=g.n_det_cols,
        n_projections=g.n_projections,
    )


def test_geometry_0deg_source_on_anterior():
    """At 0° the source sits on +x (anterior) and the detector on -x."""
    g = ConeBeamGeometry(
        sid=500.0,
        sdd=1000.0,
        n_projections=1,
        angular_inc_degree=90.0,
        n_det_rows=3,
        n_det_cols=3,
        det_row_spacing_mm=1.0,
        det_col_spacing_mm=1.0,
        first_angle=0.0,
    )
    pos_start, pos_end = g.calculate_xray_beam_list(dev="cpu")

    # First LOR: source on +x, central detector element on -x.
    src0 = pos_start[0].numpy()
    assert src0[0] == pytest.approx(g.sid, abs=1e-2)
    assert src0[1] == pytest.approx(0.0, abs=1e-4)
    assert src0[2] == pytest.approx(0.0, abs=1e-4)

    det_center = pos_end[len(pos_end) // 2].numpy()
    assert det_center[0] == pytest.approx(-(g.sdd - g.sid), abs=1e-2)
    assert det_center[1] == pytest.approx(0.0, abs=1e-4)


def test_four_region_projection_order():
    """0° projection shows the four quadrants in order 1(top-left)..4(bottom-right)."""
    vol_zyx = _four_region_volume()
    proj = _default_projector(vol_zyx)

    vol_xyz = np.transpose(vol_zyx, (2, 1, 0))
    out = proj.apply(vol_xyz)
    img = out[0]  # (rows, cols)

    # Average over 8x8 pixel blocks -> 4x4 quadrant block map.
    blocks = img.reshape(4, img.shape[0] // 4, 4, img.shape[1] // 4).mean(axis=(1, 3))

    # Top-left (row 0/1, col 0/1) must be the smallest, bottom-right the largest.
    tl = blocks[:2, :2].mean()
    tr = blocks[:2, 2:].mean()
    bl = blocks[2:, :2].mean()
    br = blocks[2:, 2:].mean()

    assert tl < tr < br and tl < bl < br
    assert tr == pytest.approx(2.0 * tl, rel=0.35)
    assert bl == pytest.approx(3.0 * tl, rel=0.35)
    assert br == pytest.approx(4.0 * tl, rel=0.35)


def test_projector_shapes():
    """ConeBeamProjector exposes expected in/out shapes and flat count."""
    vol_zyx = _four_region_volume(8)
    proj = _default_projector(vol_zyx)

    z, y, x = vol_zyx.shape
    assert proj.in_shape == (x, y, z)  # parallelproj (nx, ny, nz)
    assert proj.out_shape == (1, proj.n_det_rows, proj.n_det_cols)
    assert proj.flat_out_shape == (proj.n_det_rows * proj.n_det_cols,)


def test_shape_helper_roundtrip():
    """to/from_parallelproj_batch round-trip a volume exactly."""
    rng = np.random.default_rng(0)
    vol_zyx = rng.standard_normal((5, 6, 7)).astype(np.float32)

    batch = to_parallelproj_batch(vol_zyx)
    assert batch.shape == (1, 1, 7, 6, 5)  # (1, 1, nx, ny, nz)

    out = from_parallelproj_batch(batch)
    assert out.shape == (5, 6, 7)
    np.testing.assert_array_equal(out, vol_zyx)
