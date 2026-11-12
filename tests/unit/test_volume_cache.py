"""Tests for volume_cache.py."""

import json
from pathlib import Path

import pytest

from visualization import volume_cache


def _write_cache(tmp_path: Path, files: list[Path]) -> Path:
    cache_file = tmp_path / "last_loaded.json"
    cache_file.write_text(json.dumps({"files": [str(f) for f in files]}))
    return cache_file


class TestLoadLastLoaded:
    """Behaviour of the persisted 'last loaded' series lookup."""

    def test_returns_none_without_cache_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(volume_cache, "CACHE_FILE", tmp_path / "missing.json")

        assert volume_cache.load_last_loaded() is None

    def test_returns_files_when_first_file_exists(self, tmp_path, monkeypatch):
        files = [tmp_path / f"slice_{i}.dcm" for i in range(3)]
        for file in files:
            file.write_text("dicom")
        monkeypatch.setattr(volume_cache, "CACHE_FILE", _write_cache(tmp_path, files))

        assert volume_cache.load_last_loaded() == files

    def test_does_not_stat_every_cached_file(self, tmp_path, monkeypatch):
        """Reloads must not probe hundreds of (possibly slow network) paths."""
        files = [tmp_path / f"slice_{i}.dcm" for i in range(5)]
        for file in files:
            file.write_text("dicom")
        monkeypatch.setattr(volume_cache, "CACHE_FILE", _write_cache(tmp_path, files))

        checked: list[Path] = []
        original_exists = Path.exists

        def counting_exists(self):
            if self in files:
                checked.append(self)
            return original_exists(self)

        monkeypatch.setattr(Path, "exists", counting_exists)

        result = volume_cache.load_last_loaded()

        assert result == files
        assert checked == [files[0]]

    def test_returns_none_when_first_file_is_gone(self, tmp_path, monkeypatch):
        files = [tmp_path / "gone.dcm", tmp_path / "slice_1.dcm"]
        files[1].write_text("dicom")
        monkeypatch.setattr(volume_cache, "CACHE_FILE", _write_cache(tmp_path, files))

        assert volume_cache.load_last_loaded() is None

    def test_returns_none_for_invalid_cache_file(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "last_loaded.json"
        cache_file.write_text("not json")
        monkeypatch.setattr(volume_cache, "CACHE_FILE", cache_file)

        assert volume_cache.load_last_loaded() is None


class TestLastSessionRecord:
    """The {kind, files} record behind the 'Restore last session' button."""

    def test_demo_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setattr(volume_cache, "CACHE_FILE", tmp_path / "last_loaded.json")

        volume_cache.save_last_demo()

        assert volume_cache.load_last_session() == ("demo", [])

    def test_dicom_roundtrip_keeps_files(self, tmp_path, monkeypatch):
        files = [tmp_path / f"slice_{i}.dcm" for i in range(2)]
        for file in files:
            file.write_text("dicom")
        monkeypatch.setattr(volume_cache, "CACHE_FILE", tmp_path / "last_loaded.json")

        volume_cache.save_last_loaded(files)

        assert volume_cache.load_last_session() == ("dicom", files)

    def test_legacy_record_without_kind_is_dicom(self, tmp_path, monkeypatch):
        files = [tmp_path / "slice_0.dcm"]
        files[0].write_text("dicom")
        monkeypatch.setattr(volume_cache, "CACHE_FILE", _write_cache(tmp_path, files))

        kind, restored = volume_cache.load_last_session()

        assert kind == "dicom"
        assert restored == files

    def test_load_last_loaded_ignores_demo_record(self, tmp_path, monkeypatch):
        monkeypatch.setattr(volume_cache, "CACHE_FILE", tmp_path / "last_loaded.json")
        volume_cache.save_last_demo()

        assert volume_cache.load_last_loaded() is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
