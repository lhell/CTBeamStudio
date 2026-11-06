"""Tests for real-vs-simulated projection comparison metrics."""

import numpy as np
import pytest

from visualization.comparison import compute_metrics, difference_image


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
