"""Tests for NPY loader."""

import tempfile
from pathlib import Path

import numpy as np
import pytest

from visualization.loaders.npy import load_npy, load_npy_series, scan_npy_folder


class TestLoadNpy:
    """Tests for load_npy function."""

    def test_load_valid_npy_file(self):
        """Loads a valid .npy file successfully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "volume.npy"

            # Create a 3D array
            array = np.random.randint(-1000, 1000, (10, 64, 64), dtype=np.int16)
            np.save(path, array)

            volume = load_npy(path)

            assert volume.array.shape == (10, 64, 64)
            assert volume.spacing == (1.0, 1.0, 1.0)
            assert volume.origin == (0.0, 0.0, 0.0)

    def test_load_npy_wrong_extension_raises(self):
        """ValueError when file is not .npy."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "volume.npz"
            path.write_text("not a npy")

            with pytest.raises(ValueError, match="Expected .npy file"):
                load_npy(path)

    def test_load_npy_not_3d_raises(self):
        """ValueError when array is not 3D."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "volume.npy"

            # 2D array (now should work - 2D is supported!)
            array = np.random.rand(64, 64).astype(np.float32)
            np.save(path, array)

            # 2D arrays are now loaded as single slice
            volume = load_npy(path)
            assert volume.array.shape == (1, 64, 64)

    def test_load_npy_1d_raises(self):
        """ValueError when array is 1D."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "volume.npy"

            array = np.array([1, 2, 3, 4], dtype=np.float32)
            np.save(path, array)

            with pytest.raises(ValueError, match="Expected 2D or 3D array"):
                load_npy(path)

    def test_custom_spacing(self):
        """Custom spacing is applied correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "volume.npy"

            array = np.zeros((10, 64, 64), dtype=np.float32)
            np.save(path, array)

            volume = load_npy(path, spacing=(2.5, 0.5, 0.5))

            assert volume.spacing == (2.5, 0.5, 0.5)

    def test_default_spacing(self):
        """Default spacing is (1.0, 1.0, 1.0)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "volume.npy"

            array = np.zeros((5, 32, 32), dtype=np.float32)
            np.save(path, array)

            volume = load_npy(path)

            assert volume.spacing == (1.0, 1.0, 1.0)


class TestNpyUnitDetection:
    """Tests for unit detection in NPY loader."""

    def test_detect_hu_from_int16(self):
        """Detects HU from int16 with large values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "volume.npy"

            # int16 with values > 100 -> should detect HU
            array = np.array([[[500]], [[1000]], [[-200]]], dtype=np.int16)
            np.save(path, array)

            volume = load_npy(path)

            assert volume.meta["unit"] == "HU"

    def test_detect_attenuation_from_float(self):
        """Detects 1/mm from float with small positive values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "volume.npy"

            # float32 with values < 10 -> should detect 1/mm
            array = np.array([[[0.5]], [[1.2]], [[0.8]]], dtype=np.float32)
            np.save(path, array)

            volume = load_npy(path)

            assert volume.meta["unit"] == "1/mm"

    def test_detect_attenuation_from_float_small(self):
        """Detects 1/mm from float with very small values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "volume.npy"

            # float32 with values < 1 -> should detect 1/mm
            array = np.array([[[0.05]], [[0.12]], [[0.08]]], dtype=np.float32)
            np.save(path, array)

            volume = load_npy(path)

            assert volume.meta["unit"] == "1/mm"

    def test_force_unit_hu(self):
        """Can force HU unit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "volume.npy"

            array = np.zeros((3, 32, 32), dtype=np.float32)
            np.save(path, array)

            volume = load_npy(path, unit="HU")

            assert volume.meta["unit"] == "HU"

    def test_force_unit_1_per_mm(self):
        """Can force 1/mm unit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "volume.npy"

            array = np.zeros((3, 32, 32), dtype=np.int16)
            np.save(path, array)

            volume = load_npy(path, unit="1/mm")

            assert volume.meta["unit"] == "1/mm"

    def test_force_unit_1_per_cm(self):
        """Can force 1/cm unit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "volume.npy"

            array = np.zeros((3, 32, 32), dtype=np.int16)
            np.save(path, array)

            volume = load_npy(path, unit="1/cm")

            assert volume.meta["unit"] == "1/cm"

    def test_invalid_unit_raises(self):
        """ValueError for invalid unit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "volume.npy"

            array = np.zeros((3, 32, 32), dtype=np.float32)
            np.save(path, array)

            with pytest.raises(ValueError, match="Invalid unit"):
                load_npy(path, unit="invalid")


class TestNpyMetadata:
    """Tests for metadata in NPY loader."""

    def test_metadata_contains_source_file(self):
        """Metadata contains source file path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "volume.npy"

            array = np.zeros((3, 32, 32), dtype=np.float32)
            np.save(path, array)

            volume = load_npy(path)

            assert "source_file" in volume.meta
            assert str(path) in volume.meta["source_file"]

    def test_metadata_contains_unit(self):
        """Metadata always contains unit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "volume.npy"

            array = np.zeros((3, 32, 32), dtype=np.int16)
            np.save(path, array)

            volume = load_npy(path)

            assert "unit" in volume.meta


class TestNpy2DSupport:
    """Tests for 2D slice support in load_npy."""

    def test_load_2d_array_as_single_slice(self):
        """2D array is loaded as single slice volume."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "slice.npy"

            # 2D array (y, x)
            array = np.random.rand(64, 64).astype(np.float32)
            np.save(path, array)

            volume = load_npy(path)

            # Should be (1, y, x)
            assert volume.array.shape == (1, 64, 64)
            assert volume.spacing == (1.0, 1.0, 1.0)


