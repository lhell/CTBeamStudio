"""Action definitions for the UI queue.

The four long-running user actions are described here: what to run on the
worker thread (``run``) and what to do with the result on the main thread
(``apply``). ``action_queue`` owns ordering and threading; this module owns the
action-specific knowledge.

Rules:

- ``run`` closures are Streamlit-free and read no session state. Every input is
  frozen when the button is clicked, so later widget changes cannot alter a
  queued job.
- ``apply`` functions take the state mapping explicitly (``st.session_state`` in
  production, a dict in tests) and do not call ``st.*`` themselves. The drain
  glue reports the returned message.
- One deliberate seam: ``actions_inline`` in session state runs submissions
  synchronously on the calling thread. Only the integration suite sets it,
  because ``AppTest`` cannot advance a background worker on the same run.
"""

import logging
import time
import uuid
from pathlib import Path
from typing import Callable, MutableMapping, Optional

import streamlit as st

from visualization import action_queue
from visualization.action_queue import (
    STATUS_CANCELLED,
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
    QueueItem,
)

logger = logging.getLogger(__name__)

KIND_SERIES = "series"
KIND_MEASUREMENTS = "measurements"
KIND_DUMMY = "dummy"
KIND_FORWARD_PROJECTION = "forward-projection"

TOAST_QUEUED = "Added to queue"


def session_token() -> str:
    """Return this session's queue key.

    The registry is process-global, so a fixed key would make every browser
    session share one queue. Each session gets its own token, exactly like the
    startup job name.
    """
    import streamlit as st

    token = st.session_state.get("action_queue_token")
    if token is None:
        token = uuid.uuid4().hex
        st.session_state["action_queue_token"] = token
    return token


def inline_mode() -> bool:
    """Whether submissions run on the calling thread (integration-test seam)."""
    import streamlit as st

    return bool(st.session_state.get("actions_inline"))


def series_file_list(selected_series, n_slices=None, data_path=None) -> list:
    """Resolve the file list for one Load Series click.

    Pure and synchronous: a click may not hand an iterator or a live widget
    value to the worker. ``data_path`` is only read when the scanned series
    carries no file list (the old sidebar fallback).
    """
    files = list(getattr(selected_series, "files", ()) or ())
    if not files:
        files = list(Path(data_path).iterdir())
    return files[:n_slices] if n_slices else files


def _progress(session: str, item: QueueItem) -> Callable[[int, int], None]:
    """A thread-safe progress callback bound to one queue item."""

    def report(current: int, total: int) -> None:
        action_queue.set_progress(session, item.id, current, total)

    return report


def _toast(message: str, icon: Optional[str] = None) -> None:
    import streamlit as st

    st.toast(message, icon=icon)


def _submit(session: str, *, kind: str, label: str, make_run, apply) -> str:
    """Build the item, queue it, and return its id.

    ``make_run`` receives the item so progress callbacks can address it before
    the queue has assigned an id.
    """
    item = QueueItem(label=label, run=lambda: None, kind=kind, apply=apply)
    item.run = make_run(item)

    if inline_mode():
        item_id = action_queue.run_now(session, item)
        drain_action_results(session)
        return item_id

    item_id = action_queue.enqueue(session, item)
    _toast(TOAST_QUEUED, icon="⏳")
    return item_id


# --- Load Series -------------------------------------------------------------


def enqueue_series(session: str, files, series) -> str:
    """Queue a DICOM series read.

    ``files`` and ``series`` are snapshotted here; the apply step stores the
    volume and the same series, so the sidebar shows what was actually loaded.
    """
    paths = [str(f) for f in files]
    file_list = list(files)

    def make_run(item):
        def run():
            from visualization.volume_cache import load_volume_cached

            return load_volume_cached(
                paths, _progress_callback=_progress(session, item)
            )

        return run

    return _submit(
        session,
        kind=KIND_SERIES,
        label="Load Series",
        make_run=make_run,
        apply=lambda volume, state: apply_series(
            volume, state, series=series, files=file_list
        ),
    )


def apply_series(
    volume, state: MutableMapping, *, series, files, save_cache=None
) -> str:
    """Store a loaded series, drop stale slice indices, persist the session."""
    if save_cache is None:
        from visualization.volume_cache import save_last_loaded as save_cache

    state["volume"] = volume
    state["series"] = series
    state["loaded_files"] = list(files)
    for key in ("axial_slice", "coronal_slice", "sagittal_slice"):
        state.pop(key, None)

    save_cache(list(files))
    logger.info(
        "Loaded %d slices, shape=%s",
        len(files),
        getattr(getattr(volume, "array", None), "shape", None),
    )
    return f"Loaded {len(files)} slices!"


# --- Load Measurements -------------------------------------------------------


