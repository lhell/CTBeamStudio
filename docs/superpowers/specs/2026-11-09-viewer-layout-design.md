# Viewer Layout — Small Stacked MPRs + Large 3D View

**Date:** 2026-11-09
**Status:** Approved design, pending implementation
**Scope:** Viewer tab layout only (`render_viewer_tab` in `src/visualization/app.py`)

## 1. Problem

The Viewer tab currently renders its three content areas in a single vertical
stack:

1. the 3D canvas, full width,
2. the **3D Options** expander,
3. the **Slice Options** expander,
4. the three MPR planes side by side in an equal-width 3-column row.

Two consequences:

- **The 3D view and the MPR views compete for the same vertical space.** Both
  are full width, so each is only as tall as the viewport allows before the
  user has to scroll. On a 1080p screen the 3D canvas is roughly 450 px tall,
  which is too small to judge projection geometry against the volume — the
  primary reason to open this tab.
- **Opening either options expander pushes the views down.** An expander
  reflows the page, so adjusting a slice slider moves the very image the user
  is trying to watch.

The MPR planes, by contrast, do not need the full width: they are individually
portrait-ish slices whose useful information is limited by their display size,
not by the column they sit in.

## 2. Goal

Give the 3D view the majority of the tab — both wider and taller — while the
three MPR planes stay visible, small, and stacked beside it. Options must be
reachable *without* displacing either view.

**Success criteria**

- The 3D view is visibly the largest element in the tab.
- All three MPR planes are visible at the same time as the 3D view.
- Opening or closing either options panel moves no view.
- Every existing control still works, with the same labels, keys, defaults and
  conditional visibility.
- No page-level scrollbar appears at 1920×1080.

**Non-goals**

- No change to the Geometry tab or the Real-vs-Simulated tab.
- No change to the controls themselves, their defaults, or the slice/windowing
  pipeline.
- No re-enable of the shelved PyVista render mode (plan.md T-82).
- No custom CSS and no new dependencies.
- No change to the startup-loading path, the empty state, or the sidebar.

## 3. Decisions

### 3.1 A 3+1 split, not a 2×2 grid

The user's initial phrasing was "2×2 layout, first three MPR small, bottom
right 3D big". A literal 2×2 grid cannot deliver "3D big": in a 2×2 grid the 3D
cell is one quadrant, so it is no larger than an MPR cell. The requirement that
actually matters is *the 3D view dominates*, which a 3+1 split satisfies
directly:

```
left column (narrow)            right column (wide)
┌──────────────────────┐        ┌───────────────────────────────┐
│ [⚙️ Slice Options]   │        │ [⚙️ 3D Options]               │
│                      │        │                               │
│  Axial               │        │                               │
│  [ small image ]     │        │       3D view (tall)          │
│  Coronal             │        │                               │
│  [ small image ]     │        │                               │
│  Sagittal            │        │                               │
│  [ small image ]     │        │                               │
└──────────────────────┘        └───────────────────────────────┘
```

This was chosen by the user over an equal 2×2 grid and over a 2-row split.

### 3.2 Options live in popovers, beside the views they control

`st.popover` renders its contents in a floating panel anchored to a button.
Opening one does **not** reflow the page, so views never move. This replaces
both expanders.

Placement follows the view each panel controls: **Slice Options in the left
column** (above the MPR stack), **3D Options in the right column** (above the 3D
canvas).

Verified behaviour on the pinned Streamlit 1.39.1, from the installed
docstring: *"Opening and closing the popover will not trigger a rerun.
Interacting with widgets inside of an open popover will rerun the app while
keeping the popover open."* Dragging a slider inside a panel therefore keeps
the panel open. This was checked explicitly because it determines whether the
design is usable at all.

Known constraint: the popover body is styled `maxHeight: 70vh; overflow: auto`.
The 3D Options panel carries ~15 controls and will scroll internally below
roughly 1000 px of viewport height. This is acceptable — the alternative
(a modal `st.dialog`) would block the view being adjusted, which defeats the
purpose.

### 3.3 The columns share one height constant

The MPR container and the Plotly figure must agree on height, or the page gains
dead space or a nested scrollbar. A single module-level constant is used for
both:

```python
VIEWER_HEIGHT_PX = 900
```

Both columns carry a popover button of equal height above their content, so
their content starts at the same offset and the columns end on one baseline.

`st.container(height=...)` defaults to `border=True`, which would draw a frame
around the MPR stack. The design uses `border=False`: the slice headings and
captions already delimit each view, and a box around three images competing with
the 3D canvas adds visual noise without grouping anything meaningful.

### 3.4 Column ratio is derived, not chosen for looks

Three square MPR images stacked at column width `w` need `3w` px of height, plus
~165 px of per-image chrome (bold heading ~30 px + spacing caption ~25 px, ×3).
With content width `C` and a `[1, r]` split, the left column is `C / (1 + r)`
wide. The layout fits only when:

