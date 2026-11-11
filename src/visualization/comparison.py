"""Comparison metrics for real vs simulated projection images."""

from typing import Dict

import numpy as np


def difference_image(real: np.ndarray, simulated: np.ndarray) -> np.ndarray:
    """Return the signed difference ``real - simulated`` as float64."""
    real = np.asarray(real, dtype=np.float64)
    simulated = np.asarray(simulated, dtype=np.float64)
    if real.shape != simulated.shape:
        raise ValueError(
            "real and simulated images must have the same shape, got "
            f"{real.shape} and {simulated.shape}"
        )
    return real - simulated


def _pearson_correlation(real: np.ndarray, simulated: np.ndarray) -> float:
    """Pearson correlation, defined as 0.0 for constant input."""
    real_centered = real - real.mean()
    sim_centered = simulated - simulated.mean()
    denom = np.sqrt(np.sum(real_centered**2) * np.sum(sim_centered**2))
    if denom == 0:
        return 0.0
    return float(np.sum(real_centered * sim_centered) / denom)


def _ssim(real: np.ndarray, simulated: np.ndarray, data_range: float) -> float:
    """Structural similarity, with a small-image / constant fallback."""
    if data_range == 0:
        return 1.0

    try:
        from skimage.metrics import structural_similarity
    except ImportError:  # pragma: no cover - optional in minimal environments
        mae = float(np.mean(np.abs(real - simulated)))
        return float(max(0.0, 1.0 - mae / data_range))

    min_dim = min(real.shape)
    if min_dim < 3:
        mae = float(np.mean(np.abs(real - simulated)))
        return float(max(0.0, 1.0 - mae / data_range))

    win_size = min(7, min_dim)
    if win_size % 2 == 0:
        win_size -= 1
    return float(
        structural_similarity(
            real,
            simulated,
            data_range=data_range,
            win_size=win_size,
        )
    )


def compute_metrics(real: np.ndarray, simulated: np.ndarray) -> Dict[str, float]:
    """Compute MAE, RMSE, Pearson correlation and SSIM between two images.

    Both inputs are converted to float64. For constant images where a
    correlation is undefined, ``correlation`` is reported as ``0.0``.
    """
    real = np.asarray(real, dtype=np.float64)
    simulated = np.asarray(simulated, dtype=np.float64)
    if real.shape != simulated.shape:
        raise ValueError(
            "real and simulated images must have the same shape, got "
            f"{real.shape} and {simulated.shape}"
        )

    diff = real - simulated
    mae = float(np.mean(np.abs(diff)))
    rmse = float(np.sqrt(np.mean(diff**2)))
    correlation = _pearson_correlation(real, simulated)

    data_range = float(
        max(real.max(), simulated.max()) - min(real.min(), simulated.min())
    )
    ssim = _ssim(real, simulated, data_range)

    return {
        "mae": mae,
        "rmse": rmse,
        "correlation": correlation,
        "ssim": ssim,
    }


def compute_metrics_per_slice(
    measured: np.ndarray, simulated: np.ndarray
) -> Dict[str, np.ndarray]:
    """Compute per-projection metric series for two sinogram stacks.

    Both inputs are canonical ``(n_proj, rows, cols)`` stacks; frame ``i``
    of each is compared with :func:`compute_metrics`. Returns a dict with
    the same keys, each mapping to a float64 array of shape ``(n_proj,)``.
    """
    measured = np.asarray(measured, dtype=np.float64)
    simulated = np.asarray(simulated, dtype=np.float64)
    if measured.shape != simulated.shape:
        raise ValueError(
            "measured and simulated stacks must have the same shape, got "
            f"{measured.shape} and {simulated.shape}"
        )

    n_proj = measured.shape[0]
    per_frame = [
        compute_metrics(measured[i], simulated[i]) for i in range(n_proj)
    ]
    return {
        key: np.asarray([frame[key] for frame in per_frame], dtype=np.float64)
        for key in ("mae", "rmse", "correlation", "ssim")
    }