def enqueue_measurements(
    session: str, path, selection, axis_order: str, geometry
) -> str:
    """Queue a measured projection / sinogram read."""
    source = Path(path)

    def make_run(item):
        def run():
            from backend.loaders.sinogram import load_sinogram

            return load_sinogram(
                source,
                selection=selection,
                geometry=geometry,
                axis_order=axis_order,
                progress=_progress(session, item),
            )

        return run

    return _submit(
        session,
        kind=KIND_MEASUREMENTS,
        label="Load Measurements",
        make_run=make_run,
        apply=apply_measurements,
    )


def apply_measurements(sinogram, state: MutableMapping) -> str:
    state["sinogram"] = sinogram
    return "Measurements loaded!"


# --- Dummy measurement -------------------------------------------------------


def enqueue_dummy_measurement(session: str) -> str:
    def make_run(item):
        def run():
            from visualization.phantom import (
                DEMO_SCATTER_SIGMA_MM,
                DEMO_SPR,
                create_dummy_measured_sinogram,
            )

            # Light scatter, like load_demo_volume (T-11-06): the shared
            # demo constants keep both entry points identical.
            return create_dummy_measured_sinogram(
                spr=DEMO_SPR, scatter_sigma_mm=DEMO_SCATTER_SIGMA_MM
            )

        return run

    return _submit(
        session,
        kind=KIND_DUMMY,
        label="Dummy measurement",
        make_run=make_run,
        apply=apply_dummy_measurement,
    )


def apply_dummy_measurement(dummy, state: MutableMapping, clear_edits=None) -> str:
    """Store the coherent demo trio and preset the sample selection to "all"."""
    if clear_edits is None:
        from visualization.projection_panel import clear_geometry_edit_state

        clear_edits = clear_geometry_edit_state

    state["volume"] = dummy.volume
    state["projection_geometry"] = dummy.geometry
    state["geometry_is_default"] = False
    state["geometry_loaded_original"] = dummy.geometry
    state["sinogram"] = dummy.sinogram
    state["sample_proj_mode"] = "all"
    state["sample_row_mode"] = "all"
    state["sample_col_mode"] = "all"
    clear_edits()

    note = (
        "cached projection reused"
        if getattr(dummy, "params", {}).get("fp_from_cache")
        else "projection computed"
    )
    return f"Dummy measurement ready ({note})."


# --- Forward projection ------------------------------------------------------


def enqueue_forward_projection(
    session: str,
    volume,
    geometry,
    *,
    proj_indices,
    row_indices,
    col_indices,
    energy_kev: float,
    use_cuda: bool,
    n_projections_total: Optional[int] = None,
) -> str:
    """Queue a forward projection.

    Indices are resolved by the caller, so an invalid selection is an immediate
    UI error instead of a queued failure. A missing volume is likewise rejected
    before this call (no dependency graph between queue entries).
    """
    proj_idx = list(proj_indices)
    row_idx = list(row_indices)
    col_idx = list(col_indices)

    def make_run(item):
        def run():
            from backend.forward_project import forward_project
            from visualization.projection_panel import prepare_projection_volume

            projection_volume = prepare_projection_volume(volume, energy_kev)
            return forward_project(
                projection_volume,
                geometry,
                row_indices=row_idx,
                col_indices=col_idx,
                proj_indices=proj_idx,
                n_projections_total=n_projections_total,
                use_cuda=use_cuda,
                progress=_progress(session, item),
            )

        return run

    return _submit(
        session,
        kind=KIND_FORWARD_PROJECTION,
        label="Forward Projection",
        make_run=make_run,
        apply=apply_forward_projection,
    )


def apply_forward_projection(result, state: MutableMapping) -> str:
    state["forward_projection"] = result
    n_projections = int(result.projections.shape[0])
    return f"Computed {n_projections} projections."


# --- Main-thread result hand-off --------------------------------------------


def streamlit_notify(level: str, message: str) -> None:
    """Render a drain outcome in the app (must run with a script context)."""
    import streamlit as st

    if level == "error":
        st.error(message)
    else:
        st.toast(message, icon="✅")


def _log_notify(level: str, message: str) -> None:
    """Default for context-free callers (workers are never in this path)."""
    logger.log(logging.ERROR if level == "error" else logging.INFO, "%s", message)


def drain_action_results(
    session: str,
    state: Optional[MutableMapping] = None,
    notify: Optional[Callable[[str, str], None]] = None,
) -> list[QueueItem]:
    """Apply every finished item exactly once, on the main thread.

    Called at the top of ``main()`` so widget-backed keys are written before
    the widgets that own them are created. ``state`` and ``notify`` are
    injectable for tests; the app passes ``st.session_state`` implicitly and
    ``actions.streamlit_notify`` explicitly.
    """
    if state is None:
        import streamlit as st

        state = st.session_state
    if notify is None:
        notify = _log_notify

    drained = action_queue.drain_results(session)
    for item in drained:
        if item.status != action_queue.STATUS_DONE:
            notify("error", f"{item.label} failed: {item.error}")
            continue
        try:
            message = item.apply(item.result, state) if item.apply is not None else None
        except Exception as exc:  # noqa: BLE001 - surfaced to the operator
            logger.exception("Applying %s failed", item.label)
            notify("error", f"{item.label} finished but could not be applied: {exc}")
        else:
            notify("success", message or f"{item.label} finished")
    return drained


