from pathlib import Path

import numpy as np
import pytest
from backend.loaders.sinogram import (
    SelectionConfig,
    SinogramData,
    _detect_format,
    _load_numpy,
    load_sinogram,
    resolve_indices,
)


def test_resolve_all():
    assert resolve_indices("all", 10) == list(range(10))


def test_resolve_central():
    assert resolve_indices("central", 10, range_=(3, 7)) == [3, 4, 5, 6]


def test_resolve_range():
    assert resolve_indices("range", 10, range_=(2, 5)) == [2, 3, 4]


def test_resolve_downsample():
    assert resolve_indices("downsample", 10, downsample=3) == [0, 3, 6, 9]


def test_resolve_custom():
    assert resolve_indices("custom", 10, custom=[0, 2, 5]) == [0, 2, 5]


def test_resolve_bad_mode():
    with pytest.raises(ValueError):
        resolve_indices("bogus", 10)


def test_resolve_range_out_of_bounds():
    with pytest.raises(IndexError):
        resolve_indices("range", 5, range_=(0, 10))


def test_resolve_empty_result_raises():
    with pytest.raises(ValueError):
        resolve_indices("central", 5, range_=(5, 5))


def test_axis_order_default_is_canonical():
    s = SinogramData(data=None, geometry=None, selection=SelectionConfig(),
                     original_shape=(3, 4, 5), source_axis_order=("proj", "row", "col"))
    assert s.axis_order == ("proj", "row", "col")


def test_axis_order_invalid_raises():
    s = SinogramData(data=None, geometry=None, selection=SelectionConfig(),
                     original_shape=(3, 4, 5), source_axis_order=("proj", "row", "col"))
    with pytest.raises(ValueError):
        s.axis_order = ("proj", "row")  # not a permutation


def test_materialize_replaces_none_with_loader_result():
    s = SinogramData(data=None, geometry=None, selection=SelectionConfig(),
                     original_shape=(3, 4, 5), source_axis_order=("proj", "row", "col"),
                     _loader=lambda: np.zeros((3, 4, 5)))
    out = s.materialize()
    assert out.shape == (3, 4, 5)
    assert s.data.shape == (3, 4, 5)


def test_detect_format_npy(tmp_path):
    p = tmp_path / "a.npy"; p.touch()
    assert _detect_format(p) == "numpy"

def test_detect_format_npz(tmp_path):
    p = tmp_path / "a.npz"; p.touch()
    assert _detect_format(p) == "numpy"

def test_detect_format_unknown(tmp_path):
    p = tmp_path / "a.xyz"; p.touch()
    assert _detect_format(p) == "unknown"

def test_load_numpy_full(tmp_path):
    arr = np.zeros((3, 4, 5)); p = tmp_path / "s.npy"
    np.save(p, arr)
    s = _load_numpy(p, SelectionConfig(), ("proj", "row", "col"))
    assert s.data.shape == (3, 4, 5)
    assert s.original_shape == (3, 4, 5)

def test_load_numpy_selected_rows(tmp_path):
    arr = np.arange(60).reshape(3, 4, 5); p = tmp_path / "s.npy"
    np.save(p, arr)
    sel = SelectionConfig(row_mode="range", row_range=(1, 3))
    s = _load_numpy(p, sel, ("proj", "row", "col"))
    assert s.data.shape == (3, 2, 5)
    np.testing.assert_array_equal(s.data[:, 0], arr[:, 1])

def test_load_numpy_axis_order_normalizes(tmp_path):
    # file stored (row, proj, col) -> canonical (proj, row, col)
    arr = np.arange(24).reshape(2, 3, 4)  # (row, proj, col)
    p = tmp_path / "s.npy"; np.save(p, arr)
    s = _load_numpy(p, SelectionConfig(), ("row", "proj", "col"))
    assert s.data.shape == (3, 2, 4)
    assert s.source_axis_order == ("row", "proj", "col")

def test_load_npy_confused_ext(tmp_path):
    p = tmp_path / "a.xyz"; p.touch()
    with pytest.raises(ValueError):
        load_sinogram(p)

def test_load_sinogram_numpy(tmp_path):
    arr = np.zeros((3, 4, 5)); p = tmp_path / "s.npy"
    np.save(p, arr)
    s = load_sinogram(p)
    assert s.data.shape == (3, 4, 5)
    assert s.format == "numpy"
