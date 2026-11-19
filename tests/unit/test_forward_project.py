"""Tests for forward projection module."""

import builtins

import numpy as np
import pytest

from backend.geometry import ProjectionGeometry
from backend.volume import Volume

# The helix tests exercise the real projection path (parallelproj + torch;
# the compiled kernels are on PATH only inside the conda env). Guard per
# test, not with a module-level ``pytest.importorskip``: that aborts
# collection of the whole file and would silently delete the tests that do
# not need parallelproj (same pattern as the nibabel guard in
# test_sinogram_loader.py).
try:
    from backend.parallelproj import geometry as _pp_geometry  # noqa: F401

    _PROJECTION_BACKEND_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on environment
    _PROJECTION_BACKEND_AVAILABLE = False

requires_projection_backend = pytest.mark.skipif(
    not _PROJECTION_BACKEND_AVAILABLE,
    reason="parallelproj/torch projection backend is not installed",
)


def test_forward_projection_result_dataclass():
    """Test ForwardProjectionResult can be created."""
    from backend.forward_project import ForwardProjectionResult

    projections = np.zeros((10, 64, 512))
    geometry = ProjectionGeometry()
    result = ForwardProjectionResult(
        projections=projections,
        geometry=geometry,
        row_indices=list(range(64)),
        col_indices=list(range(512)),
        proj_indices=list(range(10)),
    )
    assert result.projections.shape == (10, 64, 512)
    assert result.geometry is not None
    assert len(result.row_indices) == 64
    assert len(result.col_indices) == 512
    assert len(result.proj_indices) == 10


def test_forward_project_returns_correct_shape():
    """Test forward_project returns projections with correct shape."""
    from backend.forward_project import forward_project

    # Simple attenuation volume (water at ~70 keV in 1/mm).
    volume = Volume(
        array=np.ones((10, 10, 10), dtype=np.float32) * 0.0194,
        spacing=(2.5, 1.0, 1.0),
        origin=(0, 0, 0),
        meta={"unit": "1/mm"},
    )

    geometry = ProjectionGeometry(
        n_det_cols=16, n_det_rows=16, projections_per_rotation=1
    )

    result = forward_project(volume, geometry)

    # Should return (n_projections, n_rows, n_cols) with a 0° projection
    assert result.projections.shape[0] == 1
    assert result.projections.shape[1] == 16
    assert result.projections.shape[2] == 16


def test_forward_project_with_selection():
    """Test forward_project with row/col/projection selection."""
    from backend.forward_project import forward_project

    volume = Volume(
        array=np.ones((20, 20, 20), dtype=np.float32) * 0.0194,
        spacing=(2.5, 1.0, 1.0),
        origin=(0, 0, 0),
        meta={"unit": "1/mm"},
    )

    geometry = ProjectionGeometry(
        n_det_cols=16, n_det_rows=16, projections_per_rotation=1
    )

    # Select only central row (0° projection)
    result = forward_project(
        volume,
        geometry,
        row_indices=[8],  # central row
        proj_indices=[0],  # single 0° projection
    )

    assert result.projections.shape[0] == 1  # 1 projection
    assert result.projections.shape[1] == 1  # 1 row
    assert result.projections.shape[2] == 16  # all cols


def test_parallelproj_availability():
    """Test that parallelproj availability flag works."""
    from backend.forward_project import PARALLELPROJ_AVAILABLE

    # Just check the flag exists and is a boolean
    assert isinstance(PARALLELPROJ_AVAILABLE, bool)


