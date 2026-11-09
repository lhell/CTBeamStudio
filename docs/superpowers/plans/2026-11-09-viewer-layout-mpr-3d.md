# Viewer Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the 3D view the majority of the Viewer tab by stacking the three MPR planes small in a left column, and make both option panels float so opening them never displaces a view.

**Architecture:** Confined to `render_viewer_tab()` in `src/visualization/app.py`. Two Streamlit columns `[1, 4]`, a fixed-height `st.container` for the MPR stack, and `st.popover` replacing both option expanders. One shared height constant aligns the columns.

**Tech Stack:** Python 3.11, Streamlit 1.37–1.39 (pinned), Plotly 7.1, pytest + `streamlit.testing.v1.AppTest`.

**Spec:** `docs/superpowers/specs/2026-11-09-viewer-layout-design.md` — the plan implements §3 (Decisions) and §4 (Architecture); read both together. §3.4 holds the column-ratio derivation and §3.5 the dependency floor.
---

## Status: Re-verified 2026-11-09 against commit `c4ad84e`

- The Viewer tab is still `render_viewer_tab()` in `src/visualization/app.py` (lines 109–473). Do **not** move it. `src/visualization/views/` is a broken stub from `f9220ea` whose `__init__.py` imports two modules that do not exist; leave it alone.
- PyVista is shelved (plan.md T-82): `render_mode` offers only `["iso"]`, and the PyVista branch is gone.
- "Show Trajectory" no longer exists; the trajectory draws whenever a geometry is loaded.
- The working tree is clean apart from these docs, so there is a clean base to diff against.

## Global Constraints

- Scope is `render_viewer_tab()` plus `pyproject.toml`. Nothing else.
- No changes to `volume3d.py`, `mpr.py`, `windowing.py`, `display_units.py`, `sidebar.py`, `background_load.py`, `projection_panel.py`, any loader, or any geometry code.
- No change to `main()`, `render_startup_status()`, `render_empty_state()`, or `STARTUP_FAILURE_MESSAGE`.
- Every control keeps its label, `key`, default, and conditional visibility. This is a re-layout, not a redesign.
- `clamp_slice_state`, `to_isotropic`, `extract_slice`, `to_display_units`, `apply_window` stay behaviourally identical.
- Keep `st.image(..., use_column_width=True)`. 1.40 deprecates it; the codebase uses it throughout and migration is out of scope.
- No custom CSS. Sizing uses native `height=` / `use_container_width=`.
- These smoke tests must pass **unmodified**: `test_3d_plot_has_a_projection_geometry_toggle_in_the_corner`, `test_render_mode_offers_only_iso_surface`, `test_3d_options_no_longer_offer_a_show_trajectory_checkbox`, `test_startup_shows_an_empty_state_with_both_load_actions`.

## Review Focus

1. **Slice clamping ordering** — clamping must precede slice-slider creation, or a differently sized volume leaves stale keys and raises a widget-key error. Tested in Task 3 Step 1 via the existing `clamp_slice_state` unit tests plus the integration run.
2. **Column end-alignment** — MPR container height and figure height must stay equal, or the page gains dead space or a nested scrollbar. Manual in Task 4; the constant in Task 1 makes drift visible.
3. **Anisotropic coronal/sagittal heights** — `to_isotropic` can multiply slice height several-fold. The fixed-height container must scroll instead of stretching the page. Manual in Task 4.
4. **Geometry overlay boundary** — `n_base_traces` must be captured after `create_volume_figure` and before any overlay trace. Guaranteed by `test_3d_plot_has_a_projection_geometry_toggle_in_the_corner`, which asserts the Off button keeps some traces visible and hides others.
5. **Existing smoke-test discovery** — the geometry test finds the chart via recursive `_walk()` over `app.main.children`. Verified that a chart nested in `tabs → columns → container` is still found.
6. **Dependency floor drift** — `pyproject.toml` claims `>=1.28.0` while the app already needs `st.fragment` (1.37.0). Task 1 corrects it; a reviewer must not "helpfully" revert that.

---

## Task 1: Raise the Streamlit dependency floor and add the shared height constant

**Files:**
- Modify: `pyproject.toml:31`
- Modify: `src/visualization/app.py`

**Interfaces:**
- Produces: `VIEWER_HEIGHT_PX: int = 900` at module level in `app.py`, consumed by Tasks 2 and 3.

---

- [ ] **Step 1: Raise the floor to the version the app already requires**

In `pyproject.toml`, change:

```toml
    "streamlit>=1.28.0,<1.40.0",
```

to:

```toml
    "streamlit>=1.37.0,<1.40.0",
```

Rationale, for the commit message: `st.fragment` (already used at `app.py:489`) is GA in 1.37.0, so the old floor was already unsatisfiable. This design adds `st.container(height=)` (1.30.0) and `st.popover` (1.32.0), both below 1.37, so 1.37.0 covers everything. The upper pin stays because 1.40 deprecates `use_column_width`, which the codebase still uses.

