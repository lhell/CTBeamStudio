"""End-to-end check: a real forward projection must produce non-zero data.

Run inside the activated ct-viewer conda env (parallelproj_c.dll only
resolves there). Not part of the pytest suite: it needs the compiled
parallelproj backend, which CI installs but a bare checkout does not.

The geometry and volume mirror tests/integration/test_projection_workflow.py:
a dense central block inside a volume whose origin is offset so it is
centred on the rotation axis. Projections come out zero if the volume sits
outside the field of view, which is a geometry mistake, not a backend bug.
"""

import sys

sys.path.insert(0, "src")

import numpy as np

from backend.forward_project import PARALLELPROJ_AVAILABLE, forward_project
from backend.geometry import ProjectionGeometry
from backend.volume import Volume

print("PARALLELPROJ_AVAILABLE:", PARALLELPROJ_AVAILABLE)
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

result = forward_project(volume, geometry, use_cuda=False)
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
