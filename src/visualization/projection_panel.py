"""Projection panel: pure helpers for the sinogram / forward-projection tabs.

The rendering functions live at the bottom of this module and are intentionally
thin wrappers around Streamlit; the helpers above are importable without
Streamlit so they can be unit-tested.
"""

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional

import numpy as np

from backend.geometry import ProjectionGeometry
from backend.loaders.sinogram import SelectionConfig, resolve_indices
from visualization.geometry_cache import save_cached_geometry


def prepare_projection_volume(volume, energy_kev: float):
    """Return ``volume`` in 1/mm, ready for forward projection.

    HU volumes are converted at ``energy_kev``; volumes already carrying
    attenuation units are passed through untouched (DICOM auto-detection can
    yield 1/mm or 1/cm directly). Converting them again would apply the
    water scaling twice, so it is deliberately not attempted.
    """
    from backend.attenuation import ATTENUATION_UNITS, volume_for_projection

    unit = (volume.meta or {}).get("unit")
    if unit in ATTENUATION_UNITS:
        return volume
    return volume_for_projection(volume, energy_kev)


@dataclass(frozen=True)
class GeometryField:
    """Description of an editable ``ProjectionGeometry`` field."""

    name: str
    label: str
    kind: str  # "int" | "float" | "choice" | "text"
    step: float = 1.0
    choices: tuple[str, ...] = ()


EDITABLE_GEOMETRY_FIELDS: tuple[GeometryField, ...] = (
    GeometryField("sdd", "SDD (mm)", "float", step=10.0),
    GeometryField("sid", "SID (mm)", "float", step=10.0),
    GeometryField("n_det_cols", "Detector Columns", "int"),
    GeometryField("n_det_rows", "Detector Rows", "int"),
    GeometryField("det_col_spacing_mm", "Column Spacing (mm)", "float", step=0.01),
    GeometryField("det_row_spacing_mm", "Row Spacing (mm)", "float", step=0.01),
    GeometryField("projections_per_rotation", "Projections / Rotation", "int"),
    GeometryField("pitch", "Pitch", "float", step=0.1),
    GeometryField("source_angle", "Source Angle (deg)", "float", step=1.0),
    GeometryField(
        "detector_in_plane_angle", "Detector In-Plane Angle (deg)", "float", step=1.0
    ),
    GeometryField(
        "detector_out_of_plane_angle",
        "Detector Out-of-Plane Angle (deg)",
        "float",
        step=1.0,
    ),
    GeometryField(
        "detector_tilt_angle", "Detector Tilt Angle (deg)", "float", step=1.0
    ),
    GeometryField("source_offset_x", "Source Offset X (mm)", "float", step=1.0),
    GeometryField("source_offset_y", "Source Offset Y (mm)", "float", step=1.0),
    GeometryField("source_offset_z", "Source Offset Z (mm)", "float", step=1.0),
    GeometryField("detector_offset_x", "Detector Offset X (mm)", "float", step=1.0),
    GeometryField("detector_offset_y", "Detector Offset Y (mm)", "float", step=1.0),
    GeometryField(
        "detector_shape",
        "Detector Shape",
        "choice",
        choices=("flat", "curved"),
    ),
    GeometryField(
        "geometry_type",
        "Geometry Type",
        "choice",
        choices=("cone_beam", "parallel", "fan_beam"),
    ),
    GeometryField("source", "Source / Manufacturer", "text"),
)

SELECTION_MODES: tuple[str, ...] = ("all", "central", "range", "downsample")


def build_selection_config(
    proj_mode: str = "all",
    proj_range: Optional[tuple[int, int]] = None,
    proj_downsample: Optional[int] = None,
    row_mode: str = "all",
    row_range: Optional[tuple[int, int]] = None,
    row_downsample: Optional[int] = None,
    col_mode: str = "all",
    col_range: Optional[tuple[int, int]] = None,
    col_downsample: Optional[int] = None,
) -> SelectionConfig:
    """Build a :class:`SelectionConfig` from per-axis UI values."""
    return SelectionConfig(
        proj_mode=proj_mode,
        proj_range=proj_range,
        proj_downsample=proj_downsample,
        row_mode=row_mode,
        row_range=row_range,
        row_downsample=row_downsample,
        col_mode=col_mode,
        col_range=col_range,
        col_downsample=col_downsample,
    )


