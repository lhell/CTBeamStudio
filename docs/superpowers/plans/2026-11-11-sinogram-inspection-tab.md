# Sinogram Inspection Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the "Real vs Simulated" tab into "🔍 Sinogram Inspection": an always-rendered 3-column view (Measured | Simulated | Difference) with a shared projection-index slider, plus per-slice and distribution metric plots — fixing the length-1 slider crash and the "loaded but never shown" measured data.

**Architecture:** One pure helper in `comparison.py` computes per-slice metric series and builds the two Plotly figures; `projection_panel.py` renders the new layout (always-drawn frame, progressive fill) plus a length-safe slider helper that never renders `min == max` sliders; `app.py` only changes the tab label.

**Tech Stack:** Streamlit 1.39 (AppTest for smoke tests), Plotly `graph_objects` (already used in `volume3d.py`), NumPy, pytest.

**Spec:** Approved in-chat design (this session, Nov 11 2026): tab renamed to `🔍 Sinogram Inspection`; the empty layout (3-column frame with in-slot hints) always renders; measured projections are visible immediately after loading, independent of volume/geometry/forward projection; simulated projections appear after "Run Forward Projection"; the three views sit next to each other in 3 columns; one shared "Projection index" slider below the views drives all three, each side clamped to its own last index, length-1 data renders no slider; when measured and simulated shapes match, a per-slice metric plot and a distribution plot render side by side below the slices plus the current slice's values; shape mismatch → difference and plots are omitted with a one-line hint in those slots.

## Global Constraints

- Tab label: `🔍 Sinogram Inspection` (exact string, in `src/visualization/app.py` line 657 and `tests/integration/test_ui_smoke.py` `TAB_LABELS`).
- Metric keys: `mae`, `rmse`, `correlation`, `ssim`; display names: `MAE`, `RMSE`, `Correlation`, `SSIM`.
- No slider may ever be rendered with `min_value == max_value` (Streamlit 1.39 raises `StreamlitAPIException`); length-1 axes render no slider.
- Pure helpers (`compute_metrics_per_slice`, `build_metric_figure`, `build_distribution_figure`, `resolve_view_index`, `index_slider`) stay importable without Streamlit side effects; `index_slider` imports `streamlit` inside the function like the module's other render helpers.
- Unit tests must not require a Streamlit script-run context (bare-mode `st.session_state` use is okay, as the existing `test_clamp_index_state_*` tests show); full rendering is covered by AppTest in the smoke test.
- Hint copy (test-pinned): measured slot empty → contains "measured data"; simulated slot empty → contains "run the forward projection"; mismatch slot → contains "shapes differ"; filled slots get captions `Measured projection {i+1}/{n}` / `Simulated projection {i+1}/{n}`. Top status captions keep the exact format `Measured: {shape} · axis order … · format …` and `Simulated: {shape} · … projections`.
- Session-state keys stay compatible: `sinogram`, `forward_projection`, sidebar `meas_*` and `fp_*` widget keys are unchanged; the new shared slider key is `sino_shared_index`; the old `meas_preview_index` key is dropped.
- English UI copy throughout. Commits follow the repo's conventional-commit style (`feat(scope): …`).

## Review Focus

(Inputs and failure modes the spec implies but no listed test may cover; each pinned to its owning task.)

1. Length-1 measured data with no volume — the original user crash (`slider(0, 0)` via the old preview branch) → pinned in Task 5, `test_sinogram_inspection_crash_regression_no_volume`.
2. Length-1 measured data with volume present (normal path, no crash but previously invisible) → pinned in Task 5, `test_sinogram_inspection_renders_single_projection`.
3. Shared slider index exceeding the smaller side's count (measured pinned at its last frame) → pinned in Task 5, `test_sinogram_inspection_shape_mismatch_hints` (measured shows 1/1 while slider spans the simulated side) and Task 3 unit tests for the guards.
4. Shape-mismatch path must keep both image columns and not raise → pinned in Task 5, `test_sinogram_inspection_shape_mismatch_hints`.
5. Empty state keeps the old "measured data" mention so the existing missing-inputs test stays green → pinned in Task 5, run of `test_comparison_tab_lists_missing_inputs` in the verification step.
6. Zero-length axis (`n_items == 0`) must not touch session state or render → pinned in Task 3, `test_resolve_view_index_non_positive_returns_zero` / `test_index_slider_non_positive_renders_nothing`.

