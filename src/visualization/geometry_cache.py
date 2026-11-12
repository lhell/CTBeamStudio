"""Persistent cache for the projection geometry shown in the app.

The last loaded or edited geometry is stored as JSON so it can be restored on
the next start. If the cache is missing or invalid, the dataclass defaults are
used.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from backend.geometry import ProjectionGeometry

CACHE_FILE = Path("data/.last_geometry.json")


def save_cached_geometry(
    geometry: ProjectionGeometry, path: Optional[Path] = None
) -> None:
    """Write ``geometry`` to the cache file."""
    cache_path = path or CACHE_FILE
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(asdict(geometry), indent=2))


def load_cached_geometry(path: Optional[Path] = None) -> Optional[ProjectionGeometry]:
    """Return the cached geometry, or ``None`` if unavailable or invalid."""
    cache_path = path or CACHE_FILE
    if not cache_path.exists():
        return None

    try:
        data = json.loads(cache_path.read_text())
        return ProjectionGeometry(**data)
    except (OSError, ValueError, TypeError):
        return None


def default_geometry(path: Optional[Path] = None) -> ProjectionGeometry:
    """Return the cached geometry or the dummy-phantom geometry.

    The dummy CBCT geometry (``visualization.phantom.create_dummy_geometry``)
    is the default: it is sized to the standard Shepp-Logan head, so the
    empty state and the demo stay coherent (same detector, same scan).
    """
    cached = load_cached_geometry(path)
    if cached is not None:
        return cached
    from visualization.phantom import create_dummy_geometry

    return create_dummy_geometry()


def clear_cached_geometry(path: Optional[Path] = None) -> None:
    """Remove the geometry cache file if it exists."""
    (path or CACHE_FILE).unlink(missing_ok=True)
