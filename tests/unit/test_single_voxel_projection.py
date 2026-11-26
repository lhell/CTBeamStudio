"""Single voxel in the image center: DICOM roundtrip + detector-centering.

The cleanest possible geometry probe: one dense voxel at the world origin,
written as a DICOM series, loaded through the app's DICOM loader, and forward
projected with the default geometry. Its projection must land on the detector
center for every gantry angle, so any detector-mapping error (row flip, z
offset, column shift) shows up as a centroid deviation in pixels.

The test also writes two best-effort artifacts under ``data/cache/``:
``single_voxel_dicom/`` (the series, loadable in the app via the sidebar) and
``single_voxel_projection_check.png`` (the 8 projections with expected vs
measured centroid markers).
"""

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from backend.attenuation import volume_for_projection
from backend.forward_project import forward_project
from backend.geometry import ProjectionGeometry
from backend.loaders.dicom import load_dicom_series

N = 64
VOXEL_HU = 500.0
AIR_HU = -1000.0
# ImagePositionPatient chosen so the loaded volume's center voxel sits at the
# world origin (see the origin derivation in the loader's standard-axial
# branch: origin = (-(IPP_y + (n_rows - 1) * row_spacing), IPP_x, IPP_z)).
IPP0 = (-32.0, -32.0, -32.0)
# User-visible artifacts (the series to load in the app + projection views).
ARTIFACT_DIR = Path(r"C:\Users\hellwege\CTBeamStudio_Data\SingleVoxel")


def _write_slice(path: Path, instance: int, hu: np.ndarray) -> None:
    """Write one axial CT slice (HU stored with the standard CT rescale)."""
    import pydicom
    from pydicom.dataset import FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, generate_uid

    ds = pydicom.Dataset()
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"  # CT Image Storage
    ds.SOPInstanceUID = generate_uid()
    ds.SeriesInstanceUID = "1.2.826.0.1.3680043.8.498.11111"
    ds.StudyInstanceUID = "1.2.826.0.1.3680043.8.498.22222"
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = ds.SOPClassUID
    file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta = file_meta
    ds.Modality = "CT"
    ds.PatientID = "SINGLE-VOXEL"
    ds.InstanceNumber = instance
    ds.Rows, ds.Columns = N, N
    ds.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    ds.ImagePositionPatient = [
        IPP0[0],
        IPP0[1],
        IPP0[2] + (instance - 1) * 1.0,
    ]
    ds.PixelSpacing = [1.0, 1.0]
    ds.SliceThickness = 1.0
    ds.RescaleSlope = 1.0
    ds.RescaleIntercept = -1024.0
    ds.BitsAllocated = ds.BitsStored = 16
    ds.PixelRepresentation = 1  # signed
    ds.HighBit = 15
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelData = (hu.astype(np.int16) + 1024).tobytes()
    pydicom.dcmwrite(path, ds, enforce_file_format=True)


