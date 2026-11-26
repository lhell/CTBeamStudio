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

# Session-state key of the scan's projection count, edited in the Geometry tab.
# The 3D trajectory and the forward projection's projection axis both use it;
# ``projections_per_rotation`` only defines how many views make one turn.
SCAN_N_PROJECTIONS_KEY = "scan_n_projections"


def scan_n_projections(geometry) -> int:
    """Return the number of projections in the scan.

    This is the number the user edits in the Geometry tab, valid for the 3D
    trajectory and the forward projection. Until that tab has rendered once,
    fall back to one full rotation (``projections_per_rotation``), which is
    the scan length of a circular acquisition.
    """
    import streamlit as st

    fallback = int(getattr(geometry, "projections_per_rotation", 0) or 0)
    return int(st.session_state.get(SCAN_N_PROJECTIONS_KEY, fallback))


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


def stack_window(*arrays) -> tuple[float, float]:
    """Return the one ``(lo, hi)`` display window for whole projection stacks.

    Every view and every slice of the comparison tab shares this window, so a
    given detector value gets the same gray level everywhere. With a per-frame
    normalize, a dim projection and a bright one looked identical and
    measured/simulated could not be compared at all. Empty or constant input
    has no range to map, so ``(0, 1)`` is returned.
    """
    lo, hi = np.inf, -np.inf
    for array in arrays:
        if array is None or not np.size(array):
            continue
        lo = min(lo, float(np.min(array)))
        hi = max(hi, float(np.max(array)))
    if not (np.isfinite(lo) and np.isfinite(hi)) or hi <= lo:
        return (0.0, 1.0)
    return (float(lo), float(hi))


def window_image(array: np.ndarray, window: tuple[float, float]) -> np.ndarray:
    """Map raw values to ``[0, 1]`` through a shared ``(lo, hi)`` window.

    Values outside the window clip, which is the point of a common window: a
    frame brighter than the rest saturates instead of silently rescaling
    itself and looking like every other frame.
    """
    lo, hi = window
    span = hi - lo
    if span <= 0:
        return np.zeros(np.shape(array), dtype=np.float32)
    image = (np.asarray(array, dtype=np.float32) - lo) / span
    return np.clip(image, 0.0, 1.0).astype(np.float32)


def apply_geometry_updates(
    geometry: ProjectionGeometry, updates: dict
) -> ProjectionGeometry:
    """Return a new geometry with ``updates`` applied.

    Raises ``ValueError`` if the updated geometry is invalid (the dataclass
    validates in ``__post_init__``).
    """
    return replace(geometry, **updates)


def difference_scale(measured, simulated) -> float:
    """Largest ``|measured - simulated|`` over both whole stacks.

    The difference views need one symmetric scale for the same reason the
    projections need one window: otherwise every slice brightens to its own
    maximum and a tiny error looks as loud as a large one. The difference
    stack is never materialized — the pass runs in projection chunks.
    """
    if (
        measured is None
        or simulated is None
        or np.shape(measured) != np.shape(simulated)
    ):
        return 0.0
    scale = 0.0
    for start in range(0, len(measured), 8):
        delta = np.abs(measured[start : start + 8] - simulated[start : start + 8])
        if delta.size:
            scale = max(scale, float(np.max(delta)))
    return scale


def difference_image(delta: np.ndarray, scale: float) -> np.ndarray:
    """Map a signed difference to gray with zero at mid-gray.

    ``scale`` comes from :func:`difference_scale`, so all difference views and
    slices share one brightness mapping; ``scale <= 0`` means no difference at
    all and gives an even mid-gray.
    """
    delta = np.asarray(delta, dtype=np.float32)
    if scale <= 0:
        return np.full(delta.shape, 0.5, dtype=np.float32)
    image = delta / (2.0 * scale) + 0.5
    return np.clip(image, 0.0, 1.0).astype(np.float32)


