"""Tests for real-vs-simulated projection comparison metrics."""

import numpy as np
import pytest

from visualization.comparison import (
    build_distribution_figure,
    build_metric_figure,
    compute_metrics,
    compute_metrics_per_slice,
    difference_image,
)


def test_identical_images_have_zero_error():
    real = np.array([[0.0, 1.0], [2.0, 3.0]])
    sim = real.copy()

    metrics = compute_metrics(real, sim)

    assert metrics["mae"] == pytest.approx(0.0)
    assert metrics["rmse"] == pytest.approx(0.0)
    assert metrics["correlation"] == pytest.approx(1.0)
    assert metrics["ssim"] == pytest.approx(1.0)


def test_known_mae_and_rmse():
    real = np.array([[0.0, 1.0], [2.0, 3.0]])
    sim = np.zeros((2, 2))

    metrics = compute_metrics(real, sim)

    assert metrics["mae"] == pytest.approx(1.5)
    assert metrics["rmse"] == pytest.approx(np.sqrt(3.5))


def test_shape_mismatch_raises():
    with pytest.raises(ValueError, match="shape"):
        compute_metrics(np.zeros((2, 2)), np.zeros((2, 3)))


def test_constant_image_correlation_is_zero_not_nan():
    real = np.full((4, 4), 7.0)
    sim = np.full((4, 4), 7.0)

    metrics = compute_metrics(real, sim)

    assert metrics["correlation"] == pytest.approx(0.0)
    assert not np.isnan(metrics["correlation"])


def test_difference_image_is_real_minus_simulated():
    real = np.array([[1.0, 2.0]])
    sim = np.array([[0.5, 0.5]])

    diff = difference_image(real, sim)

    np.testing.assert_allclose(diff, [[0.5, 1.5]])


def test_per_slice_matches_frame_metrics():
    measured = np.random.default_rng(42).normal(size=(3, 5, 7))
    simulated = measured + 0.1

    per_slice = compute_metrics_per_slice(measured, simulated)

    assert set(per_slice) == {"mae", "rmse", "correlation", "ssim"}
    for values in per_slice.values():
        assert values.shape == (3,)
    for i in range(3):
        frame = compute_metrics(measured[i], simulated[i])
        for key, value in frame.items():
            assert per_slice[key][i] == pytest.approx(value)


def test_per_slice_raises_shape_mismatch():
    with pytest.raises(ValueError, match="shape"):
        compute_metrics_per_slice(np.zeros((2, 4, 4)), np.zeros((3, 4, 4)))


def test_per_slice_single_projection():
    per_slice = compute_metrics_per_slice(np.ones((1, 4, 4)), np.ones((1, 4, 4)))

    assert per_slice["mae"].shape == (1,)
    assert per_slice["mae"][0] == pytest.approx(0.0)


def test_build_metric_figure_traces_and_marker():
    per_slice = compute_metrics_per_slice(np.zeros((4, 6, 6)), np.zeros((4, 6, 6)))
    per_slice["mae"] = np.array([0.0, 1.0, 2.0, 3.0])

    fig = build_metric_figure(per_slice, current_index=2)

    assert [t.name for t in fig.data] == ["MAE", "RMSE", "Correlation", "SSIM"]
    np.testing.assert_array_equal(fig.data[0].x, [0, 1, 2, 3])
    np.testing.assert_array_equal(fig.data[0].y, [0.0, 1.0, 2.0, 3.0])
    assert len(fig.layout.shapes) == 1
    assert fig.layout.shapes[0].x0 == 2


def test_build_metric_figure_accepts_proj_indices():
    per_slice = {"mae": np.arange(3.0)}

    fig = build_metric_figure(per_slice, current_index=0, proj_indices=[10, 40, 220])

    assert [t.name for t in fig.data] == ["MAE"]
    assert list(fig.data[0].x) == [10, 40, 220]
    assert fig.layout.shapes[0].x0 == 10


def test_build_distribution_figure_histograms_overlay():
    values = {k: np.linspace(0.0, 1.0, 12) for k in ("mae", "rmse", "correlation", "ssim")}

    fig = build_distribution_figure(values)

    assert [t.type for t in fig.data] == ["histogram"] * 4
    assert [t.name for t in fig.data] == ["MAE", "RMSE", "Correlation", "SSIM"]
    assert fig.layout.barmode == "overlay"
    assert all(t.opacity == 0.6 for t in fig.data)
