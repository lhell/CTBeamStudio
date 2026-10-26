"""Caching and persistence for loaded volumes."""

import json
from pathlib import Path

from visualization.loaders.dicom import load_dicom_series

CACHE_FILE = Path("data/.last_loaded.json")


def load_volume_cached(
    file_paths_str: list, unit: str | None = None, _progress_callback=None
):
    """Load volume from file paths (no caching due to Volume serialization issues)."""
    files = [Path(p) for p in file_paths_str]
    return load_dicom_series(files, unit=unit, progress=_progress_callback)


def save_last_loaded(files: list) -> None:
    """Save last loaded file paths to cache file."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps({"files": [str(f) for f in files]}))


def load_last_loaded() -> list | None:
    """Load last saved file paths from cache file."""
    if not CACHE_FILE.exists():
        return None
    try:
        files = [Path(f) for f in json.loads(CACHE_FILE.read_text()).get("files", [])]
        return files if files and all(f.exists() for f in files) else None
    except Exception:
        return None


def clear_last_loaded() -> None:
    """Clear the cache file."""
    CACHE_FILE.unlink(missing_ok=True)
