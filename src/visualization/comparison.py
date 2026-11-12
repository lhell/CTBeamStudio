"""Comparison metrics for real vs simulated projection images."""

from typing import Dict, Optional, Sequence

import numpy as np
import plotly.graph_objects as go

# (dict key, display name, y-axis): MAE/RMSE share the left axis,
# SSIM uses the right one.
_METRIC_ORDER = (
    ("mae", "MAE", "y"),
    ("rmse", "RMSE", "y"),
    ("ssim", "SSIM", "y2"),
)


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
    """Compute MAE, RMSE and SSIM between two images.

    Both inputs are converted to float64.
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

    data_range = float(
        max(real.max(), simulated.max()) - min(real.min(), simulated.min())
    )
    ssim = _ssim(real, simulated, data_range)

    return {
        "mae": mae,
        "rmse": rmse,
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
    per_frame = [compute_metrics(measured[i], simulated[i]) for i in range(n_proj)]
    return {
        key: np.asarray([frame[key] for frame in per_frame], dtype=np.float64)
        for key in ("mae", "rmse", "ssim")
    }


def build_metric_figure(
    per_slice: Dict[str, np.ndarray],
    current_index: int,
    proj_indices: Optional[Sequence[int]] = None,
) -> "go.Figure":
    """Line chart of every metric against the projection index.

    MAE/RMSE use the left y-axis; SSIM uses the right one. A
    vertical line marks the projection currently shown in the views.
    ``proj_indices`` (the gantry indices actually computed) replaces the
    plain 0..n-1 x-axis when given.
    """
    x_values = list(proj_indices) if proj_indices is not None else None
    traces = []
    for key, name, yaxis in _METRIC_ORDER:
        if key not in per_slice:
            continue
        values = np.asarray(per_slice[key], dtype=np.float64)
        if x_values is None or len(x_values) != len(values):
            xs = list(range(len(values)))
        else:
            xs = x_values
        traces.append(
            go.Scatter(
                x=xs,
                y=values,
                name=name,
                mode="lines",
                yaxis=yaxis,
            )
        )
    fig = go.Figure(data=traces)
    n_items = len(fig.data[0].x) if fig.data else 0
    if x_values:
        marker_x = x_values[min(current_index, len(x_values) - 1)]
    else:
        marker_x = min(current_index, max(n_items - 1, 0))
    fig.add_shape(
        type="line",
        x0=marker_x,
        x1=marker_x,
        y0=0,
        y1=1,
        yref="paper",
        line=dict(color="grey", dash="dash"),
    )
    fig.update_layout(
        xaxis_title="Projection",
        yaxis_title="MAE / RMSE",
        yaxis2=dict(
            overlaying="y",
            side="right",
            title="SSIM",
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=10, r=10, t=30, b=10),
    )
    return fig


def build_distribution_figure(per_slice: Dict[str, np.ndarray]) -> "go.Figure":
    """Overlaid histograms of each metric's per-projection values."""
    traces = []
    for key, name, _yaxis in _METRIC_ORDER:
        if key not in per_slice:
            continue
        traces.append(
            go.Histogram(
                x=np.asarray(per_slice[key], dtype=np.float64),
                name=name,
                histnorm="probability density",
                opacity=0.6,
            )
        )
    fig = go.Figure(data=traces)
    fig.update_layout(
        barmode="overlay",
        xaxis_title="Metric value",
        yaxis_title="Density",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=10, r=10, t=30, b=10),
    )
    return fig
