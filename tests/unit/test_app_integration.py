"""Integration tests for Streamlit app - MPR + Windowing pipeline."""

import numpy as np
import pytest

from visualization.volume import Volume
from visualization.mpr import extract_slice
from visualization.windowing import apply_window, WINDOW_PRESETS


class TestMPRWindowingIntegration:
    """Test the full MPR + windowing pipeline used in the app."""

    @pytest.fixture
    def test_volume(self):
        """Create a test volume matching app usage."""
        array = np.arange(490).reshape(10, 7, 7).astype(np.int16)
        # Add some HU-like values (air: -1000, water: 0, bone: +800)
        array = array * 200 - 1000  # Range: -1000 to +8800 HU
        return Volume(
            array=array,
            spacing=(3.0, 0.7, 0.7),
            origin=(0.0, 0.0, 0.0)
        )

    def test_axial_mpr_with_windowing(self, test_volume):
        """Test axial slice extraction + windowing pipeline."""
        slice_img, spacing = extract_slice(test_volume, "axial", 5)
        windowed = apply_window(slice_img, 40, 400)  # abdomen preset

        assert windowed.shape == slice_img.shape
        assert windowed.dtype == np.uint8
        assert windowed.min() >= 0
        assert windowed.max() <= 255

    def test_coronal_mpr_with_windowing(self, test_volume):
        """Test coronal slice extraction + windowing pipeline."""
        slice_img, spacing = extract_slice(test_volume, "coronal", 3)
        windowed = apply_window(slice_img, -600, 1500)  # lung preset

        assert windowed.shape == slice_img.shape
        assert windowed.dtype == np.uint8
        assert windowed.min() >= 0
        assert windowed.max() <= 255

    def test_sagittal_mpr_with_windowing(self, test_volume):
        """Test sagittal slice extraction + windowing pipeline."""
        slice_img, spacing = extract_slice(test_volume, "sagittal", 3)
        windowed = apply_window(slice_img, 400, 1800)  # bone preset

        assert windowed.shape == slice_img.shape
        assert windowed.dtype == np.uint8
        assert windowed.min() >= 0
        assert windowed.max() <= 255

    def test_all_window_presets_work(self, test_volume):
        """Test all window presets work with MPR."""
        slice_img, _ = extract_slice(test_volume, "axial", 5)

        for preset_name, (center, width) in WINDOW_PRESETS.items():
            windowed = apply_window(slice_img, center, width)
            assert windowed.dtype == np.uint8, f"Preset {preset_name} failed"
            assert windowed.min() >= 0
            assert windowed.max() <= 255

    def test_manual_windowing_values(self, test_volume):
        """Test manual center/width values work (as in app sliders)."""
        slice_img, _ = extract_slice(test_volume, "axial", 5)

        # Test range of manual values (as in app sliders)
        for center in [-500, 0, 500, 1500, 2500]:
            for width in [100, 500, 1000, 2000, 3500]:
                windowed = apply_window(slice_img, center, width)
                assert windowed.dtype == np.uint8
                assert 0 <= windowed.min() <= windowed.max() <= 255


class TestSliderBounds:
    """Test slider bound calculations used in the app."""

    @pytest.fixture
    def test_volume(self):
        # 3D volume: 10 slices, 10x10 pixels each
        array = np.arange(1000).reshape(10, 10, 10).astype(np.int16)
        return Volume(
            array=array,
            spacing=(1.0, 1.0, 1.0),
            origin=(0.0, 0.0, 0.0)
        )

    def test_axial_slider_bounds(self, test_volume):
        """Axial slider max should be shape[0] - 1."""
        max_idx = test_volume.array.shape[0] - 1
        assert max_idx == 9

        # Extract at bounds
        slice_img, _ = extract_slice(test_volume, "axial", 0)
        assert slice_img.shape == (10, 10)

        slice_img, _ = extract_slice(test_volume, "axial", max_idx)
        assert slice_img.shape == (10, 10)

    def test_coronal_slider_bounds(self, test_volume):
        """Coronal slider max should be shape[1] - 1."""
        max_idx = test_volume.array.shape[1] - 1
        assert max_idx == 9

        slice_img, _ = extract_slice(test_volume, "coronal", max_idx)
        assert slice_img.shape == (10, 10)

    def test_sagittal_slider_bounds(self, test_volume):
        """Sagittal slider max should be shape[2] - 1."""
        max_idx = test_volume.array.shape[2] - 1
        assert max_idx == 9

        slice_img, _ = extract_slice(test_volume, "sagittal", max_idx)
        assert slice_img.shape == (10, 10)


class TestVolumeInfoDisplay:
    """Test volume info that the app displays."""

    @pytest.fixture
    def test_volume(self):
        array = np.zeros((20, 512, 512), dtype=np.int16)
        return Volume(
            array=array,
            spacing=(2.5, 0.5, 0.5),
            origin=(0.0, 0.0, 0.0)
        )

    def test_shape_display(self, test_volume):
        """Test shape property works for display."""
        assert test_volume.shape == (20, 512, 512)
        assert test_volume.n_slices == 20

    def test_spacing_display(self, test_volume):
        """Test spacing property works for display."""
        assert test_volume.spacing == (2.5, 0.5, 0.5)

    def test_spacing_caption_format(self, test_volume):
        """Test spacing format matches app caption."""
        # Axial: spacing[1], spacing[2]
        _, spacing = extract_slice(test_volume, "axial", 10)
        assert spacing == (0.5, 0.5)

        # Coronal: spacing[0], spacing[2] - use valid index 5 (max is 511)
        _, spacing = extract_slice(test_volume, "coronal", 5)
        assert spacing == (2.5, 0.5)

        # Sagittal: spacing[0], spacing[1] - use valid index 5
        _, spacing = extract_slice(test_volume, "sagittal", 5)
        assert spacing == (2.5, 0.5)