def resolve_selection(
    config: SelectionConfig, shape: tuple[int, int, int]
) -> tuple[list[int], list[int], list[int]]:
    """Resolve a canonical ``(proj, row, col)`` selection to index lists."""
    proj_idx = resolve_indices(
        config.proj_mode,
        shape[0],
        config.proj_range,
        config.proj_downsample,
        config.proj_custom,
    )
    row_idx = resolve_indices(
        config.row_mode,
        shape[1],
        config.row_range,
        config.row_downsample,
        config.row_custom,
    )
    col_idx = resolve_indices(
        config.col_mode,
        shape[2],
        config.col_range,
        config.col_downsample,
        config.col_custom,
    )
    return proj_idx, row_idx, col_idx


def normalize_projection(array: np.ndarray) -> np.ndarray:
    """Normalize an arbitrary projection image to float32 in ``[0, 1]``.

    A constant image maps to all zeros (nothing to show).
    """
    array = np.asarray(array, dtype=np.float32)
    lo = float(array.min()) if array.size else 0.0
    hi = float(array.max()) if array.size else 0.0
    if hi <= lo:
        return np.zeros_like(array, dtype=np.float32)
    return ((array - lo) / (hi - lo)).astype(np.float32)


def apply_geometry_updates(
    geometry: ProjectionGeometry, updates: dict
) -> ProjectionGeometry:
    """Return a new geometry with ``updates`` applied.

    Raises ``ValueError`` if the updated geometry is invalid (the dataclass
    validates in ``__post_init__``).
    """
    return replace(geometry, **updates)


def normalize_difference(diff: np.ndarray) -> np.ndarray:
    """Map a signed difference to grayscale ``[0, 1]`` with zero at mid-gray."""
    diff = np.asarray(diff, dtype=np.float32)
    scale = float(np.max(np.abs(diff))) if diff.size else 0.0
    if scale == 0:
        return np.full_like(diff, 0.5, dtype=np.float32)
    return (diff / (2.0 * scale) + 0.5).astype(np.float32)


def clamp_index_state(key: str, max_index: int) -> None:
    """Keep a sliders' session-state value inside ``[0, max_index]``."""
    import streamlit as st

    if key in st.session_state:
        st.session_state[key] = int(max(0, min(st.session_state[key], max_index)))
    else:
        st.session_state[key] = 0


def resolve_view_index(key: str, n_items: int) -> int:
    """Return a valid index for a view with ``n_items`` frames.

    Clamps ``st.session_state[key]`` into ``[0, n_items - 1]`` (seeding it
    with 0 when absent). For ``n_items <= 0`` there is nothing to index:
    returns 0 without touching session state.
    """
    import streamlit as st

    if n_items <= 0:
        return 0
    clamp_index_state(key, n_items - 1)
    return int(st.session_state[key])


def index_slider(container, label: str, key: str, n_items: int) -> int:
    """Render a projection-index slider, or nothing for tiny ranges.

    Streamlit rejects sliders with ``min_value == max_value``, so a
    0..0 slider (a single frame) must never be rendered. Returns the
    selected index: 0 for empty/single-frame cases.
    """
    if n_items <= 1:
        return 0
    index = resolve_view_index(key, n_items)
    return int(container.slider(label, 0, n_items - 1, key=key))


# ---------------------------------------------------------------------------
# Streamlit rendering (thin adapters around the helpers above)
# ---------------------------------------------------------------------------

AXIS_ORDERS: tuple[tuple[str, str, str], ...] = (
    ("proj", "row", "col"),
    ("proj", "col", "row"),
    ("row", "proj", "col"),
    ("row", "col", "proj"),
    ("col", "proj", "row"),
    ("col", "row", "proj"),
)


def format_axis_order(order: tuple[str, str, str]) -> str:
    """Human-readable representation of a file axis order."""
    return " → ".join(order)