- [ ] **Step 2: Add the shared height constant**

In `src/visualization/app.py`, immediately above `def render_viewer_tab(`:

```python
# Shared height for the two viewer columns, so the MPR stack and the 3D canvas
# end on one baseline. Tune together with the column ratio in render_viewer_tab
# and keep 3 * left_column_width + 165 <= VIEWER_HEIGHT_PX, or the MPR column
# scrolls permanently (see docs/superpowers/specs/2026-11-09-viewer-layout-design.md §3.4).
VIEWER_HEIGHT_PX = 900
```

- [ ] **Step 3: Verify nothing broke**

Run: `pytest tests/integration/test_ui_smoke.py -q`
Expected: PASS. The constant is inert until Task 2 uses it.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml src/visualization/app.py
git commit -m "build: require streamlit>=1.37 (st.fragment, popover) and add viewer height constant"
```

---

## Task 2: Left column — floating Slice Options and stacked MPR views

**Files:**
- Modify: `src/visualization/app.py` (`render_viewer_tab`)

**Interfaces:**
- Consumes: `VIEWER_HEIGHT_PX` from Task 1; `extract_slice`, `to_display_units`, `apply_window`, `to_isotropic`, `clamp_slice_state`, `window_limits`, `window_in_display_units`, `unit_label`.
- Produces: the tuple `col_mpr, col_3d = st.columns([1, 4])`, and in-scope locals `display_unit`, `energy_kev`, `center`, `width`, `axial_idx`, `coronal_idx`, `sagittal_idx`, `axial_max`, `coronal_max`, `sagittal_max` for Task 3.

---

- [ ] **Step 1: Move dimension computation and clamping above the widgets**

Currently `axial_max`/`coronal_max`/`sagittal_max` and the three `clamp_slice_state(...)` calls sit at lines 338–346, *after* the 3D figure renders. Move them to just before the new two-column block. Behaviour must not change: missing key → `max_idx // 2`; out-of-range key clamped into `[0, max_idx]`.

This is required by §5 of the spec: clamping must happen before the slice sliders exist.

- [ ] **Step 2: Create the two-column split**

Replace the MPR row's `axial_col, coronal_col, sagittal_col = st.columns(3)` with:

```python
col_mpr, col_3d = st.columns([1, 4])
```

Ratio rationale is §3.4 of the spec; do not substitute `[1, 1.4]`.

- [ ] **Step 3: Convert Slice Options to a popover in the left column**

Inside `with col_mpr:`, replace `with st.expander("Slice Options", expanded=True):` with:

```python
with st.popover("⚙️ Slice Options", use_container_width=True):
```

Move the existing body in unchanged: Display Unit selectbox, the attenuation-only energy slider, Preset selectbox, Center and Width sliders built from `window_limits()` / `window_in_display_units()` / `unit_label()`, and the three slice sliders. Nested `st.columns` inside a popover body is verified working on 1.39.1.

- [ ] **Step 4: Stack the three MPR views in a fixed-height container**

Still inside `with col_mpr:`, after the popover:

```python
with st.container(height=VIEWER_HEIGHT_PX, border=False):
    # Axial, then Coronal, then Sagittal
```

`border=False` is deliberate: the default `border=True` frames the stack, which adds noise next to the 3D canvas (spec §3.3).

Each block keeps the current shape exactly: `st.markdown("**Axial**")`, the slice/spacing `st.caption`, then `st.image(..., clamp=True, use_column_width=True)`. Coronal and sagittal keep their `to_isotropic(...)` resampling. The three plain `st.columns(3)` wrappers are removed — the blocks now stack vertically.

- [ ] **Step 5: Run the smoke test**

Run: `pytest tests/integration/test_ui_smoke.py -q`
Expected: PASS. At this point the 3D canvas still renders full-width above the columns; that intermediate state is expected and is corrected in Task 3.

- [ ] **Step 6: Commit**

```bash
git add src/visualization/app.py
git commit -m "refactor(ui): stack MPR planes in left column, float Slice Options"
```

---

## Task 3: Right column — floating 3D Options and the tall 3D view

**Files:**
- Modify: `src/visualization/app.py` (`render_viewer_tab`)
- Test: `tests/integration/test_ui_smoke.py`

**Interfaces:**
- Consumes: `col_3d` and the in-scope locals from Task 2; `VIEWER_HEIGHT_PX`; `create_volume_figure`, `add_trajectory_to_figure`, `add_source_detector_figure`, `add_geometry_toggle`, `get_volume_center`.
- Produces: nothing importable.

---

- [ ] **Step 1: Convert 3D Options to a popover in the right column**

Inside `with col_3d:`, replace `with st.expander("3D Options", expanded=True):` with:

```python
with st.popover("⚙️ 3D Options", use_container_width=True):
```

Move the body in unchanged: Render Mode, Camera, Downsample (still mirroring into `st.session_state["volume_downsample"]`), Opacity, the iso levels and threshold sliders, SID, Gantry Angle, Auto Isocenter with manual X/Y/Z, and Auto Source/Detector with manual source/detector fields.