---

### Task 1: Plan checkpoint (review gate)

**Files:** none.

**Interfaces:**
- Consumes: this plan + the approved in-chat design (Spec above).
- Produces: user approval and execution-method choice.

- [ ] **Step 1: Present plan + execution options to the user; wait for approval before any implementation**

No code changes. Output: link to the plan file, review request, execution-method question (subagent-driven vs native). Implementation may not start before approval. Commit the plan file with the first implementation commit.

### Task 2: Per-slice metric series helper (pure)

**Files:**
- Modify: `src/visualization/comparison.py` (append after `compute_metrics`)
- Test: `tests/unit/test_comparison.py` (append)

**Interfaces:**
- Consumes: existing `compute_metrics(real, simulated) -> Dict[str, float]` (per 2D frame), existing `difference_image`.
- Produces: `compute_metrics_per_slice(measured: np.ndarray, simulated: np.ndarray) -> Dict[str, np.ndarray]` — canonical `(n_proj, rows, cols)` float-castable arrays in, `{"mae", "rmse", "correlation", "ssim"}` → float64 arrays of shape `(n_proj,)` out. Raises `ValueError` (message containing "shape") on shape mismatch.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_comparison.py`, and add `compute_metrics_per_slice` to the import block:

```python
def test_per_slice_matches_frame_metrics():
    measured = np.random.default_rng(42).normal(size=(3, 5, 7))
    simulated = measured + 0.1

    per_slice = compute_metrics_per_slice(measured, simulated)

    assert set(per_slice) == {"mae", "rmse", "correlation", "ssim"}
    for values in per_slice.values():
        assert values.shape == (3,)
    for i in range(3):
        frame = compute_metrics(measured[i], simulated[i])
        for key, value in frame.items():
            assert per_slice[key][i] == pytest.approx(value)


def test_per_slice_raises_shape_mismatch():
    with pytest.raises(ValueError, match="shape"):
        compute_metrics_per_slice(np.zeros((2, 4, 4)), np.zeros((3, 4, 4)))


def test_per_slice_single_projection():
    per_slice = compute_metrics_per_slice(np.ones((1, 4, 4)), np.ones((1, 4, 4)))

    assert per_slice["mae"].shape == (1,)
    assert per_slice["mae"][0] == pytest.approx(0.0)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/unit/test_comparison.py -v`
Expected: collection FAIL — `ImportError: cannot import name 'compute_metrics_per_slice'`

- [ ] **Step 3: Implement `compute_metrics_per_slice` in `src/visualization/comparison.py`**

Shape-check first (message containing "same shape", mirroring `compute_metrics`), then a list comprehension calling `compute_metrics(measured[i], simulated[i])` per frame; return each key as `np.asarray([...], dtype=np.float64)`.

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/unit/test_comparison.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add src/visualization/comparison.py tests/unit/test_comparison.py
git commit -m "feat(comparison): per-slice metric series helper"
```

### Task 3: Index resolver + length-safe slider helper

**Files:**
- Modify: `src/visualization/projection_panel.py` (append after `clamp_index_state`, ~line 184, above the Streamlit rendering section divider)
- Test: `tests/unit/test_projection_panel.py` (append)

**Interfaces:**
- Consumes: existing `clamp_index_state(key, max_index)`.
- Produces (used by Task 5):
  - `resolve_view_index(key: str, n_items: int) -> int` — `n_items <= 0` → `0` without touching `st.session_state`; else clamp `st.session_state[key]` into `[0, n_items - 1]` via `clamp_index_state` and return it.
  - `index_slider(container, label: str, key: str, n_items: int) -> int` — `n_items <= 1` → `0`, rendering nothing; `n_items >= 2` → `resolve_view_index(key, n_items)` then `int(container.slider(label, 0, n_items - 1, key=key))`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_projection_panel.py`, adding `index_slider, resolve_view_index` to the import block:

```python
def test_resolve_view_index_clamps_within_range():
    import streamlit as st

    st.session_state["view_index"] = 99
    assert resolve_view_index("view_index", 5) == 4
    assert st.session_state["view_index"] == 4


def test_resolve_view_index_single_item_returns_zero():
    import streamlit as st

    st.session_state.pop("view_index_single", None)
    assert resolve_view_index("view_index_single", 1) == 0
    assert st.session_state["view_index_single"] == 0


