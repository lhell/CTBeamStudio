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
    projector,
    to_parallelproj_batch,
)
from backend.parallelproj.geometry import ConeBeamGeometry
from backend.parallelproj.projector import (
    ConeBeamProjector,
    _from_operator_output,
    _to_operator_input,
)


def _available_device() -> str:
    """Device that actually exists here: ``cuda:0`` on a GPU box, else CPU.

    Never skips: every test runs on whichever device the machine has.
    """
    import torch

    return "cuda:0" if torch.cuda.is_available() else "cpu"


class _HostTensor:
    """CPU-side array stand-in returned by ``_FakeDeviceTensor.cpu()``."""

    def __init__(self, array: np.ndarray):
        self._array = array
        self.numpy_calls = 0

    def numpy(self) -> np.ndarray:
        self.numpy_calls += 1
        return self._array


class _FakeDeviceTensor:
    """Torch-like tensor that refuses implicit numpy conversion.

    Mirrors audit finding #1: ``np.asarray`` on a CUDA tensor raises
    ``TypeError: can't convert cuda:0 device type tensor to numpy``, while
    ``.detach().cpu().numpy()`` succeeds. Using it proves the projector takes
    the explicit host-copy route; no CUDA hardware is required.
    """

    def __init__(self, array):
        self._array = np.asarray(array, dtype=np.float32)
        self.detach_calls = 0
        self.cpu_calls = 0
        self.host = None

    @property
    def shape(self):
        return self._array.shape

    def __array__(self, *args, **kwargs):
        raise TypeError("can't convert cuda:0 device type tensor to numpy.")

    def detach(self):
        self.detach_calls += 1
        return self

    def cpu(self):
        self.cpu_calls += 1
        self.host = _HostTensor(self._array)
        return self.host


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


def _default_projector(vol_zyx: np.ndarray, dev: str = "cpu") -> ConeBeamProjector:
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
    pos_start, pos_end = g.calculate_xray_beam_list(dev=dev)

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


def test_geometry_z_offset_shifts_scan_plane():
    """z_offset_mm moves the whole trajectory (source and detector) in z."""
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
    start, end = g.calculate_xray_beam_list(dev="cpu")
    shifted_start, shifted_end = g.calculate_xray_beam_list(
        dev="cpu", z_offset_mm=120.0
    )

    # Source z sits at the offset instead of 0.
    assert shifted_start[0].numpy()[2] == pytest.approx(120.0, abs=1e-4)
    assert start[0].numpy()[2] == pytest.approx(0.0, abs=1e-4)

    # Detector rows shift by the same amount: the central element of the
    # middle row lands at z = offset, the neighbouring rows one spacing away.
    assert shifted_end[1].numpy()[2] == pytest.approx(120.0, abs=1e-4)
    assert shifted_end[0].numpy()[2] == pytest.approx(119.0, abs=1e-4)
    assert shifted_end[2].numpy()[2] == pytest.approx(121.0, abs=1e-4)

    # x/y positions are unchanged by the z offset.
    np.testing.assert_allclose(
        shifted_start[0].numpy()[:2], start[0].numpy()[:2], atol=1e-5
    )


def test_geometry_source_offset_z_shifts_source_and_detector():
    """source_offset_z_mm shifts the whole LOR pair along z, not in x/y."""
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
    start, end = g.calculate_xray_beam_list(dev="cpu")
    shifted_start, shifted_end = g.calculate_xray_beam_list(
        dev="cpu", source_offset_z_mm=17.0
    )

    assert shifted_start[0].numpy()[2] == pytest.approx(17.0, abs=1e-4)
    assert shifted_end[1].numpy()[2] == pytest.approx(17.0, abs=1e-4)
    assert start[0].numpy()[2] == pytest.approx(0.0, abs=1e-4)
    np.testing.assert_allclose(
        shifted_start[0].numpy()[:2], start[0].numpy()[:2], atol=1e-5
    )


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


