from pathlib import Path

import numpy as np
import pytest

from backend.geometry import ProjectionGeometry
from backend.loaders.sinogram import (
    SelectionConfig,
    SinogramData,
    _detect_format,
    _load_numpy,
    load_sinogram,
    resolve_indices,
    scan_dicom_sinogram,
)


def test_resolve_all():
    assert resolve_indices("all", 10) == list(range(10))


def test_resolve_central():
    assert resolve_indices("central", 10, range_=(3, 7)) == [3, 4, 5, 6]


def test_resolve_range():
    assert resolve_indices("range", 10, range_=(2, 5)) == [2, 3, 4]


def test_resolve_downsample():
    assert resolve_indices("downsample", 10, downsample=3) == [0, 3, 6, 9]


def test_resolve_custom():
    assert resolve_indices("custom", 10, custom=[0, 2, 5]) == [0, 2, 5]


def test_resolve_bad_mode():
    with pytest.raises(ValueError):
        resolve_indices("bogus", 10)


def test_resolve_range_out_of_bounds():
    with pytest.raises(IndexError):
        resolve_indices("range", 5, range_=(0, 10))


def test_resolve_empty_result_raises():
    with pytest.raises(ValueError):
        resolve_indices("central", 5, range_=(5, 5))


def test_axis_order_default_is_canonical():
    s = SinogramData(
        data=None,
        geometry=None,
        selection=SelectionConfig(),
        original_shape=(3, 4, 5),
        source_axis_order=("proj", "row", "col"),
    )
    assert s.axis_order == ("proj", "row", "col")


def test_axis_order_invalid_raises():
    s = SinogramData(
        data=None,
        geometry=None,
        selection=SelectionConfig(),
        original_shape=(3, 4, 5),
        source_axis_order=("proj", "row", "col"),
    )
    with pytest.raises(ValueError):
        s.axis_order = ("proj", "row")  # not a permutation


def test_materialize_replaces_none_with_loader_result():
    s = SinogramData(
        data=None,
        geometry=None,
        selection=SelectionConfig(),
        original_shape=(3, 4, 5),
        source_axis_order=("proj", "row", "col"),
        _loader=lambda: np.zeros((3, 4, 5)),
    )
    out = s.materialize()
    assert out.shape == (3, 4, 5)
    assert s.data.shape == (3, 4, 5)


def test_detect_format_npy(tmp_path):
    p = tmp_path / "a.npy"
    p.touch()
    assert _detect_format(p) == "numpy"


def test_detect_format_npz(tmp_path):
    p = tmp_path / "a.npz"
    p.touch()
    assert _detect_format(p) == "numpy"


def test_detect_format_unknown(tmp_path):
    p = tmp_path / "a.xyz"
    p.touch()
    assert _detect_format(p) == "unknown"


def test_load_numpy_full(tmp_path):
    arr = np.zeros((3, 4, 5))
    p = tmp_path / "s.npy"
    np.save(p, arr)
    s = _load_numpy(p, SelectionConfig(), ("proj", "row", "col"))
    assert s.data.shape == (3, 4, 5)
    assert s.original_shape == (3, 4, 5)


def test_load_numpy_selected_rows(tmp_path):
    arr = np.arange(60).reshape(3, 4, 5)
    p = tmp_path / "s.npy"
    np.save(p, arr)
    sel = SelectionConfig(row_mode="range", row_range=(1, 3))
    s = _load_numpy(p, sel, ("proj", "row", "col"))
    assert s.data.shape == (3, 2, 5)
    np.testing.assert_array_equal(s.data[:, 0], arr[:, 1])


def test_load_numpy_axis_order_normalizes(tmp_path):
    # file stored (row, proj, col) -> canonical (proj, row, col)
    arr = np.arange(24).reshape(2, 3, 4)  # (row, proj, col)
    p = tmp_path / "s.npy"
    np.save(p, arr)
    s = _load_numpy(p, SelectionConfig(), ("row", "proj", "col"))
    assert s.data.shape == (3, 2, 4)
    assert s.source_axis_order == ("row", "proj", "col")