```
VIEWER_HEIGHT_PX >= 3 × C/(1+r) + 165
```

At `C ≈ 1200` px: `r=1.4` gives a 500 px column needing ~1665 px (absurd),
`r=3.5` gives ~343 px needing ~1194 px (does not fit in 900), `r=4` gives
240 px needing ~885 px (fits). **`[1, 4]` at 900 px** is the starting point.

If the container is too short, the left column scrolls permanently instead of
shrinking the images, so this inequality must hold when the values are tuned.

### 3.5 Dependency floor must be raised

`pyproject.toml` declares `streamlit>=1.28.0,<1.40.0`, but the app **already**
requires `st.fragment`, which was generally available in **1.37.0** — the
declared floor is currently wrong and would fail on 1.28.

This design additionally uses:

| API | Available since |
|---|---|
| `st.container(height=...)` | 1.30.0 |
| `st.popover` | 1.32.0 |
| `st.fragment` (already used) | 1.37.0 |

The floor therefore becomes **`streamlit>=1.37.0,<1.40.0`**. The upper pin is
kept: 1.40 deprecates `use_column_width` in favour of `use_container_width`, and
this codebase still uses `use_column_width` throughout.

## 4. Architecture

The change is confined to `render_viewer_tab()` in `src/visualization/app.py`.
No new modules, no new functions beyond the height constant.

```
render_viewer_tab(volume, projection_geometry, n_projections, trajectory_downsample)
│
├─ volume is None ──> existing empty / polling states (unchanged, early return)
│
├─ compute axial_max, coronal_max, sagittal_max
├─ clamp_slice_state(...) × 3          ← moved above the widgets
│
└─ col_mpr, col_3d = st.columns([1, 4])
   │
   ├─ col_mpr
   │   ├─ st.popover("⚙️ Slice Options")
   │   │    Display Unit · Energy · Preset · Center · Width · 3 slice sliders
   │   └─ st.container(height=VIEWER_HEIGHT_PX)
   │        Axial → Coronal → Sagittal  (heading, caption, image)
   │
   └─ col_3d
       ├─ st.popover("⚙️ 3D Options")
       │    Render Mode · Camera · Downsample · Opacity · iso levels/threshold
       │    SID · Gantry · Auto Isocenter (+manual) · Auto Source/Detector (+manual)
       └─ create_volume_figure → n_base_traces → overlay traces
          → add_geometry_toggle → st.plotly_chart(height=VIEWER_HEIGHT_PX)
```

The `plot_slot = st.container()` reservation is deleted. It existed only because
the 3D controls were defined after the plot needed to appear above them; with
the controls in a popover defined first, there is nothing to reserve.

## 5. Behaviour that must not change

- `clamp_slice_state` semantics: missing key → `max_idx // 2`; out-of-range key
  clamped into `[0, max_idx]`. It must run **before** the slice sliders are
  created, or a volume of a different size leaves stale keys.
- Slice extraction, display-unit conversion, windowing, and isotropic
  resampling for coronal/sagittal are untouched.
- `n_base_traces` is captured immediately after `create_volume_figure(...)` and
  before any overlay trace, so the in-canvas `Projection Geometry` On/Off
  buttons still hide only the source/detector and trajectory traces.
- The trajectory is drawn whenever `projection_geometry is not None` (there is
  no `show_trajectory` flag any more).
- The empty state, the startup status block, and the failure message are
  untouched.

## 6. Testing

| Layer | Test | Purpose |
|---|---|---|
| Unit | existing `tests/unit/test_app_integration.py` | `clamp_slice_state` / `to_isotropic` still importable and correct |
| Integration | existing `tests/integration/test_ui_smoke.py` | App renders without exception; tabs, sidebar order, geometry toggle, iso-only render mode all unchanged |
| Integration | new `test_viewer_options_are_floating_popovers` | The two option panels are popovers, not expanders — guards against silent revert |

`AppTest` on 1.39.1 exposes popover blocks via `at.get("popover")`, with the
label at `block.proto.popover.label` (the block itself has no `.label`
attribute). A Plotly chart nested in `tabs → columns → container` is still found
by the existing `_walk()` helper, so the geometry-toggle test needs no change.

Manual verification covers what no test can: that the 3D view is actually large,
that the columns align, and that opening a panel moves nothing.

## 7. Risks

| Risk | Mitigation |
|---|---|
| Popover body scrolls internally (70vh cap) | Accepted; contents remain reachable. Fall back to a collapsed expander above the views only if a control becomes unreachable. |
| MPR column too short for three stacked images | The derived-ratio inequality in §3.4; Task 4 tunes both constants together. |
| Anisotropic volumes make coronal/sagittal very tall | The fixed-height container scrolls internally rather than stretching the page. |
| Someone "restores" the 2×2 grid | §3.1 records why 3+1 was chosen; the popover test guards the panel placement. |
| Declared Streamlit floor stays wrong | §3.5 raises it to `>=1.37.0`; the app already required 1.37. |