def comparison_scales(measured, simulated):
    """Return ``(window, difference_scale)`` shared by every comparison view.

    Both rows and both sources draw through ``window``: one detector value,
    one gray level, whatever slider position or view it appears in. The
    difference views get one symmetric ``difference_scale`` with zero pinned
    to mid-gray, so slice-to-slice brightness does not jump either.
    """
    shapes_match = (
        measured is not None
        and simulated is not None
        and np.shape(measured) == np.shape(simulated)
    )
    return (
        stack_window(measured, simulated),
        difference_scale(measured, simulated) if shapes_match else 0.0,
    )


def cached_comparison_scales(measured, simulated):
    """Memoize :func:`comparison_scales` until one of the stacks changes.

    The window is a min/max over both full stacks and the difference scale is
    another full pass; at full projection geometry that is a second of reading
    per call, and every slider tick reruns the script. The stacks themselves
    live in session state, so the shapes plus the sums of two edge projections
    are a cheap, stable identity stamp — a new stack recomputes.
    """
    import streamlit as st

    stamp = tuple(
        (array.shape, float(np.sum(array[0])), float(np.sum(array[-1])))
        for array in (measured, simulated)
        if array is not None and np.size(array)
    )
    cached = st.session_state.get("_sino_display_scales")
    if cached is not None and cached[0] == stamp:
        return cached[1]
    scales = comparison_scales(measured, simulated)
    st.session_state["_sino_display_scales"] = (stamp, scales)
    return scales


def row_sinogram(array: np.ndarray, row_index: int) -> np.ndarray:
    """Return the ``(col, projection)`` sinogram for one detector row.

    Canonical stacks are ``(proj, row, col)``. Fixing a row leaves
    ``(proj, col)``; transposing puts detector columns on the vertical axis and
    projection angles on the horizontal one — the conventional sinogram view.
    """
    return np.asarray(array[:, row_index, :]).T


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

    The label is kept only for screen readers: each slider sits directly
    under the row it indexes, so a visible name would be redundant.
    """
    if n_items <= 1:
        return 0
    resolve_view_index(key, n_items)
    return int(
        container.slider(
            label,
            0,
            n_items - 1,
            key=key,
            label_visibility="collapsed",
        )
    )


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
    """Drop cached widget values so a newly loaded geometry prefills cleanly.

    The scan's projection count belongs to the geometry too, so it is
    re-seeded from ``projections_per_rotation`` instead of keeping a stale
    value from the previous geometry.
    """
    import streamlit as st

    for key in list(st.session_state.keys()):
        if isinstance(key, str) and (
            key.startswith("geo_edit_") or key == SCAN_N_PROJECTIONS_KEY
        ):
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

    from visualization.actions import enqueue_measurements, session_token

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
        # The Sample options in the Forward Projection tab govern the forward
        # projection; to compare shapes against the full load, preset the FP
        # to "all" (📐 Full projection geometry).
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
                    # The geometry and selection are frozen at click time; the
                    # read and its progress run on a worker. Validation above
                    # stays synchronous — it is cheap and belongs to the click.
                    enqueue_measurements(
                        session_token(),
                        path,
                        selection,
                        axis_order,
                        st.session_state.get("projection_geometry"),
                    )
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
            from visualization.actions import enqueue_dummy_measurement

            enqueue_dummy_measurement(session_token())


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

    # Number of projections in the scan. Both the 3D trajectory and the forward
    # projection's projection axis use it; ``Projections / Rotation`` above only
    # says how many views make one turn. One full rotation is the default for a
    # circular scan; the widget key is seeded through session state so a loaded
    # geometry supplies the number instead of a constant.
    if SCAN_N_PROJECTIONS_KEY not in st.session_state:
        st.session_state[SCAN_N_PROJECTIONS_KEY] = int(
            geometry.projections_per_rotation
        )
    st.number_input(
        "Projections",
        min_value=1,
        step=100,
        key=SCAN_N_PROJECTIONS_KEY,
    )
    st.caption(
        "Number of projections in the scan — used by the 3D trajectory and by "
        "the forward projection. The Sample options in the Forward Projection "
        "tab can select a subset."
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


def projection_display_image(array: np.ndarray, window, spacing=None) -> np.ndarray:
    """Return a projection frame as image, through the shared level/window.

    ``window`` is the ``(lo, hi)`` from :func:`stack_window`; it is explicit so
    no view can fall back to normalizing a single frame. ``spacing`` is
    ``(row_spacing_mm, col_spacing_mm)`` from
    :func:`projection_display_spacing`; an anisotropic detector would
    otherwise show a distorted phantom (a 2 mm x 1 mm detector shows the
    head half as tall as it really is).
    """
    image = window_image(array, window)
    if spacing is not None:
        from visualization.app import to_isotropic

        image = to_isotropic(image, spacing)
    return image


# Height (px) of an empty slot in the Sinogram Inspection tab. The three
# views sit in equal thirds of a wide layout, so this roughly squares the
# box off against one column. The point is that an empty slot reserves the
# same vertical space as a filled one, which keeps the row -- and everything
# below it -- from jumping when the first projection arrives.
#
# This is only the fallback: SQUARE_VIEW_CSS squares every slot off for real
# (aspect-ratio 1/1 at the column's rendered width), independent of the
# browser width.
PLACEHOLDER_HEIGHT_PX = 360

# Upper bound (px) for a comparison view. The cap itself comes from the
# projection images (see comparison_view_height); this only stops a very
# large detector from turning one row into a page of its own.
COMPARISON_VIEW_MAX_HEIGHT_PX = 720

# Comparison views (components.html) and their empty-slot placeholders are
# squared off by CSS: aspect-ratio makes every slot as tall as its column is
# wide, independent of the browser width, so the two rows line up and the
# measured sinogram no longer scrolls in an oversized box. The heights
# computed in Python (comparison_view_height, PLACEHOLDER_HEIGHT_PX) are only
# the fallback Streamlit paints before/if the stylesheet applies.
#
# iframe.stIFrame / iframe[title="st.iframe"] is every components.html iframe
# in this app -- the comparison views are the only ones. Scoped so the demo
# banner and the Geometry tab's st.info boxes are untouched.
SQUARE_VIEW_CSS = """
<style>
  iframe.stIFrame, iframe[title="st.iframe"] {
    height: auto !important;
    aspect-ratio: 1 / 1 !important;
  }
  .sino-placeholder {
    width: 100%;
    aspect-ratio: 1 / 1;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    border: 1px dashed rgba(128, 128, 128, 0.5);
    border-radius: 0.5rem;
    color: rgba(128, 128, 128, 0.9);
    padding: 1rem;
    box-sizing: border-box;
  }