def test_load_npy_confused_ext(tmp_path):
    p = tmp_path / "a.xyz"
    p.touch()
    with pytest.raises(ValueError):
        load_sinogram(p)


def test_load_sinogram_numpy(tmp_path):
    arr = np.zeros((3, 4, 5))
    p = tmp_path / "s.npy"
    np.save(p, arr)
    s = load_sinogram(p)
    assert s.data.shape == (3, 4, 5)
    assert s.format == "numpy"


# --- T-90: lazy subset reads (mmap npy, pre-sliced NIfTI) ---


def test_load_numpy_subset_uses_mmap(tmp_path, monkeypatch):
    arr = np.arange(60).reshape(3, 4, 5)
    p = tmp_path / "s.npy"
    np.save(p, arr)
    calls = []
    real_load = np.load

    def spy_load(*args, **kwargs):
        calls.append(kwargs.get("mmap_mode"))
        return real_load(*args, **kwargs)

    monkeypatch.setattr(np, "load", spy_load)
    sel = SelectionConfig(row_mode="range", row_range=(1, 3))
    s = _load_numpy(p, sel, ("proj", "row", "col"))
    assert calls == ["r"]  # subset: memory-mapped, only selected pages read
    assert s.data.shape == (3, 2, 5)
    np.testing.assert_array_equal(s.data[:, 0], arr[:, 1])


def test_load_numpy_full_stays_eager(tmp_path, monkeypatch):
    arr = np.zeros((3, 4, 5))
    p = tmp_path / "s.npy"
    np.save(p, arr)
    calls = []
    real_load = np.load

    def spy_load(*args, **kwargs):
        calls.append(kwargs.get("mmap_mode"))
        return real_load(*args, **kwargs)

    monkeypatch.setattr(np, "load", spy_load)
    s = _load_numpy(p, SelectionConfig(), ("proj", "row", "col"))
    assert calls == [None]  # full selection: eager read for in-memory re-derive
    assert s.data.shape == (3, 4, 5)


def test_load_npz(tmp_path):
    arr = np.zeros((3, 4, 5))
    p = tmp_path / "s.npz"
    np.savez(p, arr)
    s = _load_numpy(p, SelectionConfig(), ("proj", "row", "col"))
    assert s.data.shape == (3, 4, 5)
    assert s.format == "numpy"


# --- NIfTI via nibabel (optional dependency; skip if absent) ---
#
# The guard must not be a module-level ``pytest.importorskip``: that aborts
# collection of the whole file, silently deleting every test below it —
# including the numpy/DICOM tests that need no nibabel. Import defensively
# and skip only the tests that actually use it.
try:
    import nibabel as nib
except ImportError:  # pragma: no cover - depends on environment
    nib = None

requires_nibabel = pytest.mark.skipif(
    nib is None, reason="nibabel (the 'nifti' extra) is not installed"
)


@requires_nibabel
def test_load_nifti_full(tmp_path):
    arr = np.zeros((3, 4, 5))
    img = nib.Nifti1Image(arr, np.eye(4))
    p = tmp_path / "s.nii.gz"
    nib.save(img, p)
    from backend.loaders.sinogram import SelectionConfig, _load_nifti

    s = _load_nifti(p, SelectionConfig(), ("proj", "row", "col"))
    assert s.data.shape == (3, 4, 5)
    assert s.format == "nifti"


@requires_nibabel
def test_load_nifti_axis_normalizes(tmp_path):
    # file stored (row, proj, col) -> canonical (proj, row, col)
    arr = np.arange(24).reshape(2, 3, 4)  # (row, proj, col)
    img = nib.Nifti1Image(arr, np.eye(4), dtype=np.float32)
    p = tmp_path / "s.nii.gz"
    nib.save(img, p)
    from backend.loaders.sinogram import SelectionConfig, _load_nifti

    s = _load_nifti(p, SelectionConfig(), ("row", "proj", "col"))
    assert s.data.shape == (3, 2, 4)


