"""Tests for DICOM loader."""

import tempfile
import warnings
from pathlib import Path

import numpy as np
import pydicom
import pytest
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence

from backend.loaders.dicom import (
    SeriesInfo,
    classify_dose,
    load_dicom_series,
    scan_series,
)


def _create_ct_dicom(
    file_path: Path,
    series_instance_uid: str,
    patient_id: str = "TEST001",
    series_description: str = "Test Series",
    slice_location: float = 0.0,
    image_position_patient: tuple[float, float, float] = (0.0, 0.0, 0.0),
    image_orientation_patient: tuple[float, float, float, float, float, float] = (
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
    ),
    pixel_spacing: tuple[float, float] = (0.7, 0.7),
    rescale_slope: float = 1.0,
    rescale_intercept: float = -1024,
    gantry_detector_tilt: float = 0.0,
    rows: int = 512,
    cols: int = 512,
) -> None:
    """Create a synthetic CT DICOM file for testing.

    Args:
        file_path: Path to save the DICOM file.
        series_instance_uid: SeriesInstanceUID.
        patient_id: PatientID.
        series_description: SeriesDescription.
        slice_location: SliceLocation.
        image_position_patient: ImagePositionPatient [x, y, z].
        image_orientation_patient: ImageOrientationPatient.
        pixel_spacing: PixelSpacing [row, col].
        rescale_slope: RescaleSlope.
        rescale_intercept: RescaleIntercept.
        gantry_detector_tilt: GantryDetectorTilt.
        rows: Number of rows.
        cols: Number of columns.
    """
    from pydicom.uid import ImplicitVRLittleEndian, generate_uid

    ds = Dataset()

    # File meta for proper DICOM write
    ds.file_meta = pydicom.Dataset()
    ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
    ds.file_meta.MediaStorageSOPClassUID = (
        "1.2.840.10008.5.1.4.1.1.2"  # CT Image Storage
    )
    ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()
    ds.file_meta.ImplementationClassUID = generate_uid()

    # Patient module
    ds.PatientID = patient_id
    ds.PatientName = "Test^Patient"

    # Study module
    ds.StudyInstanceUID = "1.2.3.4.5.6.7.8.9"
    ds.StudyDate = "20200101"
    ds.StudyTime = "120000"

    # Series module
    ds.SeriesInstanceUID = series_instance_uid
    ds.SeriesDescription = series_description
    ds.SeriesNumber = 1
    ds.Modality = "CT"

    # Acquisition module
    ds.AcquisitionNumber = 1

    # Image module
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"  # CT Image Storage
    ds.SOPInstanceUID = f"1.2.3.4.5.6.7.8.9.{slice_location}"
    ds.ImageType = ["ORIGINAL", "PRIMARY", "AXIAL"]
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.Rows = rows
    ds.Columns = cols
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0  # unsigned
    ds.PixelSpacing = list(pixel_spacing)

    # Position and orientation
    ds.ImagePositionPatient = list(image_position_patient)
    ds.ImageOrientationPatient = list(image_orientation_patient)
    ds.SliceLocation = slice_location
    ds.SliceThickness = pixel_spacing[0]

    # Reconstruction
    ds.RescaleSlope = rescale_slope
    ds.RescaleIntercept = rescale_intercept
    ds.KVP = 120
    ds.ScanOptions = "HELICAL"

    # Gantry
    ds.GantryDetectorTilt = gantry_detector_tilt
    ds.TableHeight = 0.0

    # Generate synthetic pixel data (simple pattern)
    pixel_array = np.zeros((rows, cols), dtype=np.uint16)
    # Add a simple circular region in the center
    center_y, center_x = rows // 2, cols // 2
    radius = min(rows, cols) // 4
    y, x = np.ogrid[:rows, :cols]
    mask = (x - center_x) ** 2 + (y - center_y) ** 2 <= radius**2
    pixel_array[mask] = 1000  # ~water-equivalent

    ds.PixelData = pixel_array.tobytes()

    # Save to file with explicit transfer syntax
    ds.save_as(file_path, write_like_original=False)


class TestClassifyDose:
    """Tests for classify_dose function."""

    def test_quarter_dose(self):
        """Quarter dose classification."""
        assert classify_dose("Quarter Dose") == "quarter"
        assert classify_dose("QUARTER") == "quarter"
        assert classify_dose("low dose quarter") == "quarter"

    def test_half_dose(self):
        """Half dose classification."""
        assert classify_dose("Half Dose") == "half"
        assert classify_dose("HALF") == "half"
        assert classify_dose("low dose half") == "half"

    def test_full_dose(self):
        """Full dose classification."""
        assert classify_dose("Full Dose") == "full"
        assert classify_dose("Standard") == "full"
        assert classify_dose("FULL") == "full"

    def test_unknown_dose(self):
        """Unknown dose classification."""
        assert classify_dose("") == "unknown"
        assert classify_dose("Chest") == "unknown"
        assert classify_dose("Abdomen CT") == "unknown"


