"""Tests for the persistent projection-geometry cache."""

import json

from backend.geometry import ProjectionGeometry
from visualization.geometry_cache import (
    clear_cached_geometry,
    default_geometry,
    load_cached_geometry,
    save_cached_geometry,
)


def test_load_cached_geometry_returns_none_when_missing(tmp_path):
    assert load_cached_geometry(tmp_path / "missing.json") is None


def test_save_and_load_geometry_roundtrip(tmp_path):
    path = tmp_path / "geometry.json"
    geometry = ProjectionGeometry(
        sdd=1200.0,
        sid=600.0,
        n_det_cols=128,
        n_det_rows=32,
        geometry_type="cone_beam",
        source="Test Scanner",
    )

    save_cached_geometry(geometry, path)
    loaded = load_cached_geometry(path)

    assert loaded == geometry


def test_default_geometry_uses_cached_geometry(tmp_path):
    path = tmp_path / "geometry.json"
    cached = ProjectionGeometry(sdd=900.0, sid=450.0)
    save_cached_geometry(cached, path)

    assert default_geometry(path) == cached


def test_default_geometry_falls_back_to_dataclass_defaults(tmp_path):
    path = tmp_path / "geometry.json"

    assert default_geometry(path) == ProjectionGeometry()


def test_clear_cached_geometry_removes_file(tmp_path):
    path = tmp_path / "geometry.json"
    save_cached_geometry(ProjectionGeometry(sdd=900.0, sid=450.0), path)
    assert path.exists()

    clear_cached_geometry(path)

    assert not path.exists()
    assert load_cached_geometry(path) is None


def test_load_cached_geometry_ignores_corrupt_json(tmp_path):
    path = tmp_path / "geometry.json"
    path.write_text("{not valid json")

    assert load_cached_geometry(path) is None


def test_load_cached_geometry_ignores_invalid_values(tmp_path):
    path = tmp_path / "geometry.json"
    path.write_text(json.dumps({"sdd": 1000.0, "sid": 2000.0}))

    assert load_cached_geometry(path) is None
