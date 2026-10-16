"""Pytest configuration for tests."""

import sys
from pathlib import Path

# Add src to path for imports (so "from visualization..." works)
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