def clear_geometry_edit_state() -> None:
    """Drop cached widget values so a newly loaded geometry prefills cleanly."""
    import streamlit as st

    for key in list(st.session_state.keys()):
        if isinstance(key, str) and key.startswith("geo_edit_"):
            del st.session_state[key]


def _axis_selection_inputs(
    prefix: str,
    label: str,
    container,
    default_mode: str,
    default_step: int,
):
    import streamlit as st

    # The mode key is preset via the Session State API (dummy measurement,
    # full-geometry button). A widget created with an ``index=`` default
    # AND such a preset makes Streamlit warn "created with a default
    # value but also had its value set via the Session State API", so the
    # default lives in session state instead of the widget call.
    key = f"{prefix}_mode"
    if key not in st.session_state:
        st.session_state[key] = default_mode
    mode = container.selectbox(
        f"{label} selection",
        SELECTION_MODES,
        key=key,
    )
    range_ = None
    downsample = None
    if mode in ("central", "range"):
        start, end = container.columns(2)
        start_val = start.number_input(
            f"{label} start", min_value=0, value=0, step=1, key=f"{prefix}_start"
        )
        end_val = end.number_input(
            f"{label} end (exclusive)",
            min_value=0,
            value=0,
            step=1,
            key=f"{prefix}_end",
        )
        range_ = (int(start_val), int(end_val))
    elif mode == "downsample":
        downsample = container.number_input(
            f"{label} step",
            min_value=1,
            value=default_step,
            step=1,
            key=f"{prefix}_step",
        )
    return mode, range_, downsample


def render_selection_controls(
    prefix: str,
    container=None,
    default_proj_mode: str = "all",
    default_proj_step: int = 10,
    default_row_mode: str = "all",
    default_row_step: int = 10,
    default_col_mode: str = "all",
    default_col_step: int = 10,
) -> SelectionConfig:
    """Render per-axis selection widgets and return a ``SelectionConfig``."""
    import streamlit as st

    container = container if container is not None else st
    proj_mode, proj_range, proj_ds = _axis_selection_inputs(
        f"{prefix}_proj",
        "Projections",
        container,
        default_proj_mode,
        default_proj_step,
    )
    row_mode, row_range, row_ds = _axis_selection_inputs(
        f"{prefix}_row",
        "Rows",
        container,
        default_row_mode,
        default_row_step,
    )
    col_mode, col_range, col_ds = _axis_selection_inputs(
        f"{prefix}_col",
        "Columns",
        container,
        default_col_mode,
        default_col_step,
    )
    return build_selection_config(
        proj_mode=proj_mode,
        proj_range=proj_range,
        proj_downsample=proj_ds,
        row_mode=row_mode,
        row_range=row_range,
        row_downsample=row_ds,
        col_mode=col_mode,
        col_range=col_range,
        col_downsample=col_ds,
    )


def apply_axis_order_change(sinogram, axis_order: tuple[str, str, str]):
    """Reorient ``sinogram`` to ``axis_order``; return True if it changed.

    ``SinogramData`` already knows how to re-derive itself for a new order
    (transpose in memory for a full load, re-read from disk otherwise), so
    the UI only has to detect that the user picked something new. A ``None``
    sinogram, or the order it already has, is left untouched.
    """
    if sinogram is None or tuple(sinogram.axis_order) == tuple(axis_order):
        return False
    sinogram.axis_order = axis_order
    return True


