"""Caching and persistence for loaded volumes."""

import json
from pathlib import Path

from backend.loaders.dicom import load_dicom_series

CACHE_FILE = Path("data/.last_loaded.json")

# Session kinds persisted in CACHE_FILE: a DICOM volume (with its file
# paths) or the demo phantom (rebuilt from the disk-cached forward
# projection on restore, see sidebar.load_demo_volume).
KIND_DICOM = "dicom"
KIND_DEMO = "demo"

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
    _save_session_record(KIND_DICOM, files)


def save_last_demo() -> None:
    """Record that the last session used the demo phantom."""
    _save_session_record(KIND_DEMO, [])


def _save_session_record(kind: str, files: list) -> None:
    """Write a ``{kind, files}`` record to the cache file."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Sort files to ensure consistent cache key
    sorted_files = sorted(files, key=lambda f: str(f))
    CACHE_FILE.write_text(
        json.dumps({"kind": kind, "files": [str(f) for f in sorted_files]})
    )


def load_last_session() -> tuple[str, list] | None:
    """Return ``(kind, files)`` of the last session, or None.

    A record without a ``kind`` (written before the restore button existed)
    is a DICOM volume. Only the first path is verified. Probing every slice
    of a large series can block for a long time on slow (network) drives.
    Missing later files surface as a load error, which callers handle with a
    demo fallback.
    """
    if not CACHE_FILE.exists():
        return None
    try:
        record = json.loads(CACHE_FILE.read_text())
    except Exception:
        return None
    files = [Path(f) for f in record.get("files", [])]
    kind = record.get("kind", KIND_DICOM)
    if kind == KIND_DICOM and (not files or not files[0].exists()):
        return None
    return (kind, files)


def load_last_loaded() -> list | None:
    """Load last saved DICOM file paths (None for a demo record)."""
    record = load_last_session()
    if record is None or record[0] != KIND_DICOM:
        return None
    return record[1]


def clear_last_loaded() -> None:
    """Clear the cache file and in-memory cache."""
    _volume_cache.clear()
    CACHE_FILE.unlink(missing_ok=True)