@requires_nibabel
def test_load_nifti_subset_shape(tmp_path):
    arr = np.arange(60).reshape(3, 4, 5)
    img = nib.Nifti1Image(arr, np.eye(4), dtype=np.float32)
    p = tmp_path / "s.nii.gz"
    nib.save(img, p)
    from backend.loaders.sinogram import SelectionConfig, _load_nifti

    sel = SelectionConfig(proj_mode="range", proj_range=(1, 3))
    s = _load_nifti(p, sel, ("proj", "row", "col"))
    assert s.data.shape == (2, 4, 5)


# --- T-90: lazy subset reads via dataobj basic slicing ---


@requires_nibabel
def test_load_nifti_lazy_range_preslices_dataobj(tmp_path, monkeypatch):
    import nibabel.arrayproxy as ap

    from backend.loaders.sinogram import SelectionConfig, _load_nifti

    arr = np.arange(60).reshape(3, 4, 5)
    img = nib.Nifti1Image(arr, np.eye(4), dtype=np.float32)
    p = tmp_path / "s.nii.gz"
    nib.save(img, p)
    reads = []
    real_getitem = ap.ArrayProxy.__getitem__

    def spy_getitem(self, item):
        reads.append(item)
        return real_getitem(self, item)

    monkeypatch.setattr(ap.ArrayProxy, "__getitem__", spy_getitem)
    sel = SelectionConfig(proj_mode="range", proj_range=(1, 3))
    s = _load_nifti(p, sel, ("proj", "row", "col"))
    # only the selected slab was read from disk, as one basic slice
    assert reads == [(slice(1, 3), slice(None), slice(None))]
    assert s.data.shape == (2, 4, 5)
    np.testing.assert_array_equal(s.data, arr[1:3])


@requires_nibabel
def test_load_nifti_lazy_downsample(tmp_path, monkeypatch):
    import nibabel.arrayproxy as ap

    from backend.loaders.sinogram import SelectionConfig, _load_nifti

    arr = np.arange(60).reshape(3, 4, 5)
    img = nib.Nifti1Image(arr, np.eye(4), dtype=np.float32)
    p = tmp_path / "s.nii.gz"
    nib.save(img, p)
    reads = []
    real_getitem = ap.ArrayProxy.__getitem__

    def spy_getitem(self, item):
        reads.append(item)
        return real_getitem(self, item)

    monkeypatch.setattr(ap.ArrayProxy, "__getitem__", spy_getitem)
    sel = SelectionConfig(proj_mode="downsample", proj_downsample=2)
    s = _load_nifti(p, sel, ("proj", "row", "col"))
    assert reads == [(slice(0, 3, 2), slice(None), slice(None))]
    assert s.data.shape == (2, 4, 5)
    np.testing.assert_array_equal(s.data, arr[::2])


@requires_nibabel
def test_load_nifti_lazy_multi_axis_subset(tmp_path, monkeypatch):
    import nibabel.arrayproxy as ap

    from backend.loaders.sinogram import SelectionConfig, _load_nifti

    arr = np.arange(60).reshape(3, 4, 5)
    img = nib.Nifti1Image(arr, np.eye(4), dtype=np.float32)
    p = tmp_path / "s.nii.gz"
    nib.save(img, p)
    reads = []
    real_getitem = ap.ArrayProxy.__getitem__

    def spy_getitem(self, item):
        reads.append(item)
        return real_getitem(self, item)

    monkeypatch.setattr(ap.ArrayProxy, "__getitem__", spy_getitem)
    sel = SelectionConfig(
        proj_mode="range",
        proj_range=(0, 2),
        col_mode="downsample",
        col_downsample=2,
    )
    s = _load_nifti(p, sel, ("proj", "row", "col"))
    assert reads == [(slice(0, 2), slice(None), slice(0, 5, 2))]
    assert s.data.shape == (2, 4, 3)
    np.testing.assert_array_equal(s.data, arr[0:2, :, ::2])