def render_measurement_sidebar() -> None:
    """Sidebar section for loading measured projection / sinogram data."""
    import streamlit as st

    from backend.loaders.sinogram import load_sinogram

    # Collapsed on startup: measured data is an optional second input, and an
    # open section pushed the actual load controls far down the sidebar.
    with st.sidebar.expander("Measurements", expanded=False):
        path_str = st.text_input(
            "Sinogram file or DICOM folder",
            key="sinogram_path",
            placeholder=r"e.g. C:\data\projections",
        )
        axis_order = st.selectbox(
            "File axis order",
            AXIS_ORDERS,
            format_func=format_axis_order,
            key="sinogram_axis_order",
        )
        # "Load Measurements" loads the whole file by default (T-98): the
        # shape readout shows the true shape and an axis-order change can
        # re-derive in memory. The sampling options below bring the per-axis
        # selection back as an opt-in for big files — a sampled load reads
        # only the selected subset (lazily for .npy/NIfTI), never silently.
        # The Sample options in the tab govern the forward projection; to
        # compare shapes against the full load, preset the FP to "all"
        # (📐 Full projection geometry).
        sample_on_load = st.checkbox(
            "Sample instead of the whole file",
            key="load_sample_on",
            help=(
                "Load only a subset of the file. Off: the whole file is "
                "loaded. On: the per-axis selection below applies."
            ),
        )
        if sample_on_load:
            selection = render_selection_controls(
                "load",
                container=st,
                default_proj_mode="downsample",
                default_proj_step=10,
            )
        else:
            selection = build_selection_config()

        clicked = st.button("Load Measurements", key="load_measurements")
        if clicked:
            if not path_str:
                st.warning("Enter a file or folder path first.")
            else:
                path = Path(path_str)
                if not path.exists():
                    st.error(f"Path not found: {path}")
                else:
                    try:
                        with st.spinner("Loading projections..."):
                            # Loading bar with current/total projections, like
                            # the DICOM image section: a spinner alone gives
                            # no feedback on how far a big folder has come.
                            progress_bar = st.progress(0)
                            status_text = st.empty()

                            def update_progress(current: int, total: int):
                                progress_bar.progress(current / total)
                                status_text.text(
                                    f"Loading {current}/{total} projections..."
                                )

                            sinogram = load_sinogram(
                                path,
                                selection=selection,
                                geometry=st.session_state.get("projection_geometry"),
                                axis_order=axis_order,
                                progress=update_progress,
                            )
                            progress_bar.empty()
                            status_text.empty()
                    except Exception as exc:  # noqa: BLE001 - surface loader errors
                        st.error(f"Failed to load measurements: {exc}")
                    else:
                        st.session_state["sinogram"] = sinogram
                        shape = (
                            sinogram.data.shape
                            if sinogram.data is not None
                            else sinogram.original_shape
                        )
                        st.success(f"Loaded measurements {shape}.")
                        st.toast("Measurements loaded!", icon="✅")
        else:
            # The axis-order dropdown is how the user says "the file is stored
            # the other way round", and they judge it by looking at the image.
            # Apply it to already-loaded data immediately: the loader can do
            # this without another click (in memory for a full load, otherwise
            # by re-reading), so a changed order must never look like a no-op.
            try:
                # The sidebar renders before the tabs, so the reoriented data
                # is what the Sinogram Inspection tab draws this same run.
                apply_axis_order_change(st.session_state.get("sinogram"), axis_order)
            except Exception as exc:  # noqa: BLE001 - surface loader errors
                st.error(f"Failed to apply axis order: {exc}")

        # Rendered after the load attempt so the success path shows the file
        # immediately, without waiting for a later rerun.
        if st.session_state.get("sinogram") is not None:
            sinogram = st.session_state["sinogram"]
            shape = (
                sinogram.data.shape
                if sinogram.data is not None
                else sinogram.original_shape
            )
            st.caption(f"Loaded: {shape} ({sinogram.format})")
            if sinogram.path is not None:
                st.caption(f"Path: `{Path(sinogram.path).resolve()}`")
            files = tuple(getattr(sinogram, "files", ()) or ())
            if files:
                st.caption(f"Files read: {len(files)}")
                # Not an expander: this panel already lives inside the
                # "Measurements" expander, and Streamlit forbids nesting.
                st.code(
                    "\n".join(str(Path(f).resolve()) for f in files),
                    language=None,
                )

        st.divider()
        st.caption(
            "No measurement file at hand? Generate a coherent dummy pair: "
            "3D Shepp-Logan phantom (standard head size), a dummy geometry "
            "that sees the whole head, and a forward projection with "
            "scatter and Poisson noise."
        )
        if st.button("🎲 Generate dummy measurement", key="dummy_measurement"):
            from visualization.phantom import create_dummy_measured_sinogram

            try:
                with st.spinner(
                    "Synthesizing dummy measurement (forward projection + "
                    "scatter + noise)..."
                ):
                    dummy = create_dummy_measured_sinogram()
            except Exception as exc:  # noqa: BLE001 - surface generator errors
                st.error(f"Dummy measurement failed: {exc}")
            else:
                st.session_state["volume"] = dummy.volume
                st.session_state["projection_geometry"] = dummy.geometry
                st.session_state["geometry_is_default"] = False
                st.session_state["geometry_loaded_original"] = dummy.geometry
                st.session_state["sinogram"] = dummy.sinogram
                # The dummy contains the full detector and every projection
                # of its geometry, so "all" reproduces it exactly: one click
                # on "Run Forward Projection" then yields matching shapes and
                # a live comparison with difference and metrics.
                st.session_state["sample_proj_mode"] = "all"
                st.session_state["sample_row_mode"] = "all"
                st.session_state["sample_col_mode"] = "all"
                # New geometry: drop cached widget values so the geometry
                # form prefills the dummy values instead of stale ones.
                clear_geometry_edit_state()
                fp_note = (
                    "cached projection reused"
                    if dummy.params["fp_from_cache"]
                    else "projection computed"
                )
                st.toast(f"Dummy measurement ready ({fp_note}).", icon="🎲")
                st.rerun()


