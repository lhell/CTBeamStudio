"""Pytest configuration for tests."""

import sys
from pathlib import Path

# Add project root to path for imports (so "from src.visualization..." works)
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