@requires_nibabel
def test_load_nifti_lazy_subset_transposed(tmp_path, monkeypatch):
    # file stored (row, proj, col): the proj slab sits on file axis 1
    import nibabel.arrayproxy as ap

    from backend.loaders.sinogram import SelectionConfig, _load_nifti

    arr = np.arange(24).reshape(2, 3, 4)
    img = nib.Nifti1Image(arr, np.eye(4), dtype=np.float32)
    p = tmp_path / "s.nii.gz"
    nib.save(img, p)
    reads = []
    real_getitem = ap.ArrayProxy.__getitem__

    def spy_getitem(self, item):
        reads.append(item)
        return real_getitem(self, item)

    monkeypatch.setattr(ap.ArrayProxy, "__getitem__", spy_getitem)
    sel = SelectionConfig(proj_mode="range", proj_range=(0, 2))
    s = _load_nifti(p, sel, ("row", "proj", "col"))
    assert reads == [(slice(None), slice(0, 2), slice(None))]
    assert s.data.shape == (2, 2, 4)
    np.testing.assert_array_equal(s.data, arr[:, 0:2, :].transpose(1, 0, 2))


@requires_nibabel
def test_load_nifti_custom_selection_reads_fully(tmp_path):
    # "custom" index lists need fancy indexing, which the proxy cannot do:
    # the file is read fully and the selection applied in memory
    from backend.loaders.sinogram import SelectionConfig, _load_nifti

    arr = np.arange(60).reshape(3, 4, 5)
    img = nib.Nifti1Image(arr, np.eye(4), dtype=np.float32)
    p = tmp_path / "s.nii.gz"
    nib.save(img, p)
    sel = SelectionConfig(proj_mode="custom", proj_custom=[0, 2])
    s = _load_nifti(p, sel, ("proj", "row", "col"))
    assert s.data.shape == (2, 4, 5)
    np.testing.assert_array_equal(s.data, arr[[0, 2]])


@requires_nibabel
def test_load_nifti_range_out_of_bounds_raises(tmp_path):
    # invalid range_ is not pre-sliced; resolve_indices raises as before
    from backend.loaders.sinogram import SelectionConfig, _load_nifti

    arr = np.zeros((3, 4, 5))
    img = nib.Nifti1Image(arr, np.eye(4))
    p = tmp_path / "s.nii.gz"
    nib.save(img, p)
    sel = SelectionConfig(proj_mode="range", proj_range=(0, 100))
    with pytest.raises(IndexError):
        _load_nifti(p, sel, ("proj", "row", "col"))


@requires_nibabel
def test_load_nifti_empty_range_raises(tmp_path):
    from backend.loaders.sinogram import SelectionConfig, _load_nifti

    arr = np.zeros((3, 4, 5))
    img = nib.Nifti1Image(arr, np.eye(4))
    p = tmp_path / "s.nii.gz"
    nib.save(img, p)
    sel = SelectionConfig(proj_mode="range", proj_range=(2, 2))
    with pytest.raises(ValueError):
        _load_nifti(p, sel, ("proj", "row", "col"))


@requires_nibabel
def test_load_nifti_4d_raises(tmp_path):
    arr = np.zeros((3, 4, 5, 6))
    img = nib.Nifti1Image(arr, np.eye(4))
    p = tmp_path / "s4d.nii.gz"
    nib.save(img, p)
    from backend.loaders.sinogram import SelectionConfig, _load_nifti

    with pytest.raises(ValueError):
        _load_nifti(p, SelectionConfig(), ("proj", "row", "col"))