class TestScanSeries:
    """Tests for scan_series function."""

    def test_scan_series_groups_by_subdir(self):
        """Groups files by subdirectory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create files in subdirectories
            (root / "series1").mkdir()
            (root / "series2").mkdir()

            _create_ct_dicom(
                root / "series1" / "slice1.dcm",
                series_instance_uid="1.1",
                slice_location=0.0,
            )
            _create_ct_dicom(
                root / "series1" / "slice2.dcm",
                series_instance_uid="1.1",
                slice_location=1.0,
            )
            _create_ct_dicom(
                root / "series2" / "slice1.dcm",
                series_instance_uid="1.2",
                slice_location=0.0,
            )

            series_list = scan_series(root)

            # Should have 2 series (one per subdir)
            assert len(series_list) == 2

            # Check counts
            counts = {s.series_description: s.n_slices for s in series_list}
            assert counts["series1"] == 2
            assert counts["series2"] == 1

    def test_scan_series_empty_directory_raises(self):
        """Error on empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            with pytest.raises(ValueError, match="No DICOM files found"):
                scan_series(root)

    def test_scan_series_root_files(self):
        """Files in root dir are grouped together."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create files directly in root
            _create_ct_dicom(
                root / "slice1.dcm", series_instance_uid="1.1", slice_location=0.0
            )
            _create_ct_dicom(
                root / "slice2.dcm", series_instance_uid="1.1", slice_location=1.0
            )

            series_list = scan_series(root)

            # Should have 1 series
            assert len(series_list) == 1
            assert series_list[0].n_slices == 2

    def test_scan_series_files_attribute(self):
        """SeriesInfo includes files list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            (root / "series1").mkdir()
            _create_ct_dicom(
                root / "series1" / "slice1.dcm",
                series_instance_uid="1.1",
                slice_location=0.0,
            )

            series_list = scan_series(root)

            assert series_list[0].files is not None
            assert len(series_list[0].files) == 1