def test_resolve_view_index_non_positive_returns_zero():
    import streamlit as st

    st.session_state.pop("view_index_empty", None)
    assert resolve_view_index("view_index_empty", 0) == 0
    assert "view_index_empty" not in st.session_state


def test_index_slider_single_item_renders_nothing():
    import streamlit as st

    assert index_slider(st, "Projection index", "idx_single", 1) == 0


def test_index_slider_non_positive_renders_nothing():
    import streamlit as st

    assert index_slider(st, "Projection index", "idx_zero", 0) == 0
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/unit/test_projection_panel.py -v`
Expected: collection FAIL — `ImportError: cannot import name 'resolve_view_index'`

- [ ] **Step 3: Implement both helpers in `src/visualization/projection_panel.py`**

Import `streamlit as st` inside each function body (module pattern: helpers importable without Streamlit). `resolve_view_index`: guard `n_items <= 0` first, return 0 without state access; otherwise `clamp_index_state(key, n_items - 1)` and return `int(st.session_state[key])`. `index_slider`: `if n_items >= 2:` resolve then slider; else `return 0`.

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/unit/test_projection_panel.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add src/visualization/projection_panel.py tests/unit/test_projection_panel.py
git commit -m "feat(panel): view-index resolver and length-safe index slider"
```

### Task 4: Per-slice + distribution Plotly figure builders (pure)

**Files:**
- Modify: `src/visualization/comparison.py` (append)
- Test: `tests/unit/test_comparison.py` (append)

**Interfaces:**
- Consumes: `compute_metrics_per_slice` (Task 2) output shape; `plotly.graph_objects` (import as `go` at module top, matching `volume3d.py`).
- Produces (used by Task 5):
  - `build_metric_figure(per_slice: Dict[str, np.ndarray], current_index: int, proj_indices: Optional[Sequence[int]] = None) -> "plotly.graph_objects.Figure"` — one `go.Scatter` line trace per metric **present in `per_slice`**, in canonical order (`mae`, `rmse`, `correlation`, `ssim`), named `MAE`, `RMSE`, `Correlation`, `SSIM`; MAE/RMSE on y-axis "y", Correlation/SSIM on "y2"; x = `proj_indices` values if given else `0..n-1`; a single vertical line shape at the current slice's x position; returns the Figure.
  - `build_distribution_figure(per_slice: Dict[str, np.ndarray]) -> "plotly.graph_objects.Figure"` — one `go.Histogram` trace per present metric (same canonical order/names), `histnorm="probability density"`, layout `barmode="overlay"`, trace `opacity=0.6`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_comparison.py`, adding `build_distribution_figure, build_metric_figure` to the import block:

```python
def test_build_metric_figure_traces_and_marker():
    per_slice = compute_metrics_per_slice(np.zeros((4, 6, 6)), np.zeros((4, 6, 6)))
    per_slice["mae"] = np.array([0.0, 1.0, 2.0, 3.0])

    fig = build_metric_figure(per_slice, current_index=2)

    assert [t.name for t in fig.data] == ["MAE", "RMSE", "Correlation", "SSIM"]
    np.testing.assert_array_equal(fig.data[0].x, [0, 1, 2, 3])
    np.testing.assert_array_equal(fig.data[0].y, [0.0, 1.0, 2.0, 3.0])
    assert len(fig.layout.shapes) == 1
    assert fig.layout.shapes[0].x0 == 2


def test_build_metric_figure_accepts_proj_indices():
    per_slice = {"mae": np.arange(3.0)}

    fig = build_metric_figure(per_slice, current_index=0, proj_indices=[10, 40, 220])

    assert [t.name for t in fig.data] == ["MAE"]
    assert list(fig.data[0].x) == [10, 40, 220]
    assert fig.layout.shapes[0].x0 == 10