def test_availability_flag_requires_torch_too(monkeypatch):
    """parallelproj alone cannot project: the backend builds its tensors with
    torch. If torch is missing the flag must be False, so the UI warns and
    falls back to zeros instead of crashing with ModuleNotFoundError.

    ``importlib.reload`` mutates the shared module object, so the original
    state must be restored even though the test passes: leaving the module
    reloaded with the flag forced to False would make every later test (and
    any later projection in the same process) silently take the zeros path.
    """
    import importlib
    import sys

    import backend.forward_project as fp

    saved_flag = fp.PARALLELPROJ_AVAILABLE
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "torch" or name.startswith("torch."):
            raise ImportError("simulated missing torch")
        return real_import(name, *args, **kwargs)

    try:
        monkeypatch.setattr(builtins, "__import__", fake_import)
        monkeypatch.setitem(sys.modules, "parallelproj", object())

        reloaded = importlib.reload(fp)

        assert reloaded.PARALLELPROJ_AVAILABLE is False
    finally:
        # Undo the import hook and the fake parallelproj entry, then reload
        # so the shared module object is healthy again for later tests.
        monkeypatch.undo()
        importlib.reload(fp)

    assert fp.PARALLELPROJ_AVAILABLE is saved_flag


def test_forward_project_rejects_hu_volume():
    """HU is not a valid forward-projection basis; attenuation is required."""
    from backend.forward_project import forward_project

    volume = Volume(
        array=np.full((4, 4, 4), 40, dtype=np.int16),
        spacing=(1.0, 1.0, 1.0),
        origin=(0.0, 0.0, 0.0),
        meta={"unit": "HU"},
    )
    geometry = ProjectionGeometry(
        n_det_cols=4, n_det_rows=4, projections_per_rotation=1
    )

    with pytest.raises(ValueError, match="attenuation"):
        forward_project(volume, geometry)


def test_forward_project_accepts_attenuation_volume():
    """A volume in 1/mm is projected without complaint."""
    from backend.forward_project import forward_project

    volume = Volume(
        array=np.full((4, 4, 4), 0.0194, dtype=np.float32),
        spacing=(1.0, 1.0, 1.0),
        origin=(0.0, 0.0, 0.0),
        meta={"unit": "1/mm"},
    )
    geometry = ProjectionGeometry(
        n_det_cols=4, n_det_rows=4, projections_per_rotation=1
    )

    result = forward_project(volume, geometry)
    assert result.projections.shape == (1, 4, 4)


# --- Helical table feed (T-104) ---
#
# The z feed landed in b7b7279: forward_project computes
# z_step = pitch * n_rows * row_spacing / projections_per_rotation and
# calculate_xray_beam_list places projection i (its *original* angle index)
# at z = z_offset - (N / 2) * z_step + i * z_step. The slab volume below
# turns a z shift into a measurable projection change.

# Slab volume: one attenuating z plane at centre z = 0, everything else air.
_HELIX_VOLUME_ORIGIN = (-2.0, -2.0, -10.0)  # DICOM (x, y, z)


def _slab_volume():
    """(11, 5, 5) volume whose middle z plane (centre z = 0) attenuates."""
    array = np.zeros((11, 5, 5), dtype=np.float32)
    array[5, :, :] = 0.02  # water at ~70 keV, 1/mm
    return Volume(
        array=array,
        spacing=(2.0, 1.0, 1.0),
        origin=_HELIX_VOLUME_ORIGIN,
        meta={"unit": "1/mm"},
    )


def _helix_geometry():
    """Single-ray geometry with z_step = 3 mm per projection."""
    return ProjectionGeometry(
        n_det_cols=1,
        n_det_rows=1,
        projections_per_rotation=4,
        pitch=0.75,
        det_row_spacing_mm=16.0,
    )


