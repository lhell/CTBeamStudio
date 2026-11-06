"""Import-cost guard for the 3D visualization module.

``pyvista`` costs ~5.6 s to import but is only needed for the off-screen
PyVista render mode. Importing it at module scope made every ``AppTest`` run
(and therefore the UI smoke test) pay that cost even when the Plotly path was
used. See plan.md T-81 step 4.
"""

import subprocess
import sys
from pathlib import Path

SRC_PATH = Path(__file__).resolve().parents[2] / "src"


def test_importing_volume3d_does_not_import_pyvista():
    """Importing the module must not pull in pyvista; only rendering needs it."""
    code = (
        "import sys; "
        f"sys.path.insert(0, {str(SRC_PATH)!r}); "
        "import visualization.volume3d; "
        "print('pyvista' in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "False"