</style>
"""

# Zoom range of the comparison viewer, relative to "fit the column width".
VIEW_ZOOM_MAX = 8


def comparison_view_height(*frames) -> int:
    """Return the height (px) of the comparison view boxes.

    The two rows show the same detector in different directions. A row
    sinogram is one detector row as ``(col, projection)``, so it is far
    taller than wide and used to stretch the page by a few thousand pixels at
    column width. Both rows are therefore capped at the largest side of a
    first-row projection frame, so the sinogram row never grows past the
    projection images above it and the boxes line up. Without data the
    placeholder height applies; the result is clamped to
    ``[PLACEHOLDER_HEIGHT_PX, COMPARISON_VIEW_MAX_HEIGHT_PX]``.

    This is the fallback footprint only: SQUARE_VIEW_CSS squares every view
    off at the column's rendered width via ``aspect-ratio``, which overrides
    this height wherever the stylesheet applies.
    """
    sides = [
        max(np.shape(frame)) for frame in frames if frame is not None and np.size(frame)
    ]
    cap = max(sides) if sides else 0
    return int(min(COMPARISON_VIEW_MAX_HEIGHT_PX, max(PLACEHOLDER_HEIGHT_PX, cap)))


def png_data_uri(image: np.ndarray, max_side: int = 2048) -> str:
    """Encode a ``[0, 1]`` image as an inline PNG data URI.

    The long side is downscaled to ``max_side`` first: the comparison views
    are a few hundred pixels on screen and the URI travels with every rerun,
    so shipping the full detector raster as base64 would be waste.
    """
    import base64
    import io

    from PIL import Image

    array = np.clip(np.asarray(image, dtype=np.float32), 0.0, 1.0)
    pixels = (array * 255.0 + 0.5).astype(np.uint8)
    png = Image.fromarray(pixels, mode="L")
    png.thumbnail((max_side, max_side), Image.BILINEAR)
    buffer = io.BytesIO()
    png.save(buffer, format="PNG", optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def build_zoomable_image_html(data_uri: str) -> str:
    """Self-contained viewer: scrolls, and zooms with Ctrl + mouse wheel.

    ``st.image`` fills the column width and offers no zoom, so a tall
    sinogram ("fit width") cannot be inspected without the page growing and
    shrinking. The viewer keeps the full width, scrolls the overflow inside a
    fixed box, and scales the image under the cursor on Ctrl + wheel (a plain
    wheel scrolls, as expected in a scroll box). Double-click resets it. The
    image is centred while it fits and aligns to the start once it overflows,
    so nothing is clipped un-scrollably.
    """
    return f"""