def _write_series(directory: Path) -> list[Path]:
    """64 axial slices; exactly one dense voxel in the image center."""
    hu = np.full((N, N), AIR_HU, dtype=np.int16)
    directory.mkdir(parents=True, exist_ok=True)
    files = []
    for i in range(1, N + 1):
        slice_hu = hu.copy()
        if i == N // 2 + 1:  # slice 32 (1-based): the center slice
            slice_hu[N // 2, N // 2] = VOXEL_HU
        path = directory / f"slice_{i:03d}.dcm"
        _write_slice(path, i, slice_hu)
        files.append(path)
    return sorted(files)


@pytest.fixture(scope="module")
def dicom_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("single_voxel")


@pytest.fixture(scope="module")
def loaded_volume(dicom_dir):
    return load_dicom_series(_write_series(dicom_dir))


def test_dicom_roundtrip_places_center_voxel_at_world_origin(loaded_volume):
    """The app's DICOM loader must land the center voxel at (0, 0, 0)."""
    vol = loaded_volume
    assert (vol.meta or {}).get("unit") == "HU"
    assert vol.shape == (N, N, N)

    idx = np.unravel_index(int(np.argmax(vol.array)), vol.array.shape)
    # The loader transposes in-plane axes and flips rows: DICOM (row 32,
    # col 32) becomes loaded (y=32, x=31).
    assert idx == (N // 2, N // 2, N // 2 - 1)
    world = (
        vol.origin[0] + idx[2] * vol.spacing[2],
        vol.origin[1] + idx[1] * vol.spacing[1],
        vol.origin[2] + idx[0] * vol.spacing[0],
    )
    assert world == pytest.approx((0.0, 0.0, 0.0), abs=1e-6)


def test_single_voxel_projects_to_detector_center(loaded_volume, dicom_dir):
    """With the default geometry the voxel must project onto the detector
    center at every gantry angle: column center exactly (the voxel sits on
    the rotation axis), row center shifted only by the scan-plane z offset
    (z_center = -0.5 mm for an even number of slices)."""
    vol = loaded_volume
    geom = ProjectionGeometry()  # app defaults: sdd 1000, sid 500, 512 x 64

    # 8 views, 45 deg apart (angular_inc = 360 / projections_per_rotation).
    proj_indices = [i * (geom.projections_per_rotation // 8) for i in range(8)]
    res = forward_project(
        volume_for_projection(vol, 70.0),
        geom,
        proj_indices=proj_indices,
        n_projections_total=geom.projections_per_rotation,
        use_cuda=False,
    )
    p = res.projections
    assert p.shape == (8, geom.n_det_rows, geom.n_det_cols)
    assert p.min() >= 0.0
    # The line integral through one 1 mm voxel (HU 500 at 70 keV) is only
    # ~0.029, and the peak pixel is lower still (interpolation spread), so
    # the non-empty threshold must be well below that.
    assert all(p[i].max() > 0.005 for i in range(8)), "projection ran empty"

    # Analytic expectation: the scan plane sits at z_center = -0.5 mm (even
    # slice count), the voxel at z = 0; the ray widens the offset by sdd/sid
    # at the detector. Detector element i centers at (i - n/2 + 0.5) * spacing.
    z_center = vol.origin[2] + 0.5 * (N - 1) * vol.spacing[0]
    voxel_z = vol.origin[2] + (N // 2) * vol.spacing[0]
    expected_row = (voxel_z - z_center) * (geom.sdd / geom.sid) + (
        geom.n_det_rows / 2.0 - 0.5
    )
    expected_col = geom.n_det_cols / 2.0 - 0.5

    centroids = []
    for i in range(8):
        frame = p[i].astype(np.float64)
        total = frame.sum()
        rows, cols = np.mgrid[0 : frame.shape[0], 0 : frame.shape[1]]
        centroids.append(
            (float((rows * frame).sum() / total), float((cols * frame).sum() / total))
        )

    for i, (crow, ccol) in enumerate(centroids):
        assert abs(crow - expected_row) <= 1.0, (
            f"view {i} (angle {i * 45} deg): row centroid {crow:.2f}, "
            f"expected {expected_row:.2f}"
        )
        assert abs(ccol - expected_col) <= 1.0, (
            f"view {i} (angle {i * 45} deg): col centroid {ccol:.2f}, "
            f"expected {expected_col:.2f}"
        )

    _write_artifacts(dicom_dir, p, proj_indices, centroids, expected_row, expected_col)


def _write_artifacts(dicom_dir, p, proj_indices, centroids, expected_row, expected_col):
    """Best-effort diagnostics under ARTIFACT_DIR: the DICOM series (loadable
    in the app), the raw projections, and a PNG comparing expected vs
    measured centroids."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        out_dir = ARTIFACT_DIR
        out_dir.mkdir(parents=True, exist_ok=True)

        # Copy the series so it can be loaded via the app's sidebar input.
        app_dir = out_dir / "dicom"
        if app_dir.exists():
            shutil.rmtree(app_dir)
        shutil.copytree(dicom_dir, app_dir)

        # The exact geometry these projections were computed with, loadable
        # in the app's Geometry tab (the app would otherwise auto-restore the
        # last-used geometry, which does not match the default here).
        from dataclasses import asdict

        import yaml

        geom = ProjectionGeometry()
        (out_dir / "geometry_default.yaml").write_text(
            yaml.safe_dump(asdict(geom), sort_keys=True)
        )

        # Raw projections for offline inspection, plus the metadata needed to
        # reproduce them: which angle indices, which angles, which energy.
        np.save(out_dir / "projections.npy", p)
        # The same array as an app-loadable *measured* sinogram: pure line
        # integrals — no scatter, no noise — so loading it in the app's
        # Measurements section and running the FP must reproduce it exactly.
        np.save(out_dir / "measured_sinogram.npy", p)
        (out_dir / "projections_meta.json").write_text(
            json.dumps(
                {
                    "proj_indices": proj_indices,
                    "angles_deg": [
                        i * 360.0 / geom.projections_per_rotation for i in proj_indices
                    ],
                    "n_projections_total": geom.projections_per_rotation,
                    "energy_kev": 70.0,
                    "shape": list(p.shape),
                    "geometry": asdict(geom),
                },
                indent=2,
            )
        )

        fig, axes = plt.subplots(2, 4, figsize=(18, 9))
        for i, ax in enumerate(axes.flat):
            ax.imshow(p[i], cmap="gray", origin="lower", aspect="equal")
            ax.plot(expected_col, expected_row, marker="+", color="lime", markersize=14)
            ax.plot(
                centroids[i][1],
                centroids[i][0],
                marker="x",
                color="red",
                markersize=10,
            )
            angle = i * 45
            ax.set_title(
                f"{angle} deg: d(row)={centroids[i][0] - expected_row:+.2f}, "
                f"d(col)={centroids[i][1] - expected_col:+.2f} px",
                fontsize=9,
            )
            ax.set_xlim(230, 282)
            ax.set_ylim(12, 52)
        fig.suptitle(
            "Single center voxel, default geometry: expected (+) vs measured (x) centroid"
        )
        fig.tight_layout()
        fig.savefig(out_dir / "single_voxel_projection_check.png", dpi=90)
        plt.close(fig)
    except OSError:
        pass  # an unavailable artifact directory must not fail the test