The body defines `render_mode`, `camera_preset`, `opacity`, `n_iso_levels`, `iso_threshold`, `sid`, `gantry_angle`, `isocenter`, `source_pos`, `detector_pos`. All must remain in scope for the figure code below it — a popover is an ordinary context manager, so this works unchanged.

- [ ] **Step 2: Move the figure build into the right column**

Move the block currently at lines 264–336 into `with col_3d:`, below the popover, in this order: `create_volume_figure(...)` → `n_base_traces = len(fig.data)` → the `if projection_geometry is not None:` trajectory branch (else the single source/detector pair) → `fig = add_geometry_toggle(fig, n_base_traces)` → `st.plotly_chart(...)`.

Keep `n_base_traces` captured immediately after `create_volume_figure` and before every overlay trace. Add no traces between them. Keep the existing `if projection_geometry is not None:` condition — there is no `show_trajectory` flag any more.

- [ ] **Step 3: Size the figure to the shared height**

Immediately before `st.plotly_chart(...)`:

```python
fig.update_layout(height=VIEWER_HEIGHT_PX)
```

Keep `use_container_width=True` and `key="plotly_3d"` so widget state survives reruns.

- [ ] **Step 4: Delete the plot-slot reservation**

Remove `plot_slot = st.container()` (line 132) and the `with plot_slot:` wrapper (line 335). The ordering problem it worked around no longer exists, because the 3D controls are now defined before the chart. Confirm `plot_slot` has no other use first.

- [ ] **Step 5: Add the regression test for the floating panels**

Append to `tests/integration/test_ui_smoke.py`:

```python
def test_viewer_options_are_floating_popovers(app):
    """The option panels float over the views instead of pushing them down.
    Guards against a silent revert to expanders."""
    labels = [block.proto.popover.label for block in app.get("popover")]

    assert "⚙️ Slice Options" in labels
    assert "⚙️ 3D Options" in labels
```

The label lives on `block.proto.popover.label`; the block object has no `.label` attribute on 1.39.1.

- [ ] **Step 6: Verify the tests pass**

Run: `pytest tests/integration/test_ui_smoke.py -q`
Expected: PASS, including the new test and the four must-pass-unmodified tests.

- [ ] **Step 7: Commit**

```bash
git add src/visualization/app.py tests/integration/test_ui_smoke.py
git commit -m "refactor(ui): float 3D Options beside a tall 3D view"
```

---

## Task 4: Full suite and manual verification

**Files:** none created.

---

- [ ] **Step 1: Run the unit suite**

Run: `pytest tests/unit -q`
Expected: PASS. `tests/unit/test_app_integration.py` imports `clamp_slice_state` and `to_isotropic` from `visualization.app`, proving those entry points survived.

- [ ] **Step 2: Run the integration suite**

Run: `pytest tests/integration -q`
Expected: PASS, with `APP_PATH` still resolving to `src/visualization/app.py`.

- [ ] **Step 3: Run the project's lint checks**

Run the commands in `LINTING.md`.
Expected: no new findings in `app.py`.

- [ ] **Step 4: Launch and check the layout**

Run: `streamlit run src/visualization/app.py`

- [ ] Three MPR views small and stacked on the left, in axial → coronal → sagittal order.
- [ ] The 3D view fills the right column and is clearly the largest element.
- [ ] Both columns end on the same baseline; no page-level scrollbar at 1920×1080.
- [ ] Opening "⚙️ Slice Options" moves no view, and dragging a slice slider keeps the panel open.
- [ ] Opening "⚙️ 3D Options" moves no view; its contents are reachable, scrolling inside the panel if needed.
- [ ] A volume with `spacing=(3.0, 0.7, 0.7)` scrolls inside the MPR container instead of stretching the page.

- [ ] **Step 5: Check behaviour is unchanged**

- [ ] Each slice slider updates its plane.
- [ ] Display Unit HU ↔ attenuation re-ranges Center and Width.
- [ ] Window presets apply.
- [ ] Render Mode still offers only `Iso-Surface` and renders.
- [ ] The in-canvas `Projection Geometry` On/Off buttons toggle only the overlay.
- [ ] Auto Isocenter and Auto Source/Detector still reveal their manual fields.
- [ ] A fresh start still shows "Nothing to show" with "Load Demo Phantom".

- [ ] **Step 6: Tune the ratio and height together**

If the layout needs adjusting, change `st.columns([1, 4])` and `VIEWER_HEIGHT_PX` as a pair. Keep `VIEWER_HEIGHT_PX >= 3 × left_column_width + 165` (spec §3.4), or the left column will scroll permanently. Because both the container and the figure read `VIEWER_HEIGHT_PX`, they cannot drift apart.

- [ ] **Step 7: Commit the tuned values**

```bash
git add src/visualization/app.py
git commit -m "style(ui): tune viewer column ratio and shared height"
```