def test_forward_project_selected_projection_indices_match_full():
    """A non-contiguous projection selection picks the matching angles."""
    from backend.forward_project import forward_project
    from backend.geometry import ProjectionGeometry
    from backend.volume import Volume

    geometry = ProjectionGeometry(
        sdd=1000.0,
        sid=500.0,
        n_det_rows=8,
        n_det_cols=8,
        det_row_spacing_mm=1.0,
        det_col_spacing_mm=1.0,
        projections_per_rotation=8,
    )
    volume = Volume(
        array=np.full((8, 8, 8), 0.02, dtype=np.float32),
        spacing=(1.0, 1.0, 1.0),
        origin=(0.0, 0.0, 0.0),
        meta={"unit": "1/mm"},
    )

    full = forward_project(volume, geometry, use_cuda=False)
    selected = forward_project(volume, geometry, proj_indices=[2, 5], use_cuda=False)

    assert selected.projections.shape[0] == 2
    np.testing.assert_allclose(
        selected.projections,
        full.projections[[2, 5]],
        rtol=1e-5,
        atol=1e-5,
    )


# --- Device boundary (T-08-01) ---
#
# parallelproj 1.10.x dispatches on the image array, so the projector converts
# every tensor to host numpy at one boundary. These tests pin that contract
# without needing CUDA: the fake tensor raises on implicit numpy conversion,
# exactly like a real CUDA tensor did in audit finding #1.


def test_lor_positions_never_convert_cuda_tensor_implicitly():
    """LOR positions go through ``detach().cpu()``, never ``np.asarray``."""
    raw = np.arange(12, dtype=np.float32).reshape(4, 3)
    fake = _FakeDeviceTensor(raw)

    out = _to_operator_input(fake)

    assert isinstance(out, np.ndarray)
    assert out.shape == (4, 3)
    assert out.dtype == np.float32
    np.testing.assert_array_equal(out, raw)
    assert fake.detach_calls == 1
    assert fake.cpu_calls == 1


def test_operator_output_returns_host_numpy():
    """A tensor-shaped operator result is copied to host memory."""
    raw = np.arange(6, dtype=np.float32)
    fake = _FakeDeviceTensor(raw)

    out = _from_operator_output(fake)

    assert isinstance(out, np.ndarray)
    np.testing.assert_array_equal(out, raw)


def test_projector_converts_all_tensors_before_calling_parallelproj(monkeypatch):
    """``__init__``, ``apply`` and ``adjoint`` hand host numpy to upstream."""
    seen = {}

    class _StubOperator:
        in_shape = (2, 2, 2)
        out_shape = (4,)

        def __call__(self, volume):
            seen["volume"] = volume
            return np.ones(4, dtype=np.float32)

        def adjoint(self, flat_proj):
            seen["adjoint"] = flat_proj
            return np.ones((2, 2, 2), dtype=np.float32)

    def _factory(start, end, *args, **kwargs):
        seen["start"] = start
        seen["end"] = end
        return _StubOperator()

    monkeypatch.setattr(projector, "ListmodePETProjector", _factory)

    pos = _FakeDeviceTensor(np.zeros((8, 3), dtype=np.float32))
    proj = ConeBeamProjector(
        pos,
        pos,
        img_shape_zyx=(2, 2, 2),
        spacing_zyx=(1.0, 1.0, 1.0),
        origin_zyx=(0.0, 0.0, 0.0),
        n_det_rows=2,
        n_det_cols=2,
        n_projections=1,
    )

    for key in ("start", "end"):
        assert isinstance(seen[key], np.ndarray)
        assert seen[key].shape == (8, 3)

    out = proj.apply(_FakeDeviceTensor(np.ones((2, 2, 2), dtype=np.float32)))
    assert isinstance(seen["volume"], np.ndarray)
    assert out.shape == (1, 2, 2)

    adj = proj.adjoint(_FakeDeviceTensor(np.ones((1, 2, 2), dtype=np.float32)))
    assert isinstance(seen["adjoint"], np.ndarray)
    assert adj.shape == (2, 2, 2)


def test_geometry_lors_from_available_device_match_cpu():
    """LORs built on the available device project like CPU-built LORs.

    On a CPU-only machine both sides are the CPU path; on a GPU machine the
    left side exercises exactly the CUDA-tensor boundary that used to raise.
    """
    vol_zyx = _four_region_volume(8)
    vol_xyz = np.transpose(vol_zyx, (2, 1, 0))

    on_device = _default_projector(vol_zyx, dev=_available_device()).apply(vol_xyz)
    on_cpu = _default_projector(vol_zyx, dev="cpu").apply(vol_xyz)

    np.testing.assert_allclose(on_device, on_cpu, rtol=1e-5, atol=1e-5)
