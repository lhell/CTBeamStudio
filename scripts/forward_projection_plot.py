"""Visual test for forward_project: volume + 0° projection in world orientation.

Run this from PyCharm with the ``ct-viewer`` conda environment (Python 3.12,
which has parallelproj installed). It builds a small 4-region test volume,
forward-projects it at 0°, and displays both with matplotlib using correct
*world* axes (x / y / z), plus the source and detector positions of the beam.

## World convention used here

DICOM / project world space is right-handed ``(x, y, z)``:
    - ``x`` = anterior / posterior (source at 0° sits on ``+x``, the detector
      on ``-x``),
    - ``y`` = left / right (transaxial, in-plane),
    - ``z`` = feet / head (axial, slice direction; ``+z`` = up on screen).

At 0° the X-rays travel along ``+x -> -x`` (front to back), so the projection
is the detector image seen with:
    - horizontal axis = ``y`` (transaxial, ``-y`` on the left, ``+y`` right),
    - vertical axis   = ``z`` (axial, ``-z`` at the bottom, ``+z`` at top).

Requires: numpy, matplotlib, parallelproj (in ct-viewer env).
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  (activates 3D projection)

# Make sure the project's src/ is importable when running from PyCharm.
SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backend.forward_project import PARALLELPROJ_AVAILABLE, forward_project
from backend.geometry import ProjectionGeometry
from backend.volume import Volume


def make_volume(n: int = 16) -> Volume:
    """``(z, y, x)`` volume with four labelled quadrants in the ``(z, y)`` plane.

    Region values (constant over all ``x``), in world orientation:
        1 -> low z, low y      (front-bottom-left in world)
        2 -> low z, high y     (front-bottom-right)
        3 -> high z, low y     (front-top-left)
        4 -> high z, high y    (front-top-right)

    The volume is centred around the isocenter.
    """
    vol = np.zeros((n, n, n), dtype=np.float32)
    vol[0 : n // 2, 0 : n // 2, :] = 1.0
    vol[0 : n // 2, n // 2 : n, :] = 2.0
    vol[n // 2 : n, 0 : n // 2, :] = 3.0
    vol[n // 2 : n, n // 2 : n, :] = 4.0

    spacing = (1.0, 1.0, 1.0)  # (dz, dy, dx)
    origin = tuple(-(n - 1) / 2.0 * s for s in spacing)  # DICOM (x, y, z)
    return Volume(array=vol, spacing=spacing, origin=origin, meta={})


def main() -> None:
    print(f"parallelproj available: {PARALLELPROJ_AVAILABLE}")
    if not PARALLELPROJ_AVAILABLE:
        print(
            "WARNING: parallelproj not installed. Use the ct-viewer conda "
            "environment to see a real projection."
        )

    n = 16
    volume = make_volume(n)

    # Small, fast 0° cone-beam geometry covering the whole volume at 2×
    # magnification (sid=500, sdd=1000), 1 mm detector pixels.
    sid, sdd = 500.0, 1000.0
    geometry = ProjectionGeometry(
        sid=sid,
        sdd=sdd,
        n_det_cols=32,
        n_det_rows=32,
        det_col_spacing_mm=1.0,
        det_row_spacing_mm=1.0,
        projections_per_rotation=1,
    )

    result = forward_project(volume, geometry, use_cuda=False)
    proj = result.projections[0]  # (rows=z, cols=y) at 0°
    print(f"projection shape: {result.projections.shape}")
    print(f"projection min/max: {proj.min():.3f} / {proj.max():.3f}")

    # World positions of the axial slice center and of source/detector.
    zc = n // 2  # central (mid) slice index
    y_extent = (n - 1) / 2.0  # half-width of the volume in world mm

    # --- Plot ---------------------------------------------------------------
    fig = plt.figure(figsize=(16, 5.5))
    gs = fig.add_gridspec(1, 3, width_ratios=[1, 1, 1])
    axes = [
        fig.add_subplot(gs[0]),
        fig.add_subplot(gs[1]),
        fig.add_subplot(gs[2], projection="3d"),
    ]

    # Left: axial slice (y, x plane) at mid-z, in world orientation.
    ax = axes[0]
    im = ax.imshow(volume.array[zc, :, :], origin="lower", cmap="viridis")
    ax.set_title(f"Volume — axial slice z={zc} (plane y–x)")
    ax.set_xlabel("x (anterior +, posterior -)")
    ax.set_ylabel("y (right +, left -)")
    ax.set_xticks([0, n - 1])
    ax.set_yticks([0, n - 1])
    fig.colorbar(im, ax=ax, fraction=0.046)

    # Overlay the source (+) and detector (×) projected onto this slice, and
    # the X-ray direction (front -> back along +x -> -x).
    ax.scatter(
        [n - 1], [n / 2 - 0.5], marker="+", s=160, color="red", label="source (+x)"
    )
    ax.scatter(
        [0], [n / 2 - 0.5], marker="x", s=120, color="blue", label="detector (-x)"
    )
    ax.annotate(
        "",
        xy=(0.5, n / 2 - 0.5),
        xytext=(n - 2, n / 2 - 0.5),
        arrowprops=dict(arrowstyle="->", color="k", lw=1.5),
    )
    ax.text(n / 2, n * 0.9, "X-ray direction", ha="center", fontsize=8)
    ax.legend(loc="lower right", fontsize=7)

    # Right: the 0° projection in world orientation.
    #   horizontal axis = y (transaxial), vertical axis = z (axial, +z up).
    # `proj` has rows=z (row 0 = low z -> bottom) and cols=y (col 0 = low y
    # -> left), so origin="lower" maps it directly onto world axes.
    ax = axes[1]
    im = ax.imshow(proj, origin="lower", cmap="viridis")
    ax.set_title("0° forward projection (source on +x)")
    ax.set_xlabel("y (transaxial, right +, left -)")
    ax.set_ylabel("z (axial, head +)")
    ax.set_xticks([0, proj.shape[1] - 1])
    ax.set_yticks([0, proj.shape[0] - 1])
    ax.set_xticklabels([f"-{y_extent:.0f}", f"+{y_extent:.0f}"])
    ax.set_yticklabels([f"-{y_extent:.0f}", f"+{y_extent:.0f}"])
    fig.colorbar(im, ax=ax, fraction=0.046)

    # Right-center: 3D view of the volume in world orientation.
    ax = axes[2]
    # volume.array is (z, y, x); transpose to (x, y, z) so the 3D axes are the
    # world axes. Downsample for a lighter render. Each of the four labelled
    # regions (values 1..4) is coloured via the viridis colormap.
    vol3 = volume.array.transpose(2, 1, 0)[::2, ::2, ::2]
    occupied = vol3 > 0
    cmap = plt.get_cmap("viridis")
    facecolors = np.empty(occupied.shape + (4,))
    for idx in np.ndindex(occupied.shape):
        v = vol3[idx]
        facecolors[idx] = cmap((v - 1.0) / 3.0 if v > 0 else 0.0)
    ax.voxels(
        occupied,
        facecolors=facecolors,
        edgecolor="k",
        linewidth=0.1,
        alpha=0.85,
    )
    ax.set_title("Volume — 3D view (world axes)")
    ax.set_xlabel("x (anterior/posterior)")
    ax.set_ylabel("y (left/right)")
    ax.set_zlabel("z (axial, head +)")

    fig.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
