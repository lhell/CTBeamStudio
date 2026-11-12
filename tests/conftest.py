"""Pytest configuration for tests."""

import sys
from pathlib import Path

import pytest

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

print(
    f"[conftest] OK - visualization.windowing found at {visualization.windowing.__file__}"
)


@pytest.fixture
def create_projection_dicom():
    """Synthetic DICOM projection-series factory (3 frames of shape (4, 5)).

    Calling it with a directory writes the series and returns the directory
    that contains the files. Projection frame i has pixel array
    ``np.full((4, 5), i * 10, uint16)`` so tests can verify selection.

    Pass ``graded=True`` to give every frame a distinct row-major ramp instead
    of a constant: a constant frame looks the same transposed, so only a graded
    one can prove an axis-order transpose actually happened.
    """

    def _create(tmp_path, graded=False):
        import numpy as np
        import pydicom
        from pydicom.dataset import Dataset
        from pydicom.uid import ImplicitVRLittleEndian, generate_uid

        n_proj, n_rows, n_cols = 3, 4, 5
        d = Path(tmp_path) / "proj_series"
        d.mkdir()

        for i in range(n_proj):
            ds = Dataset()
            ds.file_meta = pydicom.Dataset()
            ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
            ds.file_meta.MediaStorageSOPClassUID = (
                "1.2.840.10008.5.1.4.1.1.2"  # CT Image Storage
            )
            ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()
            ds.file_meta.ImplementationClassUID = generate_uid()

            ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
            ds.SOPInstanceUID = generate_uid()
            ds.PatientID = "PROJ"
            ds.StudyInstanceUID = "1.2.3.4.5.6.7.8.9"
            ds.SeriesInstanceUID = "1.2.3.4.5.6.7.8.10"
            ds.Modality = "CT"
            ds.Rows = n_rows
            ds.Columns = n_cols
            ds.InstanceNumber = i
            ds.SamplesPerPixel = 1
            ds.PhotometricInterpretation = "MONOCHROME2"
            ds.BitsAllocated = 16
            ds.BitsStored = 16
            ds.HighBit = 15
            ds.PixelRepresentation = 0
            ds.PixelSpacing = [1.0, 1.0]
            ds.ImagePositionPatient = [0.0, 0.0, float(i)]
            ds.RescaleSlope = 1.0
            ds.RescaleIntercept = 0.0

            ds.PixelData = np.full((n_rows, n_cols), i * 10, dtype=np.uint16).tobytes()
            if graded:
                ds.PixelData = (
                    np.arange(n_rows * n_cols, dtype=np.uint16).reshape(n_rows, n_cols)
                    + i * 100
                ).tobytes()
            ds.save_as(d / f"proj_{i}.dcm", write_like_original=False)

        return d

    return _create
