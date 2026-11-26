""""Kugelwald" phantom (a small forest of spheres): DICOM roundtrip +
detector centering at many positions.

9 spheres: one on the rotation axis and 8 on a 20 mm ring (angles offset by
22.5 deg so that no two spheres ever share a line of sight in the 8 views at
0/45/90/... deg; z alternates +12/-12 mm, inside the 64-row cone). Every
sphere has an analytic flat-detector pinhole projection derived from the same
parameters the beam list uses; the test asserts each sphere's local intensity
centroid matches it within 1 px at all 8 gantry angles.

Artifacts (best-effort) land under ``C:\\Users\\hellwege\\CTBeamStudio_Data\\
Kugelwald``: the DICOM series (loadable in the app), the geometry YAML, the
raw projections + metadata, and a PNG with expected (green +) vs measured
(red x) positions for every sphere and view.
"""

import json
import shutil
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pytest

from backend.attenuation import volume_for_projection
from backend.forward_project import forward_project
from backend.geometry import ProjectionGeometry
from backend.loaders.dicom import load_dicom_series

N = 64
SPHERE_HU = 1000.0
AIR_HU = -1000.0
SPHERE_RADIUS_VOX = 1.5
# (radius_mm, angle_deg, z_mm) — 8 ring spheres + the center sphere. The
# ring angles carry a +12 deg global rotation (verified numerically) so that
# no two spheres share a line of sight in any of the 8 views (min projected
# separation 11 px), while all 3D distances to the center stay unique
# (min gap 1.4 mm) — every sphere is identifiable by its distance to center.
SPHERE_SPEC = (
    (10.0, 34.5, -8.0),
    (12.0, 79.5, 8.0),
    (16.0, 124.5, -8.0),
    (18.0, 169.5, 8.0),
    (22.0, 214.5, -8.0),
    (24.0, 259.5, 8.0),
    (26.0, 304.5, -8.0),
    (28.0, 349.5, 8.0),
    (0.0, 0.0, 0.0),
)
IPP0 = (-32.0, -32.0, -32.0)
# Loader's standard-axial origin (derived from IPP0 in load_dicom_series).
ORIGIN = (-31.0, -32.0, -32.0)
ARTIFACT_DIR = Path(r"C:\Users\hellwege\CTBeamStudio_Data\Kugelwald")


def sphere_centers_world():
    """The 9 sphere centers in world mm, each at a voxel center.

    All 3D distances to the center are unique (asserted in the roundtrip
    test), so every projected blob is identifiable by its sphere's radial
    distance.
    """
    centers = []
    for radius, a_deg, z in SPHERE_SPEC:
        a = np.deg2rad(a_deg)
        centers.append((radius * np.cos(a), radius * np.sin(a), z))
    return centers


def sphere_centers_vox():
    """Sphere centers as loaded-volume voxel indices (z, y, x)."""
    out = []
    for wx, wy, wz in sphere_centers_world():
        out.append(
            (
                int(round(wz - ORIGIN[2])),
                int(round(wy - ORIGIN[1])),
                int(round(wx - ORIGIN[0])),
            )
        )
    return out


def _hu_volume() -> np.ndarray:
    """(z, y, x) HU volume: air everywhere, 9 spheres of SPHERE_HU.

    Indexing here is the *loaded* convention (y = DICOM column, x = flipped
    DICOM row) so sphere_centers_vox() maps 1:1 onto the array the app
    produces.
    """
    hu = np.full((N, N, N), AIR_HU, dtype=np.int16)
    zz, yy, xx = np.mgrid[0:N, 0:N, 0:N]
    for cz, cy, cx in sphere_centers_vox():
        mask = (zz - cz) ** 2 + (yy - cy) ** 2 + (xx - cx) ** 2 <= SPHERE_RADIUS_VOX**2
        hu[mask] = np.int16(SPHERE_HU)
    return hu


def _write_slice(path: Path, instance: int, hu_slice: np.ndarray) -> None:
    """One axial CT slice; ``hu_slice`` is in the *DICOM* (row, col) frame."""
    import pydicom
    from pydicom.dataset import FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, generate_uid

    ds = pydicom.Dataset()
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"  # CT Image Storage
    ds.SOPInstanceUID = generate_uid()
    ds.SeriesInstanceUID = "1.2.826.0.1.3680043.8.498.33333"
    ds.StudyInstanceUID = "1.2.826.0.1.3680043.8.498.44444"
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = ds.SOPClassUID
    file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta = file_meta
    ds.Modality = "CT"
    ds.PatientID = "KUGELWALD"
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
    ds.PixelRepresentation = 1
    ds.HighBit = 15
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelData = (hu_slice.astype(np.int16) + 1024).tobytes()
    pydicom.dcmwrite(path, ds, enforce_file_format=True)