<style>
  html, body {{ margin: 0; padding: 0; height: 100%; background: transparent; overflow: hidden; }}
  html {{ color-scheme: dark; }}
  #box {{ height: 100%; overflow: auto; overscroll-behavior: contain;
         display: flex; flex-direction: column; justify-content: safe center;
         scrollbar-width: thin; scrollbar-color: #4a4a4a transparent; }}
  #box::-webkit-scrollbar {{ width: 10px; height: 10px; }}
  #box::-webkit-scrollbar-track {{ background: rgba(0, 0, 0, 0.35); }}
  #box::-webkit-scrollbar-thumb {{ background: #4a4a4a; border-radius: 5px; }}
  #box::-webkit-scrollbar-thumb:hover {{ background: #666666; }}
  #img {{ display: block; width: 100%; align-self: safe center; }}
</style>
<div id="box"><img id="img" src="{data_uri}" alt=""></div>
<script>
(function () {{
  const box = document.getElementById("box");
  const img = document.getElementById("img");
  const step = 1.15, min = 0.1, max = {VIEW_ZOOM_MAX};
  let zoom = 1.0;
  box.addEventListener("wheel", function (ev) {{
    if (!ev.ctrlKey) return;
    ev.preventDefault();
    const next = Math.min(max, Math.max(min, zoom * (ev.deltaY < 0 ? step : 1 / step)));
    if (next === zoom) return;
    const rect = box.getBoundingClientRect();
    const fx = (ev.clientX - rect.left + box.scrollLeft) / img.offsetWidth;
    const fy = (ev.clientY - rect.top + box.scrollTop) / img.offsetHeight;
    zoom = next;
    img.style.width = zoom * 100 + "%";
    box.scrollLeft = fx * img.offsetWidth - (ev.clientX - rect.left);
    box.scrollTop = fy * img.offsetHeight - (ev.clientY - rect.top);
  }}, {{ passive: false }});
  box.addEventListener("dblclick", function () {{
    zoom = 1.0;
    img.style.width = "100%";
  }});
}})();
</script>
"""


def _render_comparison_view(image: np.ndarray, height: int) -> None:
    """Render one already-normalized image as a capped, zoomable view."""
    from streamlit.components.v1 import html as component_html

    component_html(
        build_zoomable_image_html(png_data_uri(image)),
        height=height,
        scrolling=False,
    )


def _render_placeholder(message: str) -> None:
    """Render an empty slot as a square ``.sino-placeholder`` box.

    A bare ``st.info`` is a one-line strip, which left the three columns
    looking collapsed until data arrived, and a fixed-height container
    cannot match the square image slots around it at an arbitrary browser
    width. The marker class lets SQUARE_VIEW_CSS square the slot off with
    ``aspect-ratio``: it reserves exactly the footprint a filled view has.
    """
    import streamlit as st

    st.markdown(
        f'<div class="sino-placeholder">{message}</div>', unsafe_allow_html=True
    )


def render_comparison_tab() -> None:
    """Sinogram Inspection: measured vs simulated projections side by side.

    The full frame (three columns + shared index slider) always renders;
    each slot fills in as its data arrives. Measured data is shown as soon
    as it is loaded; simulated data appears after a forward projection.
    The controls that produce the simulated data live in the Forward
    Projection tab.
    """
    import streamlit as st

    from visualization.comparison import (
        build_distribution_figure,
        build_metric_figure,
        compute_metrics_per_slice,
    )

    st.subheader("Sinogram Inspection")

    # Square every slot off at the column's rendered width (see
    # SQUARE_VIEW_CSS): the views and the empty placeholders around them
    # share one aspect-ratio, so both rows line up at any browser width.
    st.markdown(SQUARE_VIEW_CSS, unsafe_allow_html=True)

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

    # One level/window for every view and every slice: a detector value maps to
    # the same gray in both rows and in both sources, so the brightness no
    # longer follows the slider and measured vs simulated stays comparable.
    # Same for the difference: one symmetric scale, zero pinned to mid-gray.
    window, diff_scale = cached_comparison_scales(measured, simulated)

    # Both rows are capped at the largest side of a projection frame, so the
    # sinogram row below never grows past the images here and the two rows
    # line up. The views scroll internally; Ctrl + wheel zooms them.
    view_height = comparison_view_height(
        measured[meas_index] if measured is not None else None,
        simulated[sim_index] if simulated is not None else None,
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
            _render_comparison_view(
                projection_display_image(measured[meas_index], window, meas_spacing),
                height=view_height,
            )
        else:
            _render_placeholder(
                "No measured data — load measurements in the sidebar or "
                "generate a dummy measurement.",
            )
    with col_sim:
        if n_sim:
            st.caption(f"Simulated projection {sim_index + 1}/{n_sim}")
            _render_comparison_view(
                projection_display_image(simulated[sim_index], window, sim_spacing),
                height=view_height,
            )
        else:
            _render_placeholder(
                "Run the forward projection to fill this column.",
            )
    with col_diff:
        if shapes_match:
            diff = difference_image(
                measured[meas_index] - simulated[sim_index], diff_scale
            )
            if meas_spacing is not None:
                from visualization.app import to_isotropic

                diff = to_isotropic(diff, meas_spacing)
            # Same structure as the measured/simulated columns: a caption line
            # above, then the image — otherwise the difference image starts
            # one caption-line higher than its neighbours.
            st.caption("Difference (measured − simulated)")
            _render_comparison_view(diff, height=view_height)
        elif n_meas and n_sim:
            _render_placeholder(
                f"Shapes differ ({measured.shape} vs {simulated.shape}) — preset "
                'the projection to "all" (📐 Full projection geometry) to '
                "compare.",
            )
        else:
            _render_placeholder(
                "Difference appears once measured and simulated shapes match.",
            )

    # Shared slider below the views. Renders nothing when there are fewer
    # than two frames on either side (a 0..0 slider is illegal in Streamlit).
    index_slider(st, "Projection index", "sino_shared_index", n_total)

    # --- Second row: row sinogram (rows → cols → projections) ---------------
    # Fix one detector row and show columns against projection angle. The
    # horizontal axis is an angle index, not detector columns, so the
    # detector-spacing resampling used for the projection images above does
    # not apply here.
    n_rows_meas = measured.shape[1] if measured is not None else 0
    n_rows_sim = simulated.shape[1] if simulated is not None else 0
    n_rows_total = max(n_rows_meas, n_rows_sim)

    row = resolve_view_index("sino_row_index", n_rows_total)
    meas_row = min(row, n_rows_meas - 1) if n_rows_meas else 0
    sim_row = min(row, n_rows_sim - 1) if n_rows_sim else 0

    # The sinogram row uses the same box height as the projection row above
    # (view_height): the sinogram is far taller than wide at column width,
    # so it scrolls inside that box instead of stretching the page.
    row_sino_meas, row_sino_sim, row_sino_diff = st.columns(3)
    with row_sino_meas:
        if n_rows_meas:
            label = f"Measured sinogram, row {meas_row + 1}/{n_rows_meas}"
            st.caption(label)
            _render_comparison_view(
                window_image(row_sinogram(measured, meas_row), window),
                height=view_height,
            )
        else:
            _render_placeholder("No measured data for a row sinogram.")
    with row_sino_sim:
        if n_rows_sim:
            label = f"Simulated sinogram, row {sim_row + 1}/{n_rows_sim}"
            st.caption(label)
            _render_comparison_view(
                window_image(row_sinogram(simulated, sim_row), window),
                height=view_height,
            )
        else:
            _render_placeholder("Run the forward projection to fill this row.")
    with row_sino_diff:
        if shapes_match:
            diff = difference_image(
                row_sinogram(measured, meas_row) - row_sinogram(simulated, sim_row),
                diff_scale,
            )
            st.caption("Difference sinogram (measured − simulated)")
            _render_comparison_view(diff, height=view_height)
        elif n_rows_meas and n_rows_sim:
            _render_placeholder("Shapes differ — see the projection row above.")
        else:
            _render_placeholder(
                "Difference sinogram appears once measured and simulated "
                "shapes match.",
            )

    st.caption(
        "Ctrl + mouse wheel zooms a view, double-click resets it. "
        "A view scrolls when it is larger than its box."
    )

    # Own slider for the row, below the second row.
    index_slider(st, "Row index", "sino_row_index", n_rows_total)

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


def render_forward_projection_tab(
    volume, geometry: Optional[ProjectionGeometry]
) -> None:
    """Forward Projection: sampling, beam energy and the run button.

    Kept separate from Sinogram Inspection so that tab stays a pure image
    grid. The widgets still render on every rerun — Streamlit builds all
    tabs — so the measurement loader in the sidebar can keep reading the
    shared ``sample_selection`` stash right after a widget change.
    """
    import streamlit as st

    from backend.forward_project import PARALLELPROJ_AVAILABLE
    from visualization.actions import enqueue_forward_projection, session_token

    st.subheader("Forward Projection")

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
        # The sidebar loads measurements before the tabs render, so the loader
        # cannot instantiate the shared widgets itself — it reads this stash
        # instead. A widget change reruns before any click can happen, so the
        # stash is never stale at click time.
        st.session_state["sample_selection"] = selection
        # One click back to the full detector and every projection of the
        # geometry: the same preset the dummy measurement applies, without
        # having to touch the three dropdowns by hand. The preset runs as an
        # on_click callback because callbacks execute before the script (and
        # thus before these widgets are instantiated) — assigning the
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
            help=(
                "Builds the ray (LOR) geometry on the GPU. The projection "
                "kernel itself is chosen by the installed parallelproj build: "
                "a CUDA build uses the GPU whenever it can see a device, and a "
                "CPU-only build always projects on the CPU."
            ),
        )
        st.caption("A CPU-only parallelproj build always projects on the CPU.")
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
        elif not PARALLELPROJ_AVAILABLE:
            # Hard stop instead of queueing a run that could only produce the
            # warned-about zeros: a projection without parallelproj is never
            # useful, so nothing is started (T-11-04).
            st.error(
                "parallelproj is not installed in this environment — the "
                "forward projection would return zeros, so nothing was "
                "started. Install it via conda-forge (conda install -c "
                "conda-forge parallelproj) and launch the app from the "
                "ct-viewer environment, e.g. via run_app.cmd."
            )
        else:
            # The projection axis is the scan's projection count from the
            # Geometry tab, not one rotation: a helical scan spans several
            # rotations, and "all" must mean all of them.
            n_scan = scan_n_projections(geometry)
            detector_shape = (n_scan, geometry.n_det_rows, geometry.n_det_cols)
            try:
                proj_idx, row_idx, col_idx = resolve_selection(
                    selection, detector_shape
                )
            except (
                Exception
            ) as exc:  # noqa: BLE001 - invalid selection is a click error
                st.error(f"Invalid projection selection: {exc}")
            else:
                # Volume, geometry, selection and energy are frozen here. The
                # projection itself runs on a worker; the poller forces a rerun
                # when the result is ready, which applies it at the top of main.
                enqueue_forward_projection(
                    session_token(),
                    volume,
                    geometry,
                    proj_indices=proj_idx,
                    row_indices=row_idx,
                    col_indices=col_idx,
                    energy_kev=energy_kev,
                    use_cuda=use_cuda,
                    n_projections_total=n_scan,
                )