def test_build_distribution_figure_histograms_overlay():
    values = {k: np.linspace(0.0, 1.0, 12) for k in ("mae", "rmse", "correlation", "ssim")}

    fig = build_distribution_figure(values)

    assert [t.type for t in fig.data] == ["histogram"] * 4
    assert [t.name for t in fig.data] == ["MAE", "RMSE", "Correlation", "SSIM"]
    assert fig.layout.barmode == "overlay"
    assert all(t.opacity == 0.6 for t in fig.data)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/unit/test_comparison.py -v`
Expected: collection FAIL — `ImportError: cannot import name 'build_metric_figure'`

- [ ] **Step 3: Implement both builders in `src/visualization/comparison.py`**

Shared order table: `_METRIC_ORDER = (("mae", "MAE"), ("rmse", "RMSE"), ("correlation", "Correlation"), ("ssim", "SSIM"))`; iterate `if key in per_slice`, so partial dicts still render. Marker x-position algorithm (choose one): `x_values = proj_indices if proj_indices is not None else list(range(n))`; `ci = min(current_index, len(x_values) - 1)`; `marker_x = x_values[ci]`. Vertical line via `fig.add_shape(type="line", x0=marker_x, x1=marker_x, y0=0, y1=1, yref="paper")`. Right axis: assign `yaxis="y2"` to Correlation/SSIM traces and `fig.layout.yaxis2 = {"overlaying": "y", "side": "right"}`. Axis titles and hover polish left to the implementer following `volume3d.py` styling patterns.

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/unit/test_comparison.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add src/visualization/comparison.py tests/unit/test_comparison.py
git commit -m "feat(comparison): per-slice and distribution plotly figure builders"
```

### Task 5: Sinogram Inspection tab — rewrite, rename, regression tests

**Files:**
- Modify: `src/visualization/projection_panel.py:469-636` (replace `render_comparison_tab` wholesale; update its docstring)
- Modify: `src/visualization/app.py:657` (tab label)
- Modify: `tests/integration/test_ui_smoke.py` (TAB_LABELS + new tests)

**Interfaces:**
- Consumes: `resolve_view_index`, `index_slider` (Task 3); `compute_metrics_per_slice`, `build_metric_figure`, `build_distribution_figure` (Tasks 2/4); existing `normalize_difference`, `normalize_projection`, `_render_projection_image`, `render_selection_controls`, `resolve_selection`, `prepare_projection_volume`, `forward_project`, `PARALLELPROJ_AVAILABLE`, `clamp_index_state`, `format_axis_order`; session state `sinogram`, `forward_projection`, widget keys `fp_*`, new key `sino_shared_index`.
- Produces: new tab behavior (spec above).

- [ ] **Step 1: Write the failing tests**

In `tests/integration/test_ui_smoke.py`:

(a) Update `TAB_LABELS` to `["🩻 Viewer", "📐 Geometry", "🔍 Sinogram Inspection"]`.

(b) Extend imports: `from backend.forward_project import ForwardProjectionResult`, `from backend.geometry import ProjectionGeometry`, `from backend.loaders.sinogram import SelectionConfig, SinogramData` (pytest already imported).

(c) Append helpers and tests (they reuse the module-scoped `app` fixture and the existing `_walk` helper; each test seeds the state it needs):