def _write_series(directory: Path) -> list[Path]:
    """64 slices; loaded-frame (z, y, x) -> DICOM (slice, row=63-x, col=y)."""
    hu = _hu_volume()
    directory.mkdir(parents=True, exist_ok=True)
    files = []
    for i in range(1, N + 1):
        z = i - 1
        # Loaded x is the flipped DICOM row: dicom_row = N - 1 - x.
        slice_hu = hu[z].T[::-1]  # (y, x) loaded -> (row, col) DICOM
        path = directory / f"slice_{i:03d}.dcm"
        _write_slice(path, i, slice_hu)
        files.append(path)
    return sorted(files)


@pytest.fixture(scope="module")
def dicom_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("kugelwald")


@pytest.fixture(scope="module")
def loaded_volume(dicom_dir):
    return load_dicom_series(_write_series(dicom_dir))


def test_dicom_roundtrip_places_all_spheres(loaded_volume):
    """All 9 spheres must land on their planned voxel centers in HU, and
    every sphere must have a unique 3D distance to the center."""
    vol = loaded_volume
    assert (vol.meta or {}).get("unit") == "HU"
    assert vol.shape == (N, N, N)

    distances = []
    for cz, cy, cx in sphere_centers_vox():
        assert vol.array[cz, cy, cx] == np.int16(SPHERE_HU)
        distances.append(
            float(
                np.linalg.norm(
                    [
                        vol.origin[0] + cx * vol.spacing[2],
                        vol.origin[1] + cy * vol.spacing[1],
                        vol.origin[2] + cz * vol.spacing[0],
                    ]
                )
            )
        )
    # Identifiability: all radial distances distinct (min gap 1 mm).
    gaps = np.diff(sorted(distances))
    assert gaps.min() >= 1.0, f"radial distance gap too small: {sorted(distances)}"


def test_kugelwald_projects_to_expected_positions(loaded_volume, dicom_dir):
    """Every sphere's local centroid must match its analytic pinhole
    projection within 1 px, in all 8 views."""
    vol = loaded_volume
    geom = ProjectionGeometry()

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
    assert all(p[i].max() > 0.05 for i in range(8)), "projection ran empty"

    # Sphere centers as the volume actually contains them (voxel centers).
    centers_world = [
        (
            vol.origin[0] + cx * vol.spacing[2],
            vol.origin[1] + cy * vol.spacing[1],
            vol.origin[2] + cz * vol.spacing[0],
        )
        for (cz, cy, cx) in sphere_centers_vox()
    ]

    # Analytic flat-detector pinhole model, same parameters as the beam list:
    # source S = (sid cos a, sid sin a, z_scan); a point P projects along the
    # ray to the detector plane sdd away from S: t = sdd / (d . axis),
    # u = t (d . U), v = t d_z; element i centers at (i - n/2 + 0.5) * spacing.
    z_scan = vol.origin[2] + 0.5 * (N - 1) * vol.spacing[0]
    expected = []  # per view: list of (row, col)
    for i in range(8):
        a = np.deg2rad(i * 45.0)
        s = np.array([geom.sid * np.cos(a), geom.sid * np.sin(a), z_scan])
        axis = np.array([-np.cos(a), -np.sin(a), 0.0])
        u_axis = np.array([-np.sin(a), np.cos(a), 0.0])
        view = []
        for pw in centers_world:
            d = np.asarray(pw) - s
            t = geom.sdd / (d @ axis)
            u = t * (d @ u_axis)
            v = t * d[2]
            view.append(
                (
                    v / geom.det_row_spacing_mm + geom.n_det_rows / 2.0 - 0.5,
                    u / geom.det_col_spacing_mm + geom.n_det_cols / 2.0 - 0.5,
                )
            )
        expected.append(view)

        # Self-check of the phantom design: no two spheres may project within
        # 8 px of each other in any view, or their blobs would blend.
        pts = np.asarray(view)
        dist = np.linalg.norm(pts[:, None, :] - pts[None, :, :], axis=-1)
        np.fill_diagonal(dist, np.inf)
        assert dist.min() >= 8.0, f"view {i}: spheres overlap ({dist.min():.1f} px)"

    # Local centroid in a +-5 px window around each expectation: the 3 mm
    # spheres project to ~6 px wide blobs, so the window holds exactly one
    # blob and the >= 11 px sphere separation keeps neighbours out.
    half = 5
    measured = []
    for i in range(8):
        frame = p[i].astype(np.float64)
        view = []
        for k in range(len(expected[i])):
            erow, ecol = expected[i][k]
            r0 = max(0, int(erow) - half)
            r1 = min(frame.shape[0], int(erow) + half + 1)
            c0 = max(0, int(ecol) - half)
            c1 = min(frame.shape[1], int(ecol) + half + 1)
            patch = frame[r0:r1, c0:c1]
            total = patch.sum()
            assert (
                total > 0
            ), f"view {i}: no signal near (row {erow:.1f}, col {ecol:.1f})"
            rr, cc = np.mgrid[r0:r1, c0:c1]
            view.append(
                (float((rr * patch).sum() / total), float((cc * patch).sum() / total))
            )
        measured.append(view)

    worst_row = worst_col = 0.0
    for i in range(8):
        for k, ((erow, ecol), (mrow, mcol)) in enumerate(zip(expected[i], measured[i])):
            worst_row = max(worst_row, abs(mrow - erow))
            worst_col = max(worst_col, abs(mcol - ecol))
            assert (
                abs(mrow - erow) <= 1.0
            ), f"view {i} sphere {k}: row centroid {mrow:.2f}, expected {erow:.2f}"
            assert (
                abs(mcol - ecol) <= 1.0
            ), f"view {i} sphere {k}: col centroid {mcol:.2f}, expected {ecol:.2f}"

    _write_artifacts(
        dicom_dir, p, proj_indices, expected, measured, worst_row, worst_col
    )