class TestLoadDicomSeries:
    """Tests for load_dicom_series function."""

    def test_load_dicom_series_converts_to_hu(self):
        """HU conversion works correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            uid = "1.2.3.4.5"

            # Create slices with known values
            # Pixel value = 1000, rescale slope = 1, intercept = -1024
            # Expected HU = 1000 * 1 + (-1024) = -24
            for i in range(3):
                _create_ct_dicom(
                    root / f"slice{i}.dcm",
                    series_instance_uid=uid,
                    slice_location=float(i),
                    image_position_patient=(0.0, 0.0, float(i)),
                    rescale_slope=1.0,
                    rescale_intercept=-1024,
                )

            files = list(root.glob("*.dcm"))
            volume = load_dicom_series(files)

            # Check that HU conversion happened
            # Original pixel value was ~1000, converted to ~-24 HU (for water)
            assert volume.array.shape[0] == 3  # 3 slices
            assert volume.array.shape[1] == 512  # rows
            assert volume.array.shape[2] == 512  # cols

            # Check spacing
            assert volume.spacing[0] == 1.0  # slice spacing
            assert volume.spacing[1] == 0.7  # row spacing
            assert volume.spacing[2] == 0.7  # col spacing

            # Check meta
            assert volume.meta["unit"] == "HU"

    def test_load_dicom_series_reorients_to_patient_frame(self):
        """Standard axial DICOM grids are transposed to the project's patient
        frame at load time: rows (posterior-ward) become the flipped x axis
        and columns (patient-left-ward) the y axis — the axial MPR slice
        comes out un-rotated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            uid = "1.2.3.4.5"
            _create_ct_dicom(
                root / "slice0.dcm",
                series_instance_uid=uid,
                slice_location=0.0,
                image_position_patient=(0.0, 0.0, 0.0),
                pixel_spacing=(0.5, 0.8),  # [row, col]
                rows=4,
                cols=6,
            )
            volume = load_dicom_series(list(root.glob("*.dcm")))

            # (z, y, x): the in-plane axes swap, x flips.
            assert volume.array.shape == (1, 6, 4)
            # The circle's centre moves from (row 2, col 3) to (y 3, x 1).
            # HU: circle 1000 - 1024 = -24, background 0 - 1024 = -1024.
            assert volume.array[0, 3, 1] == -24
            assert volume.array[0, 2, 3] == -1024
            # Spacing follows the axes: new y = old columns, new x = old rows.
            assert volume.spacing == (1.0, 0.8, 0.5)

    def test_load_dicom_series_custom_rescale(self):
        """Custom rescale slope and intercept."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            uid = "1.2.3.4.5"

            # pixel = 500, slope = 2, intercept = -2000
            # Expected HU = 500 * 2 + (-2000) = -1000
            _create_ct_dicom(
                root / "slice0.dcm",
                series_instance_uid=uid,
                slice_location=0.0,
                rescale_slope=2.0,
                rescale_intercept=-2000,
            )

            files = list(root.glob("*.dcm"))
            volume = load_dicom_series(files)

            # Values should be in HU
            assert volume.meta["unit"] == "HU"

    def test_load_dicom_series_inconsistent_spacing_raises(self):
        """ValueError on inconsistent spacing > 1%."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            uid = "1.2.3.4.5"

            # Create slices with inconsistent spacing (>1% variation)
            # Spacings: 1mm, then 2mm (mean=1.5mm, deviation=0.5mm, error=33%)
            positions = [
                (0.0, 0.0, 0.0),
                (0.0, 0.0, 1.0),  # 1mm from first
                (0.0, 0.0, 3.0),  # 2mm from second (inconsistent!)
            ]

            for i, pos in enumerate(positions):
                _create_ct_dicom(
                    root / f"slice{i}.dcm",
                    series_instance_uid=uid,
                    slice_location=float(i),
                    image_position_patient=pos,
                )

            files = list(root.glob("*.dcm"))

            # This should raise because spacing varies more than 1%
            with pytest.raises(ValueError, match="Slice spacing inconsistent"):
                load_dicom_series(files)

    def test_gantry_tilt_warning(self):
        """Warning issued for gantry tilt, no abort."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            uid = "1.2.3.4.5"

            # Create slice with gantry tilt
            _create_ct_dicom(
                root / "slice0.dcm",
                series_instance_uid=uid,
                slice_location=0.0,
                gantry_detector_tilt=15.0,  # 15 degree tilt
            )

            files = list(root.glob("*.dcm"))

            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                volume = load_dicom_series(files)

                # Should have warning
                assert len(w) >= 1
                gantry_warnings = [x for x in w if "Gantry tilt" in str(x.message)]
                assert len(gantry_warnings) >= 1

                # Should still return valid volume
                assert volume.array.shape[0] == 1

    def test_gantry_tilt_from_orientation(self):
        """Warning from non-axial orientation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            uid = "1.2.3.4.5"

            # Create slice with tilted orientation (not [1,0,0,0,1,0])
            _create_ct_dicom(
                root / "slice0.dcm",
                series_instance_uid=uid,
                slice_location=0.0,
                image_orientation_patient=(1.0, 0.0, 0.0, 0.0, 0.707, 0.707),
            )

            files = list(root.glob("*.dcm"))

            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                volume = load_dicom_series(files)

                # Should have warning for non-axial
                assert len(w) >= 1

    def test_load_series_no_files_raises(self):
        """ValueError when no files provided."""
        with pytest.raises(ValueError, match="No files provided"):
            load_dicom_series([])

    def test_series_info_dataclass(self):
        """SeriesInfo dataclass works correctly."""
        info = SeriesInfo(
            series_instance_uid="1.2.3",
            patient_id="Patient001",
            series_description="Test",
            n_slices=10,
            dose_class="full",
        )

        assert info.series_instance_uid == "1.2.3"
        assert info.patient_id == "Patient001"
        assert info.n_slices == 10
        assert info.dose_class == "full"


class TestDicomSorting:
    """Tests for proper slice sorting."""

    def test_slices_sorted_by_position(self):
        """Slices are sorted correctly by position along normal."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            uid = "1.2.3.4.5"

            # Create slices in random order
            positions = [
                (0.0, 0.0, 10.0),
                (0.0, 0.0, 0.0),
                (0.0, 0.0, 5.0),
            ]

            for i, pos in enumerate(positions):
                _create_ct_dicom(
                    root / f"slice{i}.dcm",
                    series_instance_uid=uid,
                    slice_location=pos[2],
                    image_position_patient=pos,
                )

            files = list(root.glob("*.dcm"))
            volume = load_dicom_series(files)

            # Check origin is the first slice (lowest position)
            assert volume.origin[2] == 0.0  # z should be 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