# --- Queue UI ----------------------------------------------------------------

_STATUS_ICON = {
    STATUS_PENDING: "⏳",
    STATUS_RUNNING: "⚙️",
    STATUS_DONE: "✅",
    STATUS_FAILED: "❌",
    STATUS_CANCELLED: "🚫",
}


def _elapsed(item: QueueItem, now: float) -> float:
    """Seconds to show for a row; frozen at completion for terminal items."""
    started = item.started_at or item.created_at
    end = item.finished_at if item.status in action_queue.TERMINAL_STATUSES else now
    return max(0.0, end - started)


# The queue renders as a dark gray window: fixed height, internally scrollable,
# so finished items pile up at the top (FIFO) instead of stretching the
# sidebar. Scoped to the sidebar's bordered containers, of which this panel is
# the only one; the light text keeps the rows readable inside the dark box in
# the default light theme.
QUEUE_PANEL_CSS = """
<style>
  [data-testid="stSidebar"] div[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #383b44;
    border: 1px solid #59606f;
    border-radius: 0.5rem;
  }
  [data-testid="stSidebar"] div[data-testid="stVerticalBlockBorderWrapper"] p,
  [data-testid="stSidebar"] div[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stCaptionContainer"] {
    color: #e8eaf0;
  }
</style>
"""

# Window height: grows with the row count up to the cap, then the box scrolls.
QUEUE_PANEL_CAP_PX = 200
QUEUE_PANEL_BASE_PX = 56
QUEUE_PANEL_ROW_PX = 26


def render_action_queue(session: str) -> None:
    """Draw one row per queue entry in a dark gray, scrollable sidebar window.

    Rows keep queue order (FIFO), so finished items drift upward and the
    active ones stay at the bottom; once the rows exceed the capped height the
    window scrolls instead of growing. Only pending rows get a Cancel button:
    a running item is inside a C call and cannot be stopped, so offering a
    button there would be a lie.
    """
    items = action_queue.snapshot(session)
    height = min(
        QUEUE_PANEL_CAP_PX,
        QUEUE_PANEL_BASE_PX + QUEUE_PANEL_ROW_PX * len(items),
    )
    with st.container(height=height, border=True):
        if not items:
            st.caption("No queued actions.")
            return

        now = time.time()
        for item in items:
            parts = [f"{item.label} · {item.status} · {_elapsed(item, now):.0f}s"]
            if item.progress is not None:
                current, total = item.progress
                parts.append(f"{current}/{total}")
                st.progress(current / total if total else 0.0)
            if item.status == STATUS_FAILED and item.error is not None:
                parts.append(str(item.error))
            icon_col, text_col = st.columns([1, 6])
            with icon_col:
                st.caption(_STATUS_ICON.get(item.status, "•"))
            with text_col:
                st.caption(" · ".join(parts))
            if item.status == STATUS_PENDING:
                if st.button("✕ Cancel", key=f"queue_cancel_{item.id}"):
                    action_queue.cancel(session, item.id)
                    st.rerun()

    if st.button("Clear finished", key="queue_clear_finished"):
        action_queue.clear_finished(session)
        st.rerun()


def render_developer_options(session: str) -> None:
    """Sidebar queue window, always visible.

    The dark gray look comes from ``QUEUE_PANEL_CSS``, injected with the panel.
    """
    with st.sidebar:
        st.markdown(QUEUE_PANEL_CSS, unsafe_allow_html=True)
        render_action_queue(session)


@st.fragment(run_every="1s")
def _queue_poller(session: str) -> None:
    """Invisible watcher that forces an app rerun when queue state changes.

    Rendering nothing is deliberate: elements drawn by a fragment linger once
    it stops being mounted, whereas an app-scoped rerun redraws the sidebar
    queue panel with fresh rows. It also applies results that would otherwise
    sit in the registry until the next user interaction.
    """
    signature = (
        tuple(
            (item.id, item.status, item.progress, item.applied)
            for item in action_queue.snapshot(session)
        ),
        action_queue.is_busy(session),
    )
    if signature != st.session_state.get("_action_queue_signature"):
        st.session_state["_action_queue_signature"] = signature
        st.rerun(scope="app")


def mount_queue_poller(session: str) -> None:
    """Mount the watcher while work is active.

    Called at the end of ``main()``: every action button has been evaluated by
    then, so a click on the FP button (which lives in a tab, after the sidebar)
    still starts polling in the very same run.
    """
    if action_queue.is_busy(session):
        _queue_poller(session)