@requires_projection_backend
def test_forward_project_reports_progress_and_chunking_is_transparent():
    """``progress(done, total)`` advances to total, and splitting the run into
    chunks (T-108) returns exactly what one call per projection returns."""
    from backend.forward_project import forward_project

    n_proj = 40  # more than one internal chunk
    volume = Volume(
        array=np.ones((5, 5, 5), dtype=np.float32) * 0.0194,
        spacing=(1.0, 1.0, 1.0),
        origin=(0.0, 0.0, 0.0),
        meta={"unit": "1/mm"},
    )
    geometry = ProjectionGeometry(
        n_det_cols=1, n_det_rows=1, projections_per_rotation=n_proj
    )

    calls = []
    result = forward_project(
        volume,
        geometry,
        proj_indices=list(range(n_proj)),
        progress=lambda done, total: calls.append((done, total)),
    )

    done = [c for c, _ in calls]
    assert done == sorted(done)
    assert all(total == n_proj for _, total in calls)
    assert done[-1] == n_proj
    assert len(calls) >= 2  # 40 projections do not fit one chunk

    single = [
        forward_project(volume, geometry, proj_indices=[i]).projections
        for i in range(n_proj)
    ]
    np.testing.assert_array_equal(result.projections, np.concatenate(single))


@requires_projection_backend
def test_forward_project_helix_shifts_projections_along_z():
    """pitch > 0 feeds the table: only the projection at z = 0 sees the slab.

    With one detector row the detector z equals the source z, so the whole
    ray lies in the plane z = z(i). The helix centres the four projections
    on the volume's z centre: z = -6, -3, 0, +3. The slab lives at z = 0
    only, and the miss rays are >= 2 mm from any non-zero voxel centre, so
    linear interpolation cannot pick up slab weight.
    """
    from backend.forward_project import forward_project

    volume = _slab_volume()
    geometry = _helix_geometry()

    result = forward_project(
        volume,
        geometry,
        row_indices=[0],
        col_indices=[0],
        proj_indices=[0, 1, 2, 3],
    )

    hit = float(result.projections[2, 0, 0])
    misses = result.projections[[0, 1, 3], 0, 0]

    assert hit > 0
    assert np.all(misses < 0.01 * hit)

    # Reproducible: the helix is a pure function of geometry and volume.
    again = forward_project(
        volume,
        geometry,
        row_indices=[0],
        col_indices=[0],
        proj_indices=[0, 1, 2, 3],
    )
    assert np.array_equal(result.projections, again.projections)


@requires_projection_backend
def test_forward_project_pitch_zero_is_exactly_circular():
    """pitch = 0 stays a circular scan: every projection sits at z_center.

    All four rays pass through the slab at z = 0, so they all hit it and
    agree (the ray through the isocenter integrates the same slab from four
    angles). With a table feed they separate — see the shift test.
    """
    from backend.forward_project import forward_project

    result = forward_project(
        _slab_volume(),
        ProjectionGeometry(n_det_cols=1, n_det_rows=1, projections_per_rotation=4),
        row_indices=[0],
        col_indices=[0],
        proj_indices=[0, 1, 2, 3],
    )

    values = result.projections[:, 0, 0]
    assert np.all(values > 0)
    assert np.allclose(values, values[0], rtol=1e-2)


@requires_projection_backend
def test_calculate_xray_beam_list_helix_z_positions_pinned():
    """The helix z feed follows the documented formula, exactly.

    z(i) = z_offset - (N / 2) * z_step + i * z_step with i the original
    angle index and N the total projection count; the detector rides on z.
    """
    from backend.parallelproj.geometry import ConeBeamGeometry

    cb = ConeBeamGeometry(
        sid=100.0,
        sdd=200.0,
        n_projections=4,
        angular_inc_degree=90.0,
        n_det_rows=1,
        n_det_cols=1,
        det_row_spacing_mm=2.0,
        det_col_spacing_mm=2.0,
    )

    pos_start, pos_end = cb.calculate_xray_beam_list(
        dev="cpu", z_offset_mm=10.0, z_step_mm=3.0
    )

    # 4 projections centred on z_offset: z = 10 - 2*3 + i*3.
    assert pos_start[:, 2].numpy() == pytest.approx([4.0, 7.0, 10.0, 13.0])
    # The detector rides on the table feed (single row, offset 0).
    assert pos_end[:, 2].numpy() == pytest.approx([4.0, 7.0, 10.0, 13.0])

    # With a known total the helix is centred over the whole scan, not the
    # selected subset.
    pos_start, _ = cb.calculate_xray_beam_list(
        dev="cpu", z_offset_mm=10.0, z_step_mm=3.0, n_projections_total=8
    )
    assert pos_start[:, 2].numpy() == pytest.approx([-2.0, 1.0, 4.0, 7.0])

    # A selection uses the original angle indices for z, not the selection
    # position (projections 1 and 3 of 4, not the first and second selected).
    pos_start, _ = cb.calculate_xray_beam_list(
        dev="cpu",
        z_offset_mm=10.0,
        z_step_mm=3.0,
        projection_indices=[1, 3],
        n_projections_total=4,
    )
    assert pos_start[:, 2].numpy() == pytest.approx([7.0, 13.0])


