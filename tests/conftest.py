"""Pytest configuration for tests."""

import sys
from pathlib import Path

# Remove tests/ from path (it shadows src/)
test_dir = str(Path(__file__).parent.resolve())
if test_dir in sys.path:
    sys.path.remove(test_dir)

# Add src to path for imports (so "from visualization..." works)
src_path = str((Path(__file__).parent.parent / "src").resolve())
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Debug
import visualization.windowing
print(f"[conftest] OK - visualization.windowing found at {visualization.windowing.__file__}")