# --- Task 4: load_sinogram dispatch + axis_order re-derivation ---


def test_load_sinogram_dispatch_numpy(tmp_path):
    arr = np.zeros((3, 4, 5))
    p = tmp_path / "s.npy"
    np.save(p, arr)
    s = load_sinogram(p)
    assert s.format == "numpy"
    assert s.data.shape == (3, 4, 5)


def test_load_sinogram_numpy_attaches_geometry(tmp_path):
    """A numpy load must carry the given geometry — the app passes the
    active (default) geometry, whose projections_per_rotation is 2304 —
    instead of silently dropping it like the DICOM path never did."""
    p = tmp_path / "s.npy"
    np.save(p, np.zeros((4, 5, 6), dtype=np.float32))
    geometry = ProjectionGeometry()
    s = load_sinogram(p, geometry=geometry)
    assert s.geometry is geometry
    assert s.geometry.projections_per_rotation == 2304


def test_load_sinogram_unknown(tmp_path):
    p = tmp_path / "a.xyz"
    p.touch()
    with pytest.raises(ValueError):
        load_sinogram(p)


def test_axis_order_change_after_full_load(tmp_path):
    # file stored (row, proj, col); axis_order flips AFTER load -> in-memory re-derive
    arr = np.arange(24).reshape(2, 3, 4)  # (row, proj, col)
    p = tmp_path / "s.npy"
    np.save(p, arr)
    s = load_sinogram(p)  # default canonical, misread -> data (2,3,4)
    s.axis_order = ("row", "proj", "col")
    assert s.data.shape == (3, 2, 4)
    assert s.source_axis_order == ("row", "proj", "col")


def test_axis_order_change_reloads_after_partial(tmp_path):
    # partial selection -> no raw held -> axis flip re-reads from disk with new order
    arr = np.arange(24).reshape(2, 3, 4)  # (row, proj, col)
    p = tmp_path / "s.npy"
    np.save(p, arr)
    sel = SelectionConfig(proj_mode="range", proj_range=(0, 2))
    s = load_sinogram(p, selection=sel)
    s.axis_order = ("row", "proj", "col")
    assert s.data.shape == (
        2,
        2,
        4,
    )  # re-read with new order + canonical proj selection
    assert s.format == "numpy"


def test_exports():
    from backend.loaders import (
        SelectionConfig,
        SinogramData,
        load_sinogram,
        resolve_indices,
    )

    assert callable(load_sinogram)


# --- Task 5: DICOM lazy sinogram loader + scan_dicom_sinogram ---


def test_scan_dicom_sinogram(tmp_path, create_projection_dicom):
    d = create_projection_dicom(tmp_path)
    info = scan_dicom_sinogram(d)
    assert info["n_proj"] == 3
    assert info["n_rows"] == 4
    assert info["n_cols"] == 5


def test_load_dicom_full(tmp_path, create_projection_dicom):
    d = create_projection_dicom(tmp_path)
    s = load_sinogram(d)
    assert s.format == "dicom"
    assert s.data.shape == (3, 4, 5)


def test_load_dicom_lazy_selection(tmp_path, create_projection_dicom):
    d = create_projection_dicom(tmp_path)
    sel = SelectionConfig(proj_mode="range", proj_range=(0, 2))
    s = load_sinogram(d, selection=sel)
    assert s.format == "dicom"
    assert s.data.shape == (2, 4, 5)


def test_load_dicom_no_series(tmp_path):
    d = tmp_path / "empty_dir"
    d.mkdir()
    with pytest.raises(ValueError):
        scan_dicom_sinogram(d)


def test_load_dicom_reports_per_projection_progress(tmp_path, create_projection_dicom):
    """The UI shows a loading bar during the load, so the DICOM sinogram
    loader reports (current, total) per projection like the image loader
    reports slices."""
    d = create_projection_dicom(tmp_path)
    calls = []

    s = load_sinogram(d, progress=lambda current, total: calls.append((current, total)))

    assert s.data.shape == (3, 4, 5)
    assert calls == [(1, 3), (2, 3), (3, 3)]


