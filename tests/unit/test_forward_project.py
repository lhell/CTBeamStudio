"""Tests for forward projection module."""

import builtins

import numpy as np
import pytest

from backend.geometry import ProjectionGeometry
from backend.volume import Volume


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
