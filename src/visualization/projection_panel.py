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
    mode = container.selectbox(
        f"{label} selection",
        SELECTION_MODES,
        index=SELECTION_MODES.index(default_mode),
        key=f"{prefix}_mode",
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


def render_measurement_sidebar() -> None:
    """Sidebar section for loading measured projection / sinogram data."""
    import streamlit as st

    from backend.loaders.sinogram import load_sinogram

    with st.sidebar.expander("Measurements", expanded=True):
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
        selection = render_selection_controls("meas", container=st)

        if st.session_state.get("sinogram") is not None:
            sinogram = st.session_state["sinogram"]
            shape = (
                sinogram.data.shape
                if sinogram.data is not None
                else sinogram.original_shape
            )
            st.caption(f"Loaded: {shape} ({sinogram.format})")

        if not st.button("Load Measurements", key="load_measurements"):
            return
        if not path_str:
            st.warning("Enter a file or folder path first.")
            return

        path = Path(path_str)
        if not path.exists():
            st.error(f"Path not found: {path}")
            return

        try:
            with st.spinner("Loading measurements..."):
                sinogram = load_sinogram(
                    path,
                    selection=selection,
                    geometry=st.session_state.get("projection_geometry"),
                    axis_order=axis_order,
                )
        except Exception as exc:  # noqa: BLE001 - surface loader errors in the UI
            st.error(f"Failed to load measurements: {exc}")
            return

        st.session_state["sinogram"] = sinogram
        shape = (
            sinogram.data.shape
            if sinogram.data is not None
            else sinogram.original_shape
        )
        st.success(f"Loaded measurements {shape}.")
        st.toast("Measurements loaded!", icon="✅")


def render_geometry_tab(geometry: Optional[ProjectionGeometry]) -> None:
    """Show the loaded geometry and let the user edit its parameters."""
    import streamlit as st

    st.subheader("Projection Geometry")
    if geometry is None:
        st.info(
            "Load a geometry file (.txt or .yaml) in the sidebar to view and "
            "edit its parameters."
        )
        return

    if st.session_state.get("geometry_is_default"):
        st.caption(
            "No geometry file loaded — showing the default geometry. "
            "Upload a .txt or .yaml file in the sidebar to replace it."
        )

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Fan angle", f"{geometry.fan_angle:.2f}°")
    col_b.metric("Cone angle", f"{geometry.cone_angle:.2f}°")
    col_c.metric("Collimation", f"{geometry.collimation_width:.1f} mm")
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
            clear_geometry_edit_state()
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


def _render_projection_image(array: np.ndarray, caption: str) -> None:
    import streamlit as st

    st.image(
        normalize_projection(array),
        caption=caption,
        clamp=True,
        use_column_width=True,
    )


def render_comparison_tab(volume, geometry: Optional[ProjectionGeometry]) -> None:
    """Run forward projection and compare it with the measured data."""
    import streamlit as st

    from backend.forward_project import PARALLELPROJ_AVAILABLE, forward_project
    from visualization.comparison import compute_metrics

    st.subheader("Real vs Simulated")
    sinogram = st.session_state.get("sinogram")

    if volume is None or geometry is None or sinogram is None:
        missing = []
        if volume is None:
            missing.append("a volume")
        if geometry is None:
            missing.append("a geometry file")
        if sinogram is None:
            missing.append("measured data")
        st.info("Load " + ", ".join(missing) + " to run the comparison.")
        if sinogram is not None:
            data = sinogram.data
            if data is not None and data.shape[0] > 0:
                clamp_index_state("meas_preview_index", data.shape[0] - 1)
                index = st.slider(
                    "Measured projection",
                    0,
                    data.shape[0] - 1,
                    key="meas_preview_index",
                )
                _render_projection_image(
                    data[index], f"Measured projection {index + 1}/{data.shape[0]}"
                )
        return

    measured = sinogram.data
    if measured is None:
        measured = sinogram.materialize()
    st.caption(
        f"Measured: {measured.shape} · axis order "
        f"{format_axis_order(sinogram.axis_order)} · format {sinogram.format}"
    )

    with st.expander("Forward projection settings", expanded=True):
        selection = render_selection_controls(
            "fp",
            container=st,
            default_proj_mode="downsample",
            default_proj_step=100,
            default_row_mode="downsample",
            default_row_step=4,
            default_col_mode="downsample",
            default_col_step=8,
        )
        use_cuda = st.checkbox("Use CUDA if available", value=True, key="fp_use_cuda")
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
        detector_shape = (
            geometry.projections_per_rotation,
            geometry.n_det_rows,
            geometry.n_det_cols,
        )
        try:
            proj_idx, row_idx, col_idx = resolve_selection(selection, detector_shape)
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
        except Exception as exc:  # noqa: BLE001 - surface backend errors in the UI
            st.error(f"Forward projection failed: {exc}")
        else:
            st.session_state["forward_projection"] = result
            st.success(f"Computed {result.projections.shape[0]} projections.")

    result = st.session_state.get("forward_projection")
    if result is None:
        return

    simulated = result.projections
    st.caption(f"Simulated: {simulated.shape} · {len(result.proj_indices)} projections")

    if simulated.shape != measured.shape:
        st.warning(
            "Measured and simulated shapes differ "
            f"({measured.shape} vs {simulated.shape}). Load the measurements "
            "with the same projection/row/column selection for a comparison. "
            "Showing the simulated data only."
        )
        clamp_index_state("fp_sim_only_index", simulated.shape[0] - 1)
        index = st.slider(
            "Simulated projection",
            0,
            simulated.shape[0] - 1,
            key="fp_sim_only_index",
        )
        _render_projection_image(
            simulated[index],
            f"Simulated projection {index + 1}/{simulated.shape[0]}",
        )
        return

    clamp_index_state("fp_compare_index", simulated.shape[0] - 1)
    index = st.slider(
        "Projection index",
        0,
        simulated.shape[0] - 1,
        key="fp_compare_index",
    )
    real_image = measured[index]
    sim_image = simulated[index]

    col_real, col_sim, col_diff = st.columns(3)
    with col_real:
        _render_projection_image(real_image, "Real")
    with col_sim:
        _render_projection_image(sim_image, "Simulated")
    with col_diff:
        st.image(
            normalize_difference(real_image - sim_image),
            caption="Difference (real − simulated)",
            clamp=True,
            use_column_width=True,
        )

    metrics = compute_metrics(real_image, sim_image)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("MAE", f"{metrics['mae']:.4g}")
    m2.metric("RMSE", f"{metrics['rmse']:.4g}")
    m3.metric("Correlation", f"{metrics['correlation']:.4f}")
    m4.metric("SSIM", f"{metrics['ssim']:.4f}")

    with st.expander("Metrics over all selected projections"):
        overall = compute_metrics(measured, simulated)
        o1, o2, o3, o4 = st.columns(4)
        o1.metric("MAE", f"{overall['mae']:.4g}")
        o2.metric("RMSE", f"{overall['rmse']:.4g}")
        o3.metric("Correlation", f"{overall['correlation']:.4f}")
        o4.metric("SSIM", f"{overall['ssim']:.4f}")