class TestNpyFolder:
    """Tests for folder scanning and loading."""

    def test_scan_npy_folder_finds_files(self):
        """Scans folder and returns sorted list of .npy files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create files in random order
            np.save(root / "slice_003.npy", np.zeros((32, 32), dtype=np.float32))
            np.save(root / "slice_001.npy", np.zeros((32, 32), dtype=np.float32))
            np.save(root / "slice_002.npy", np.zeros((32, 32), dtype=np.float32))

            files = scan_npy_folder(root)

            assert len(files) == 3
            # Should be sorted numerically
            assert files[0].name == "slice_001.npy"
            assert files[1].name == "slice_002.npy"
            assert files[2].name == "slice_003.npy"

    def test_scan_npy_folder_ignores_non_npy(self):
        """Ignores non-.npy files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            np.save(root / "slice_001.npy", np.zeros((32, 32), dtype=np.float32))
            (root / "other.txt").write_text("not npy")
            (root / "other.npz").write_text("not npy")

            files = scan_npy_folder(root)

            assert len(files) == 1

    def test_scan_npy_folder_empty_raises(self):
        """ValueError when no .npy files found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "other.txt").write_text("not npy")

            with pytest.raises(ValueError, match="No .npy files found"):
                scan_npy_folder(root)

    def test_load_npy_series_stacks_2d_slices(self):
        """Stacks multiple 2D files into volume."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create 2D slices
            np.save(root / "slice_000.npy", np.ones((32, 32), dtype=np.float32) * 1)
            np.save(root / "slice_001.npy", np.ones((32, 32), dtype=np.float32) * 2)
            np.save(root / "slice_002.npy", np.ones((32, 32), dtype=np.float32) * 3)

            files = scan_npy_folder(root)
            volume = load_npy_series(files)

            assert volume.array.shape == (3, 32, 32)
            # Check values are stacked correctly
            assert volume.array[0, 0, 0] == 1
            assert volume.array[1, 0, 0] == 2
            assert volume.array[2, 0, 0] == 3

    def test_load_npy_series_with_custom_spacing(self):
        """Custom spacing applied to series."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            np.save(root / "s1.npy", np.zeros((32, 32), dtype=np.float32))
            np.save(root / "s2.npy", np.zeros((32, 32), dtype=np.float32))

            files = scan_npy_folder(root)
            volume = load_npy_series(files, spacing=(2.5, 0.5, 0.7))

            assert volume.spacing == (2.5, 0.5, 0.7)

    def test_load_npy_series_3d_arrays(self):
        """Can also load 3D arrays and stack them."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create 3D arrays (should stack along first axis)
            np.save(root / "vol1.npy", np.ones((5, 32, 32), dtype=np.float32))
            np.save(root / "vol2.npy", np.ones((5, 32, 32), dtype=np.float32) * 2)

            files = scan_npy_folder(root)
            volume = load_npy_series(files)

            assert volume.array.shape == (10, 32, 32)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
