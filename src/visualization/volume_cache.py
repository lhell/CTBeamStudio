"""Caching and persistence for loaded volumes."""

import json
from pathlib import Path

from backend.loaders.dicom import load_dicom_series

CACHE_FILE = Path("data/.last_loaded.json")

# In-memory cache keyed by sorted tuple of file paths
_volume_cache: dict[tuple, object] = {}


def load_volume_cached(
    file_paths_str: list, unit: str | None = None, _progress_callback=None
):
    """Load volume from file paths with in-memory caching.

    Uses a simple dict cache keyed by sorted file paths.
    Cache persists for the lifetime of the server process.
    """
    # Create cache key from sorted file paths
    cache_key = tuple(sorted(file_paths_str))

    # Check cache first
    if cache_key in _volume_cache:
        return _volume_cache[cache_key]

    # Not cached - load the volume
    files = [Path(p) for p in file_paths_str]
    volume = load_dicom_series(files, unit=unit, progress=_progress_callback)

    # Store in cache
    _volume_cache[cache_key] = volume

    return volume


def save_last_loaded(files: list) -> None:
    """Save last loaded file paths to cache file."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Sort files to ensure consistent cache key
    sorted_files = sorted(files, key=lambda f: str(f))
    CACHE_FILE.write_text(json.dumps({"files": [str(f) for f in sorted_files]}))


def load_last_loaded() -> list | None:
    """Load last saved file paths from cache file.

    Only the first path is verified. Probing every slice of a large series
    can block for a long time on slow (network) drives. Missing later files
    surface as a load error, which callers handle with a demo fallback.
    """
    if not CACHE_FILE.exists():
        return None
    try:
        files = [Path(f) for f in json.loads(CACHE_FILE.read_text()).get("files", [])]
        return files if files and files[0].exists() else None
    except Exception:
        return None


def clear_last_loaded() -> None:
    """Clear the cache file and in-memory cache."""
    _volume_cache.clear()
    CACHE_FILE.unlink(missing_ok=True)