```python
def _seed_measurements(at, shape, fmt="numpy"):
    rng = np.random.default_rng(7)
    data = rng.random(shape, dtype=np.float32)
    at.session_state["sinogram"] = SinogramData(
        data=data,
        geometry=None,
        selection=SelectionConfig(),
        original_shape=tuple(shape),
        source_axis_order=("proj", "row", "col"),
        path=None,
        format=fmt,
    )
    return data


def _main_text(at) -> str:
    """Concatenate every caption/info/warning string rendered in main."""
    return " ".join(
        [c.value for c in at.caption]
        + [i.value for i in at.info]
        + [w.value for w in at.warning]
    )


def test_sinogram_inspection_renders_single_projection(app):
    """The user's exact case: measurements (1, 736, 64) must be visible with
    a volume loaded, before any forward projection runs."""
    _seed_measurements(app, shape=(1, 736, 64))

    app.run()

    assert list(app.exception) == []
    text = _main_text(app)
    assert "Measured: (1, 736, 64)" in text
    assert "Measured projection 1/1" in text


def test_sinogram_inspection_crash_regression_no_volume(app):
    """Regression: with no volume, the old preview branch rendered a
    0..0 slider for a 1-projection sinogram and raised
    StreamlitAPIException ('min_value must be less than max_value')."""
    app.session_state.pop("volume", None)
    _seed_measurements(app, shape=(1, 736, 64))

    app.run()

    assert list(app.exception) == []
    text = _main_text(app)
    assert "Measured projection 1/1" in text
    assert "run the forward projection" in text.lower()


def test_sinogram_inspection_shape_mismatch_hints(app):
    """Shapes differ → both image columns stay visible, difference and
    metric plots are omitted with an in-slot hint, no exception."""
    app.session_state["volume"] = create_demo_volume()
    _seed_measurements(app, shape=(1, 736, 64))
    app.session_state["forward_projection"] = ForwardProjectionResult(
        projections=np.zeros((2, 3, 4), dtype=np.float32),
        geometry=ProjectionGeometry(),
        row_indices=[0, 1],
        col_indices=[0, 1, 2],
        proj_indices=[0, 1],
    )

    app.run()

    assert list(app.exception) == []
    text = _main_text(app)
    assert "shapes differ" in text.lower()
    assert "Measured projection 1/1" in text
    assert "Simulated: (2, 3, 4)" in text


def test_sinogram_inspection_empty_frame_hints(app):
    """Nothing loaded → the frame renders with hints, not a dead end."""
    app.session_state.pop("sinogram", None)
    app.session_state.pop("forward_projection", None)
    app.session_state["volume"] = create_demo_volume()

    app.run()

    assert list(app.exception) == []
    hints = _main_text(app).lower()
    assert "measured data" in hints
    assert "run the forward projection" in hints


def test_sinogram_inspection_run_button_produces_simulation(app):
    """Placeholder backend: with a matching measured shape (fp defaults
    proj/row/col step 100/4/8 on the default 2304x64x512 geometry →
    (24, 16, 64)), clicking Run fills the simulated column and the metric
    plots, without exception."""
    app.session_state["volume"] = create_demo_volume()
    _seed_measurements(app, shape=(24, 16, 64))

    app.button(key="fp_run").click()
    app.run()

    assert list(app.exception) == []
    text = _main_text(app)
    assert "Simulated: (24, 16, 64)" in text
    assert "Simulated projection" in text
```

