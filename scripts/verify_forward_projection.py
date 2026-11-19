"""End-to-end check: a real forward projection must produce non-zero data.

Run inside the activated ct-viewer conda env (parallelproj_c.dll only
resolves there). Not part of the pytest suite: it needs the compiled
parallelproj backend, which CI installs but a bare checkout does not.

The geometry and volume mirror tests/integration/test_projection_workflow.py:
a dense central block inside a volume whose origin is offset so it is
centred on the rotation axis. Projections come out zero if the volume sits
outside the field of view, which is a geometry mistake, not a backend bug.

CUDA is used automatically when available; pass ``--cpu`` to build the LOR
geometry on the CPU. parallelproj itself picks the projection kernel from the
installed library build (see ``src/backend/parallelproj/projector.py``).
"""

import argparse
import sys

sys.path.insert(0, "src")

import numpy as np

from backend.forward_project import PARALLELPROJ_AVAILABLE, forward_project
from backend.geometry import ProjectionGeometry
from backend.volume import Volume


def _torch_cuda_available() -> bool:
    try:
        import torch
    except ImportError:  # pragma: no cover - manual script outside the env
        return False
    return bool(torch.cuda.is_available())


def _parallelproj_cuda_devices() -> int:
    try:
        import parallelproj
    except ImportError:  # pragma: no cover - manual script outside the env
        return 0
    return int(getattr(parallelproj, "num_visible_cuda_devices", 0))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cpu",
        action="store_true",
        help="build the LOR geometry on the CPU instead of auto-selecting CUDA",
    )
    args = parser.parse_args()

    use_cuda = (not args.cpu) and _torch_cuda_available()
    print("PARALLELPROJ_AVAILABLE:", PARALLELPROJ_AVAILABLE)
    print("LOR geometry device:", "cuda" if use_cuda else "cpu")
    print("parallelproj sees CUDA devices:", _parallelproj_cuda_devices())
    assert PARALLELPROJ_AVAILABLE, "parallelproj + torch must both be importable"

    geometry = ProjectionGeometry(
        sdd=1000.0,
        sid=500.0,
        n_det_rows=8,
        n_det_cols=8,
        det_row_spacing_mm=2.0,
        det_col_spacing_mm=2.0,
        projections_per_rotation=8,
    )

    array = np.zeros((16, 16, 16), dtype=np.float32)
    array[6:10, 6:10, 6:10] = 0.02
    volume = Volume(
        array=array,
        spacing=(1.0, 1.0, 1.0),
        origin=(-7.5, -7.5, -7.5),
        meta={"unit": "1/mm"},
    )

    result = forward_project(volume, geometry, use_cuda=use_cuda)
    projections = result.projections

    print("shape:", projections.shape)
    print("dtype:", projections.dtype)
    print(
        "min: %.6g  max: %.6g  mean: %.6g"
        % (projections.min(), projections.max(), projections.mean())
    )
    print(
        "non-zero fraction: %.3f"
        % (float(np.count_nonzero(projections)) / float(projections.size))
    )

    assert projections.shape == (8, 8, 8), projections.shape
    assert np.isfinite(projections).all(), "projection contains non-finite values"
    assert projections.max() > 0, "projection is all zeros -- not a real projection"

    print("OK: real forward projection produced non-zero data")


if __name__ == "__main__":
    main()