def test_load_numpy_reports_single_shot_progress(tmp_path):
    """Single-read formats call progress once — the bar jumps to 100 %."""
    p = tmp_path / "s.npy"
    np.save(p, np.zeros((3, 4, 5), dtype=np.float32))
    calls = []

    s = load_sinogram(p, progress=lambda current, total: calls.append((current, total)))

    assert s.data.shape == (3, 4, 5)
    assert calls == [(1, 1)]


def test_load_dicom_records_only_the_files_it_read(tmp_path, create_projection_dicom):
    """The UI has to name the exact files behind a folder load, and with a
    projection selection that is a subset — not every file in the folder."""
    d = create_projection_dicom(tmp_path)

    full = load_sinogram(d)
    assert [Path(f).name for f in full.files] == [
        f.name for f in sorted(d.glob("*.dcm"))
    ]

    sel = SelectionConfig(proj_mode="range", proj_range=(1, 3))
    subset = load_sinogram(d, selection=sel)
    assert len(subset.files) == 2
    assert [Path(f).name for f in subset.files] == [
        Path(f).name for f in sorted(d.glob("*.dcm"))[1:3]
    ]


def test_load_numpy_records_the_single_file(tmp_path):
    path = tmp_path / "sino.npy"
    np.save(path, np.zeros((2, 3, 4), dtype=np.float32))

    s = load_sinogram(path)

    assert [Path(f).name for f in s.files] == ["sino.npy"]


# --- DICOM honours the file axis order -------------------------------------
#
# A DICOM projection folder stacks its frames along a fixed axis, so the
# native order is always (proj, row, col). A user who knows the detector is
# stored transposed must still be able to say so, exactly as with .npy.


def test_load_dicom_honours_transposed_axis_order(tmp_path, create_projection_dicom):
    d = create_projection_dicom(tmp_path, graded=True)

    s = load_sinogram(d, axis_order=("proj", "col", "row"))

    # Declared order transposes each detector frame: (4, 5) -> (5, 4).
    assert s.data.shape == (3, 5, 4)
    assert s.source_axis_order == ("proj", "col", "row")
    canonical = load_sinogram(d, axis_order=("proj", "row", "col"))
    np.testing.assert_array_equal(s.data, canonical.data.transpose(0, 2, 1))


def test_load_dicom_default_axis_order_is_untransposed(
    tmp_path, create_projection_dicom
):
    d = create_projection_dicom(tmp_path, graded=True)

    s = load_sinogram(d)

    assert s.data.shape == (3, 4, 5)
    assert s.source_axis_order == ("proj", "row", "col")


def test_load_dicom_applies_row_col_selection_in_canonical_space(
    tmp_path, create_projection_dicom
):
    """Row/col selection is canonical, so with a transposed order "rows" must
    select along the axis the user calls rows — the file's columns."""
    d = create_projection_dicom(tmp_path, graded=True)
    sel = SelectionConfig(row_mode="range", row_range=(0, 2))

    s = load_sinogram(d, selection=sel, axis_order=("proj", "col", "row"))

    # canonical rows == the 5-long axis; none of it was cut by file columns
    assert s.data.shape == (3, 2, 4)


def test_dicom_axis_order_change_after_load_reorients(
    tmp_path, create_projection_dicom
):
    """Changing the order after a DICOM load must reorient, not no-op."""
    d = create_projection_dicom(tmp_path, graded=True)
    s = load_sinogram(d)
    assert s.data.shape == (3, 4, 5)

    s.axis_order = ("proj", "col", "row")

    assert s.data.shape == (3, 5, 4)
    assert s.source_axis_order == ("proj", "col", "row")
