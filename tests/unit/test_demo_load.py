"""Tests for the auto-generated dummy measurement on demo image load (T-96).

Loading the demo phantom ("Load Demo Phantom" in the empty state) must seed
the coherent demo trio — phantom volume, dummy CBCT geometry and a synthetic
measured sinogram — so the Sinogram Inspection comparison goes live without
real scanner data. The heavy generator is stubbed here (its numerics are
covered in tests/test_dummy_measurement.py).
"""

from pathlib import Path

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from backend.geometry import ProjectionGeometry
from backend.loaders.sinogram import SelectionConfig, SinogramData
from visualization.phantom import DummyMeasurement, create_demo_volume

APP_PATH = Path(__file__).resolve().parents[2] / "src" / "visualization" / "app.py"


@pytest.fixture(scope="module")
def app():
    """A fresh session: nothing loaded, so the app renders the empty state."""
    at = AppTest.from_file(str(APP_PATH), default_timeout=90)
    at.run()
    return at


def _stub_dummy_measurement() -> DummyMeasurement:
    """A tiny coherent stand-in for the (expensive) real generator."""
    geometry = ProjectionGeometry(
        n_det_cols=8,
        n_det_rows=4,
        projections_per_rotation=3,
        source="dummy-test",
    )
    data = np.zeros((3, 4, 8), dtype=np.float32)
    sinogram = SinogramData(
        data=data,
        geometry=geometry,
        selection=SelectionConfig(),
        original_shape=data.shape,
        source_axis_order=("proj", "row", "col"),
        path=None,
        format="synthetic",
    )
    return DummyMeasurement(
        volume=create_demo_volume(),
        geometry=geometry,
        sinogram=sinogram,
        params={
            "energy_kev": 70.0,
            "spr": 0.3,
            "scatter_sigma_mm": 25.0,
            "i0": 1e5,
            "seed": 42,
            "fp_from_cache": False,
        },
    )


def test_demo_load_seeds_the_coherent_trio(app, tmp_path, monkeypatch):
    """Loading the demo phantom generates the dummy measurement automatically:
    volume + dummy geometry + sinogram are seeded together and the sample
    selection is preset to "all", so the comparison is ready without a file."""
    from visualization import volume_cache

    monkeypatch.setattr(volume_cache, "CACHE_FILE", tmp_path / "last_loaded.json")
    monkeypatch.setattr(
        "visualization.phantom.create_dummy_measured_sinogram",
        _stub_dummy_measurement,
    )

    app.button(key="empty_load_demo").click()
    app.run()

    assert list(app.exception) == []
    sinogram = app.session_state["sinogram"]
    assert sinogram.data.shape == (3, 4, 8)
    assert sinogram.format == "synthetic"
    assert sinogram.path is None
    geometry = app.session_state["projection_geometry"]
    assert geometry.source == "dummy-test"
    assert app.session_state["geometry_is_default"] is False
    assert app.session_state["demo_mode"] is True
    # "all" reproduces the dummy exactly on "Run Forward Projection".
    assert app.session_state["sample_proj_mode"] == "all"
    assert app.session_state["sample_row_mode"] == "all"
    assert app.session_state["sample_col_mode"] == "all"


def test_demo_load_replaces_previously_loaded_data(app, tmp_path, monkeypatch):
    """The demo trio is self-contained: it replaces whatever volume,
    geometry and measurement were in session state before."""
    from visualization import volume_cache

    monkeypatch.setattr(volume_cache, "CACHE_FILE", tmp_path / "last_loaded.json")
    app.session_state["volume"] = None
    app.session_state["sinogram"] = None
    app.session_state["projection_geometry"] = ProjectionGeometry(
        source="user-geometry"
    )
    app.run()

    monkeypatch.setattr(
        "visualization.phantom.create_dummy_measured_sinogram",
        _stub_dummy_measurement,
    )

    app.button(key="empty_load_demo").click()
    app.run()

    assert list(app.exception) == []
    assert app.session_state["sinogram"].data.shape == (3, 4, 8)
    assert app.session_state["projection_geometry"].source == "dummy-test"


def test_empty_state_restores_the_demo_session(app, tmp_path, monkeypatch):
    """After a reload (new session, empty state) the restore button rebuilds
    the demo trio from the persisted record."""
    from visualization import volume_cache

    monkeypatch.setattr(volume_cache, "CACHE_FILE", tmp_path / "last_loaded.json")
    volume_cache.save_last_demo()
    monkeypatch.setattr(
        "visualization.phantom.create_dummy_measured_sinogram",
        _stub_dummy_measurement,
    )

    app.session_state["volume"] = None
    app.session_state["demo_mode"] = False
    app.run()

    app.button(key="empty_restore").click()
    app.run()

    assert list(app.exception) == []
    assert app.session_state["sinogram"].data.shape == (3, 4, 8)
    assert app.session_state["demo_mode"] is True