@requires_projection_backend
def test_calculate_xray_beam_list_circular_when_z_step_zero():
    """z_step = 0 (pitch = 0) is the pre-helix circular path: constant z.

    forward_project passes z_step_mm=0.0 when pitch is 0, so every
    projection sits exactly at z_offset — identical to the behaviour before
    the table feed existed.
    """
    from backend.parallelproj.geometry import ConeBeamGeometry

    cb = ConeBeamGeometry(
        sid=100.0,
        sdd=200.0,
        n_projections=4,
        angular_inc_degree=90.0,
        n_det_rows=1,
        n_det_cols=1,
        det_row_spacing_mm=2.0,
        det_col_spacing_mm=2.0,
    )

    pos_start, pos_end = cb.calculate_xray_beam_list(
        dev="cpu",
        z_offset_mm=10.0,
        z_step_mm=0.0,
        projection_indices=[0, 1, 2, 3],
        n_projections_total=4,
    )

    assert pos_start[:, 2].numpy() == pytest.approx([10.0, 10.0, 10.0, 10.0])
    assert pos_end[:, 2].numpy() == pytest.approx([10.0, 10.0, 10.0, 10.0])


@requires_projection_backend
def test_forward_project_helix_matches_3d_trajectory():
    """The helix FP and the 3D trajectory use the same placement.

    get_trajectory_positions (volume3d) draws the source path and detector
    planes; the projector computes rays at the same z(i) and angles. The
    source position is the first LOR start of each projection (identical
    for every detector element); the central-pixel detector position has no
    pixel offset and equals the drawn detector centre.
    """
    from backend.parallelproj import geometry_from_projection_geometry
    from visualization.volume3d import get_trajectory_positions

    geometry = ProjectionGeometry(
        sid=600.0,
        sdd=1000.0,
        n_det_rows=5,
        n_det_cols=5,
        det_row_spacing_mm=2.0,
        projections_per_rotation=8,
        pitch=0.5,
    )
    n = 8
    z_offset = 25.0
    z_step = (
        geometry.pitch
        * geometry.n_det_rows
        * geometry.det_row_spacing_mm
        / geometry.projections_per_rotation
    )
    assert z_step == pytest.approx(0.625)

    cb = geometry_from_projection_geometry(geometry)
    pos_start, pos_end = cb.calculate_xray_beam_list(
        dev="cpu",
        projection_indices=list(range(n)),
        z_offset_mm=z_offset,
        z_step_mm=z_step,
        n_projections_total=n,
    )
    per_proj = geometry.n_det_rows * geometry.n_det_cols
    src_fp = pos_start.view(n, per_proj, 3)[:, 0, :].numpy()
    # Central pixel: row 2, col 2 -> index 2 * n_rows + 2 (no pixel offset).
    det_fp = pos_end.view(n, per_proj, 3)[:, 2 * geometry.n_det_rows + 2, :].numpy()

    src_3d, det_3d = get_trajectory_positions(geometry, n, z_offset=z_offset)

    # float32 torch tensors vs float64 math: residual ~1e-4 mm at 1000 mm.
    np.testing.assert_allclose(src_fp, np.asarray(src_3d), atol=1e-2)
    np.testing.assert_allclose(det_fp, np.asarray(det_3d), atol=1e-2)