def render_geometry_tab(geometry: Optional[ProjectionGeometry]) -> None:
    """Load a geometry file, show it, and let the user edit its parameters."""
    import streamlit as st

    from backend.loaders.projection import load_projection_geometry

    st.subheader("Projection Geometry")

    # Geometry file loading lives here, next to the readouts and the edit
    # form — the note about what is loaded belongs beside them, not in the
    # sidebar.
    geometry_file = st.file_uploader(
        "Geometry file (.txt / .yaml)",
        type=["txt", "yaml", "yml"],
        key="geometry_tab_file",
    )
    if geometry_file is not None:
        upload_key = (
            getattr(geometry_file, "name", None),
            getattr(geometry_file, "size", None),
        )
        if st.session_state.get("last_loaded_geometry_key") != upload_key:
            content = geometry_file.read().decode("utf-8")
            suffix = Path(geometry_file.name).suffix.lower() or ".txt"

            # Create temp file with the original suffix so the loader can
            # auto-detect TXT vs YAML.
            import os
            import tempfile

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=suffix, delete=False
            ) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            try:
                loaded = load_projection_geometry(tmp_path)
                st.session_state["projection_geometry"] = loaded
                st.session_state["geometry_loaded_original"] = loaded
                st.session_state["last_loaded_geometry_key"] = upload_key
                st.session_state["geometry_is_default"] = False
                save_cached_geometry(loaded)
                clear_geometry_edit_state()
                # The readouts and the form above already rendered with the
                # old geometry this run, so rerun to show the loaded one.
                st.rerun()
            except Exception as e:
                st.error(f"Failed to load geometry: {e}")
            finally:
                os.unlink(tmp_path)

    if geometry is None:
        st.info("No geometry available — load a .txt or .yaml file above.")
        return

    if st.session_state.get("geometry_is_default"):
        st.caption(
            "No geometry file loaded — showing the default geometry. "
            "Upload a .txt or .yaml file above to replace it."
        )

    # Derived values, kept as a compact caption: st.metric renders its value
    # very large and bold, which made three secondary read-outs the most
    # prominent thing on the tab, above the editable form.
    st.caption(
        f"Fan angle {geometry.fan_angle:.2f}° · "
        f"Cone angle {geometry.cone_angle:.2f}° · "
        f"Collimation {geometry.collimation_width:.1f} mm"
    )
    st.caption(
        f"Type: {geometry.geometry_type} · Source: {geometry.source} · "
        f"Detector: {geometry.n_det_cols} × {geometry.n_det_rows} @ "
        f"{geometry.det_col_spacing_mm:.3f} × {geometry.det_row_spacing_mm:.3f} mm"
    )

    with st.form("geometry_form"):
        left, right = st.columns(2)
        updates: dict = {}
        for index, field in enumerate(EDITABLE_GEOMETRY_FIELDS):
            cell = left if index % 2 == 0 else right
            current = getattr(geometry, field.name)
            key = f"geo_edit_{field.name}"
            if field.kind == "int":
                updates[field.name] = int(
                    cell.number_input(
                        field.label,
                        min_value=1,
                        value=int(current),
                        step=int(field.step),
                        key=key,
                    )
                )
            elif field.kind == "float":
                updates[field.name] = float(
                    cell.number_input(
                        field.label,
                        value=float(current),
                        step=float(field.step),
                        format="%.4f",
                        key=key,
                    )
                )
            elif field.kind == "choice":
                choices = list(field.choices)
                current_index = choices.index(current) if current in choices else 0
                updates[field.name] = cell.selectbox(
                    field.label, choices, index=current_index, key=key
                )
            else:
                updates[field.name] = cell.text_input(
                    field.label, value=str(current), key=key
                )
        submitted = st.form_submit_button("Apply Geometry Changes", type="primary")

    if st.button("Reset to Loaded Geometry", key="geo_reset"):
        original = st.session_state.get("geometry_loaded_original")
        if original is not None:
            st.session_state["projection_geometry"] = original
            save_cached_geometry(original)
            # Re-seed the edit-form widgets with the original values (not
            # just drop them): dropping leaves Streamlit's persisted widget
            # state in place, so after a dummy load the form kept showing the
            # edited numbers and "Reset" looked like a no-op.
            clear_geometry_edit_state()
            for field in EDITABLE_GEOMETRY_FIELDS:
                st.session_state[f"geo_edit_{field.name}"] = getattr(
                    original, field.name
                )
            st.rerun()

    if submitted:
        try:
            updated = apply_geometry_updates(geometry, updates)
        except ValueError as exc:
            st.error(f"Invalid geometry: {exc}")
        else:
            st.session_state["projection_geometry"] = updated
            st.session_state["geometry_is_default"] = False
            save_cached_geometry(updated)
            st.success("Geometry updated.")
            st.rerun()


