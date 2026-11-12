"""End-to-end workflow: measured sinogram -> forward projection -> metrics.

Requires ``parallelproj`` (run inside the ``ct-viewer`` conda environment).
The test is skipped automatically when parallelproj is not installed.
"""

from pathlib import Path

import numpy as np
import pytest

parallelproj = pytest.importorskip("parallelproj")

from backend.forward_project import forward_project
from backend.geometry import ProjectionGeometry
from backend.loaders.sinogram import SelectionConfig, load_sinogram
from backend.volume import Volume
from visualization.comparison import compute_metrics


@pytest.fixture(scope="module")
def geometry() -> ProjectionGeometry:
    return ProjectionGeometry(
        sdd=1000.0,
        sid=500.0,
        n_det_rows=8,
        n_det_cols=8,
        det_row_spacing_mm=2.0,
        det_col_spacing_mm=2.0,
        projections_per_rotation=8,
    )


@pytest.fixture(scope="module")
def volume() -> Volume:
    # 16^3 attenuation volume (1/mm) with a dense central block so projections
    # are non-zero. Forward projection requires attenuation, not HU.
    array = np.zeros((16, 16, 16), dtype=np.float32)
    array[6:10, 6:10, 6:10] = 0.02
    return Volume(
        array=array,
        spacing=(1.0, 1.0, 1.0),
        origin=(-7.5, -7.5, -7.5),
        meta={"unit": "1/mm"},
    )


def test_measured_workflow_matches_forward_projection(tmp_path, geometry, volume):
    measured = forward_project(volume, geometry, use_cuda=False)
    measured_path = tmp_path / "measured.npy"
    np.save(measured_path, measured.projections)

    loaded = load_sinogram(
        Path(measured_path),
        selection=SelectionConfig(),
        geometry=geometry,
        axis_order=("proj", "row", "col"),
    )
    assert loaded.data.shape == measured.projections.shape

    simulated = forward_project(volume, geometry, use_cuda=False)

    metrics = compute_metrics(loaded.data, simulated.projections)
    assert metrics["mae"] == pytest.approx(0.0, abs=1e-5)
    assert metrics["rmse"] == pytest.approx(0.0, abs=1e-5)
    assert metrics["ssim"] == pytest.approx(1.0, abs=1e-5)


def test_non_contiguous_selection_workflow(tmp_path, geometry, volume):
    full = forward_project(volume, geometry, use_cuda=False)
    selection = SelectionConfig(proj_mode="downsample", proj_downsample=3)
    selected = forward_project(volume, geometry, use_cuda=False, proj_indices=[0, 3, 6])

    selected_path = tmp_path / "selected.npy"
    np.save(selected_path, selected.projections)
    loaded = load_sinogram(
        Path(selected_path),
        selection=SelectionConfig(),
        geometry=geometry,
        axis_order=("proj", "row", "col"),
    )

    np.testing.assert_allclose(
        loaded.data, full.projections[[0, 3, 6]], rtol=1e-5, atol=1e-5
    )
    assert selection.proj_downsample == 3
