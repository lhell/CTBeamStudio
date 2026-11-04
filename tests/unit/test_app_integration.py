"""Integration tests for Streamlit app - MPR + Windowing pipeline."""

import numpy as np
import pytest

from backend.volume import Volume
from visualization.mpr import extract_slice
from visualization.windowing import WINDOW_PRESETS, apply_window


class TestMPRWindowingIntegration:
    """Test the full MPR + windowing pipeline used in the app."""

    @pytest.fixture
    def test_volume(self):
        """Create a test volume matching app usage."""
        array = np.arange(490).reshape(10, 7, 7).astype(np.int16)
        # Add some HU-like values (air: -1000, water: 0, bone: +800)
        array = array * 200 - 1000  # Range: -1000 to +8800 HU
        return Volume(array=array, spacing=(3.0, 0.7, 0.7), origin=(0.0, 0.0, 0.0))

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
        return Volume(array=array, spacing=(1.0, 1.0, 1.0), origin=(0.0, 0.0, 0.0))

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
        return Volume(array=array, spacing=(2.5, 0.5, 0.5), origin=(0.0, 0.0, 0.0))

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


class TestIsotropicResampling:
    """Test isotropic resampling for correct aspect ratio."""

    @pytest.fixture
    def anisotropic_image(self):
        """Create anisotropic image (different row/col spacing)."""
        # Simulate coronal/sagittal: 100 rows (3mm each), 512 cols (0.7mm each)
        return np.random.randint(0, 256, (100, 512), dtype=np.uint8)

    def test_isotropic_same_spacing(self, anisotropic_image):
        """When row/col spacing equal, return original."""
        from visualization.app import to_isotropic

        result = to_isotropic(anisotropic_image, (0.7, 0.7))
        assert result.shape == anisotropic_image.shape

    def test_isotropic_vertical_stretch(self, anisotropic_image):
        """When rows thicker than cols, stretch vertically."""
        from visualization.app import to_isotropic

        # 3mm row spacing, 0.7mm col spacing -> stretch rows by ~4.3x
        result = to_isotropic(anisotropic_image, (3.0, 0.7))
        # Expected: 100 * (3.0/0.7) = ~428 rows
        assert result.shape[0] > anisotropic_image.shape[0]
        assert result.shape[1] == anisotropic_image.shape[1]

    def test_isotropic_horizontal_stretch(self, anisotropic_image):
        """When cols thicker than rows, shrink horizontally (inverse of vertical)."""
        from visualization.app import to_isotropic

        # 0.7mm row spacing, 3mm col spacing -> scale rows by 0.7/3.0 = 0.23
        result = to_isotropic(anisotropic_image, (0.7, 3.0))
        # Expected: 100 * (0.7/3.0) = ~23 rows
        assert result.shape[0] < anisotropic_image.shape[0]
        assert result.shape[1] == anisotropic_image.shape[1]


class TestSliceIndexClamping:
    """Test clamp_slice_state logic."""

    def test_clamp_above_max(self):
        """Test clamping value above max."""
        import streamlit as st

        # Simulate session state with stale value
        st.session_state["test_slice"] = 500

        from visualization.app import clamp_slice_state

        clamp_slice_state("test_slice", 100)  # max is 100
        assert st.session_state["test_slice"] == 100

    def test_clamp_below_zero(self):
        """Test clamping negative value."""
        import streamlit as st

        st.session_state["test_slice"] = -5

        from visualization.app import clamp_slice_state

        clamp_slice_state("test_slice", 100)
        assert st.session_state["test_slice"] == 0

    def test_clamp_within_bounds(self):
        """Test value within bounds stays unchanged."""
        import streamlit as st

        st.session_state["test_slice"] = 50

        from visualization.app import clamp_slice_state

        clamp_slice_state("test_slice", 100)
        assert st.session_state["test_slice"] == 50

    def test_default_when_missing(self):
        """Test default value when key not in session state."""
        import streamlit as st

        st.session_state.pop("test_slice", None)

        from visualization.app import clamp_slice_state

        clamp_slice_state("test_slice", 100)
        assert st.session_state["test_slice"] == 50  # 100 // 2
