import numpy as np
import pytest
from backend.loaders.sinogram import SelectionConfig, SinogramData, resolve_indices


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