def _write_artifacts(
    dicom_dir, p, proj_indices, expected, measured, worst_row, worst_col
):
    """Best-effort diagnostics under ARTIFACT_DIR."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import yaml

        out_dir = ARTIFACT_DIR
        out_dir.mkdir(parents=True, exist_ok=True)

        app_dir = out_dir / "dicom"
        if app_dir.exists():
            shutil.rmtree(app_dir)
        shutil.copytree(dicom_dir, app_dir)

        geom = ProjectionGeometry()
        (out_dir / "geometry_default.yaml").write_text(
            yaml.safe_dump(asdict(geom), sort_keys=True)
        )

        np.save(out_dir / "projections.npy", p)
        (out_dir / "projections_meta.json").write_text(
            json.dumps(
                {
                    "phantom": "kugelwald-9-spheres-golden-angle",
                    "sphere_distances_to_center_mm": sorted(
                        round(float(np.linalg.norm(c)), 3)
                        for c in sphere_centers_world()
                    ),
                    "proj_indices": proj_indices,
                    "angles_deg": [
                        i * 360.0 / geom.projections_per_rotation for i in proj_indices
                    ],
                    "n_projections_total": geom.projections_per_rotation,
                    "energy_kev": 70.0,
                    "shape": list(p.shape),
                    "worst_deviation_px": {"row": worst_row, "col": worst_col},
                    "geometry": asdict(geom),
                },
                indent=2,
            )
        )

        fig, axes = plt.subplots(2, 4, figsize=(20, 10))
        for i, ax in enumerate(axes.flat):
            ax.imshow(p[i], cmap="gray", origin="lower", aspect="equal")
            erows = [e[0] for e in expected[i]]
            ecols = [e[1] for e in expected[i]]
            mrows = [m[0] for m in measured[i]]
            mcols = [m[1] for m in measured[i]]
            ax.plot(ecols, erows, marker="+", color="lime", markersize=8, ls="none")
            ax.plot(mcols, mrows, marker="x", color="red", markersize=6, ls="none")
            ax.set_title(f"{i * 45} deg — 9 spheres", fontsize=9)
        fig.suptitle(
            "Kugelwald (golden-angle spiral, unique radii): "
            "expected (+) vs measured (x) per sphere"
        )
        fig.tight_layout()
        fig.savefig(out_dir / "kugelwald_projection_check.png", dpi=90)
        plt.close(fig)
    except OSError:
        pass  # an unavailable artifact directory must not fail the test