def projection_display_spacing(geometry):
    """Detector ``(row_spacing_mm, col_spacing_mm)`` for display resampling.

    The raw projection image's pixels are anisotropic in mm (axial row
    spacing vs in-plane column spacing), so the UI resamples the row axis
    by the row/col ratio before display — the same edge conversion the MPR
    planes get. ``None`` geometry means the raw shape is shown as-is.
    """
    if geometry is None:
        return None
    return (float(geometry.det_row_spacing_mm), float(geometry.det_col_spacing_mm))


def _render_projection_image(array: np.ndarray, caption: str, spacing=None) -> None:
    """Render one projection image with square mm pixels.

    ``spacing`` is ``(row_spacing_mm, col_spacing_mm)`` from
    :func:`projection_display_spacing`; an anisotropic detector would
    otherwise show a distorted phantom (a 2 mm x 1 mm detector shows the
    head half as tall as it really is).
    """
    import streamlit as st

    from visualization.app import to_isotropic

    image = normalize_projection(array)
    if spacing is not None:
        image = to_isotropic(image, spacing)
    st.image(
        image,
        caption=caption,
        clamp=True,
        use_column_width=True,
    )


# Height (px) of an empty slot in the Sinogram Inspection tab. The three
# views sit in equal thirds of a wide layout, so this roughly squares the
# box off against one column. The point is that an empty slot reserves the
# same vertical space as a filled one, which keeps the row -- and everything
# below it -- from jumping when the first projection arrives.
PLACEHOLDER_HEIGHT_PX = 360


def _render_placeholder(message: str) -> None:
    """Render an empty slot at the size a projection image will occupy.

    A bare ``st.info`` is a one-line strip, which left the three columns
    looking collapsed until data arrived. The fixed-height, borderless
    container gives the hint the same footprint as an image slot.
    """
    import streamlit as st

    with st.container(height=PLACEHOLDER_HEIGHT_PX, border=False):
        st.info(message)