Note on fixture state: these tests run after `test_load_measurements_from_npy`, which leaves a `(4, 6, 8)` sinogram in state — each test here re-seeds or pops what it asserts on, and the established file pattern (shared module app, mutations per test) is preserved. `test_comparison_tab_lists_missing_inputs` (existing) must stay green because the empty measured hint contains "measured data".

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/integration/test_ui_smoke.py -v -k "sinogram_inspection or three_tabs"`
Expected: FAIL — `test_three_tabs_are_rendered_in_order` (old label), `test_sinogram_inspection_renders_single_projection` (no "Measured projection 1/1" caption yet), and the others fail for missing captions/hints; `test_sinogram_inspection_crash_regression_no_volume` fails with a non-empty `app.exception` containing `StreamlitAPIException` (the reproduced bug).

- [ ] **Step 3: Implement the new `render_comparison_tab` in `src/visualization/projection_panel.py`**

Replace lines 469–636 wholesale. Structure (ordering matters for the test-pinned copy):

1. `st.subheader("Sinogram Inspection")`.
2. `sinogram = st.session_state.get("sinogram")`; `measured = sinogram.data if sinogram is not None and sinogram.data is not None else (sinogram.materialize() if sinogram is not None else None)`. Status captions: if measured is not None → `st.caption(f"Measured: {measured.shape} · axis order {format_axis_order(sinogram.axis_order)} · format {sinogram.format}")`.
3. Run controls, always rendered: `with st.expander("Forward projection settings", expanded=True):` the selection controls (`render_selection_controls("fp", ...)` unchanged with its `fp_*` keys and defaults), CUDA checkbox (`fp_use_cuda`), energy slider (`fp_energy_kev`), with captions as before; then the `PARALLELPROJ_AVAILABLE` warning, then `if st.button("Run Forward Projection", type="primary", key="fp_run"):` — on click, `if volume is None: st.error("Load a volume in the sidebar first.")` else the existing try-block (resolve selection → `prepare_projection_volume` → `forward_project`) storing `st.session_state["forward_projection"]` and `st.success(f"Computed {result.projections.shape[0]} projections.")`.
4. `result = st.session_state.get("forward_projection")`; if present, `st.caption(f"Simulated: {simulated.shape} · {len(result.proj_indices)} projections")` where `simulated = result.projections`.
5. Counts: `n_meas = measured.shape[0] if measured is not None else 0`; `n_sim = simulated.shape[0] if result is not None else 0`. The shared slider renders **after** the columns block (design: slider below the slices): `shared = index_slider(st, "Projection index", "sino_shared_index", max(n_meas, n_sim))` — `index_slider` renders nothing when both counts are ≤ 1 and internally clamps the session value via `resolve_view_index`, so a stale larger index can never hit a rerun with a smaller range. Per-side index: `meas_index = min(shared, n_meas - 1) if n_meas else 0`; `sim_index = min(shared, n_sim - 1) if n_sim else 0` — each side pins to its own last frame when the shared index exceeds its count.
6. Three columns `col_meas, col_sim, col_diff = st.columns(3)`:
   - Measured: if `n_meas` → caption `f"Measured projection {meas_index + 1}/{n_meas}"` + `_render_projection_image(measured[meas_index], ...)`; else `st.info("No measured data loaded — load measurements in the sidebar.")` (contains "measured data").
   - Simulated: if `n_sim` → caption `f"Simulated projection {sim_index + 1}/{n_sim}"` + `_render_projection_image(simulated[sim_index], ...)`; else `st.info("Run the forward projection to fill this column.")` (contains "run the forward projection").
   - Difference: if `n_meas and n_sim and measured.shape == simulated.shape` → `st.image(normalize_difference(measured[meas_index] - simulated[sim_index]), caption="Difference (measured − simulated)", clamp=True, use_column_width=True)`; elif `n_meas and n_sim` (mismatch) → `st.info(f"Shapes differ ({measured.shape} vs {simulated.shape}) — load a matching selection to compare.")`; else `st.info("Difference appears once measured and simulated shapes match.")`.
7. Metrics row, only when both exist and shapes match: `per_slice = compute_metrics_per_slice(measured, simulated)`; left/right captions `st.caption("Metrics per slice")` / `st.caption("Distribution over projections")` inside the two `st.columns(2)` cells with `st.plotly_chart(build_metric_figure(per_slice, current_index=shared, proj_indices=result.proj_indices), use_container_width=True)` and `st.plotly_chart(build_distribution_figure(per_slice), use_container_width=True)`; plus a current-slice caption `st.caption(f"Slice {shared + 1}: MAE {…:.4g} · RMSE {…:.4g} · Correlation {per_slice['correlation'][shared]:.4f} · SSIM {per_slice['ssim'][shared]:.4f}")`.
8. Drop the old empty-state `return`-early block, the `meas_preview_index` slider, the `fp_sim_only_index` / `fp_compare_index` sliders, the metric tiles, and the "Metrics over all selected projections" expander.

- [ ] **Step 4: Rename the tab label in `src/visualization/app.py:657`**

`["🩻 Viewer", "📐 Geometry", "🔍 Sinogram Inspection"]`

- [ ] **Step 5: Run to verify pass**

Run: `python -m pytest tests/integration/test_ui_smoke.py tests/unit/test_comparison.py tests/unit/test_projection_panel.py -v`
Expected: PASS (all). If stale widget keys from earlier runs cause `StreamlitAPIException` about session-state/widget mismatches under AppTest, pop them in the affected test before `app.run()` (e.g. `app.session_state.pop("meas_preview_index", None)`).

- [ ] **Step 6: Full suite + lint**

Run: `python -m pytest -x -q`
Expected: PASS. Then, if ruff is installed, `ruff check src tests` (repo convention per LINTING.md); fix findings in the touched files and re-run pytest.

- [ ] **Step 7: Commit (include the plan file)**

```bash
git add src/visualization/projection_panel.py src/visualization/app.py tests/integration/test_ui_smoke.py docs/superpowers/plans/2026-11-11-sinogram-inspection-tab.md
git commit -m "feat(ui): Sinogram Inspection tab with 3-column views, shared slider, per-slice metric plots"
```

### Task 6: Final verification

**Files:** none.

**Interfaces:** none — consumes the finished branch.

- [ ] **Step 1: Confirm clean worktree**

Run: `git status --porcelain`
Expected: empty.

- [ ] **Step 2: Final full verification run**

Run: `python -m pytest -x -q`
Expected: all pass. Report the exact result to the user; the original bug report ("Loaded measurements (1, 736, 64). not shown in real vs simulated tab") is closed only if `test_sinogram_inspection_renders_single_projection` and `test_sinogram_inspection_crash_regression_no_volume` are green.