def render_comparison_tab(volume, geometry: Optional[ProjectionGeometry]) -> None:
    """Sinogram Inspection: measured vs simulated projections side by side.

    The full frame (three columns + shared index slider) always renders;
    each slot fills in as its data arrives. Measured data is shown as soon
    as it is loaded; simulated data appears after a forward projection.
    """
    import streamlit as st

    from backend.forward_project import PARALLELPROJ_AVAILABLE, forward_project
    from visualization.comparison import (
        build_distribution_figure,
        build_metric_figure,
        compute_metrics_per_slice,
    )

    st.subheader("Sinogram Inspection")
    sinogram = st.session_state.get("sinogram")

    measured = None
    if sinogram is not None:
        measured = (
            sinogram.data if sinogram.data is not None else sinogram.materialize()
        )

    result = st.session_state.get("forward_projection")
    simulated = result.projections if result is not None else None

    # --- Views first: the three panels sit at the top of the tab ------------
    n_meas = measured.shape[0] if measured is not None else 0
    n_sim = simulated.shape[0] if simulated is not None else 0
    n_total = max(n_meas, n_sim)

    shared = resolve_view_index("sino_shared_index", n_total)
    meas_index = min(shared, n_meas - 1) if n_meas else 0
    sim_index = min(shared, n_sim - 1) if n_sim else 0
    shapes_match = (
        measured is not None
        and simulated is not None
        and measured.shape == simulated.shape
    )

    col_meas, col_sim, col_diff = st.columns(3)
    # Detector (row, col) spacing in mm for the display resampling: the raw
    # projection pixels are anisotropic in mm, so the views resample the row
    # axis to show the phantom undistorted.
    meas_spacing = projection_display_spacing(
        getattr(sinogram, "geometry", None) if sinogram is not None else None
    )
    sim_spacing = (
        projection_display_spacing(getattr(result, "geometry", None))
        if result is not None
        else None
    )
    with col_meas:
        if n_meas:
            st.caption(f"Measured projection {meas_index + 1}/{n_meas}")
            _render_projection_image(
                measured[meas_index],
                f"Measured projection {meas_index + 1}/{n_meas}",
                spacing=meas_spacing,
            )
        else:
            _render_placeholder(
                "No measured data — load measurements in the sidebar or "
                "generate a dummy measurement."
            )
    with col_sim:
        if n_sim:
            st.caption(f"Simulated projection {sim_index + 1}/{n_sim}")
            _render_projection_image(
                simulated[sim_index],
                f"Simulated projection {sim_index + 1}/{n_sim}",
                spacing=sim_spacing,
            )
        else:
            _render_placeholder("Run the forward projection to fill this column.")
    with col_diff:
        if shapes_match:
            diff = normalize_difference(measured[meas_index] - simulated[sim_index])
            if meas_spacing is not None:
                from visualization.app import to_isotropic

                diff = to_isotropic(diff, meas_spacing)
            # Same structure as the measured/simulated columns: a caption line
            # above, then the image — otherwise the difference image starts
            # one caption-line higher than its neighbours.
            st.caption("Difference (measured − simulated)")
            st.image(
                diff,
                clamp=True,
                use_column_width=True,
            )
        elif n_meas and n_sim:
            _render_placeholder(
                f"Shapes differ ({measured.shape} vs {simulated.shape}) — preset "
                'the projection to "all" (📐 Full projection geometry) to '
                "compare."
            )
        else:
            _render_placeholder(
                "Difference appears once measured and simulated shapes match."
            )

    # Shared slider below the views. Renders nothing when there are fewer
    # than two frames on either side (a 0..0 slider is illegal in Streamlit).
    index_slider(st, "Projection index", "sino_shared_index", n_total)

    if sinogram is not None:
        st.caption(
            f"Measured: {measured.shape} · axis order "
            f"{format_axis_order(sinogram.axis_order)} · format {sinogram.format}"
            + (
                f" · `{Path(sinogram.path).resolve()}`"
                if sinogram.path is not None
                else ""
            )
        )
    else:
        st.caption("Measured: none loaded")
    if result is not None:
        st.caption(
            f"Simulated: {simulated.shape} · {len(result.proj_indices)} projections"
        )
    else:
        st.caption("Simulated: not run yet")

    # --- Per-slice metrics + distribution (only when comparable) ------------
    if shapes_match:
        per_slice = compute_metrics_per_slice(measured, simulated)
        col_plot, col_dist = st.columns(2)
        with col_plot:
            st.caption("Metrics per slice")
            st.plotly_chart(
                build_metric_figure(
                    per_slice,
                    current_index=shared,
                    proj_indices=result.proj_indices,
                ),
                use_container_width=True,
            )
        with col_dist:
            st.caption("Distribution over projections")
            st.plotly_chart(
                build_distribution_figure(per_slice),
                use_container_width=True,
            )
        st.caption(
            f"Slice {shared + 1}: MAE {per_slice['mae'][shared]:.4g} · "
            f"RMSE {per_slice['rmse'][shared]:.4g} · "
            f"SSIM {per_slice['ssim'][shared]:.4f}"
        )

    # --- Sample options (forward projection) --------------------------------
    with st.expander("Sample options", expanded=True):
        st.caption(
            "Which projections and detector rows/columns the forward "
            "projection samples. Measurements always load the whole file; "
            'to compare shapes, preset the projection to "all" (📐 Full '
            "projection geometry)."
        )
        selection = render_selection_controls(
            "sample",
            container=st,
            default_proj_mode="downsample",
            default_proj_step=100,
            default_row_mode="downsample",
            default_row_step=4,
            default_col_mode="downsample",
            default_col_step=8,
        )
        # The sidebar loads measurements before this tab renders, so the
        # loader cannot instantiate the shared widgets itself — it reads
        # this stash instead. A widget change reruns before any click can
        # happen, so the stash is never stale at click time.
        st.session_state["sample_selection"] = selection
        # One click back to the full detector and every projection of the
        # geometry: the same preset the dummy measurement applies, without
        # having to touch the three dropdowns by hand. The preset runs as
        # an on_click callback because callbacks execute before the script
        # (and thus before these widgets are instantiated) — assigning the
        # widget-backed keys after them would raise.

        def _preset_full_geometry():
            for axis in ("proj", "row", "col"):
                st.session_state[f"sample_{axis}_mode"] = "all"

        if st.button(
            "📐 Full projection geometry",
            key="sample_full_geometry",
            on_click=_preset_full_geometry,
            help=(
                "Preset all selections to 'all': every projection, all "
                "detector rows and columns. Click 'Run Forward Projection' "
                "afterwards to compute."
            ),
        ):
            st.toast("Selection preset to full projection geometry.", icon="📐")
        use_cuda = st.checkbox(
            "Use CUDA if available (forward projection only)",
            value=True,
            key="fp_use_cuda",
        )
        st.caption("Without CUDA the projection runs on the CPU.")
        energy_kev = float(
            st.slider(
                "Beam energy (keV)",
                min_value=30,
                max_value=150,
                value=70,
                step=5,
                key="fp_energy_kev",
                help=(
                    "Monoenergetic energy used to convert HU to linear "
                    "attenuation before projection (water-equivalent model)."
                ),
            )
        )
        st.caption(
            "The volume is converted from HU to attenuation (1/mm) at this "
            "energy before projection."
        )

    if not PARALLELPROJ_AVAILABLE:
        st.warning(
            "parallelproj is not installed in this environment. Forward "
            "projection will return zeros. Install it via conda-forge."
        )

    if st.button("Run Forward Projection", type="primary", key="fp_run"):
        if volume is None:
            st.error("Load a volume in the sidebar first.")
        else:
            detector_shape = (
                geometry.projections_per_rotation,
                geometry.n_det_rows,
                geometry.n_det_cols,
            )
            try:
                proj_idx, row_idx, col_idx = resolve_selection(
                    selection, detector_shape
                )
                projection_volume = prepare_projection_volume(volume, energy_kev)
                with st.spinner("Running forward projection..."):
                    result = forward_project(
                        projection_volume,
                        geometry,
                        row_indices=row_idx,
                        col_indices=col_idx,
                        proj_indices=proj_idx,
                        use_cuda=use_cuda,
                    )
            except Exception as exc:  # noqa: BLE001 - backend errors in the UI
                st.error(f"Forward projection failed: {exc}")
            else:
                st.session_state["forward_projection"] = result
                # The views and captions above already rendered with the old
                # state this run, so rerun to fill the simulated column and
                # the metric plots immediately.
                st.toast(
                    f"Computed {result.projections.shape[0]} projections.", icon="✅"
                )
                st.rerun()
