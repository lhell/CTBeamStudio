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
- Either column can be collapsed to give the other the full width, and the
  control that does it stays reachable in every state.
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

### 3.1 A 3+1 split by default, not a 2×2 grid

The user's initial phrasing was "2×2 layout, first three MPR small, bottom
right 3D big". A literal 2×2 grid cannot deliver "3D big": in a 2×2 grid the 3D
cell is one quadrant, so it is no larger than an MPR cell. The default state is
therefore a 3+1 split, which makes the 3D view dominate directly:

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

The 2×2 grid is still available — as the **2D view** of the switcher in §3.5,
where it has the full tab width to spread into and no 3D canvas competing with
it. In the split state a 2×2 grid would shrink each plane to a quarter of a
narrow column, which is worse than the vertical stack.

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
VIEWER_HEIGHT_PX = 700
```

Both columns carry a popover button of equal height above their content, so
their content starts at the same offset and the columns end on one baseline.

**Why 700 and not 900.** The first draft used 900. In the running app that put
the top of the Plotly canvas ~362 px down the page (Streamlit header, tabs,
switcher and popover button all stack above it), so a 900 px canvas ran to
y ≈ 1262 and the lower half of the 3D scene sat below the fold on a 1080p
screen. 700 keeps the canvas inside a typical laptop viewport: measured
y = 362 → 1062 at a 670 px-tall test window, with the cube itself occupying
560 px of the 700 px canvas.

**Why the scene is top-anchored.** Plotly centres a 3D scene inside its domain.
Even at 700 px, centring leaves a large empty band above the cube and pushes it
down. `SCENE_DOMAIN_Y = [0.2, 1]` anchors the scene toward the top of the
canvas while still using most of its height (measured cube height 560 px, offset
0 px from the canvas top).

`st.container(height=...)` defaults to `border=True`, which would draw a frame
around the MPR stack. The design uses `border=False`: the slice headings already
delimit each view, and a box around three images competing with the 3D canvas
adds visual noise without grouping anything meaningful.

### 3.4 Images fill their column; the stack scrolls if it must

This section was rewritten after measuring the running app. The first draft
capped images at a fixed 260 px (`MPR_IMAGE_WIDTH`) and reasoned from a
standalone mockup. That cap is **not** in the implementation.

**Why the fixed cap was dropped.** A fixed pixel width is unsafe in a flexible
column. Measured earlier: a 260 px image in a 201 px column overflows (the
parent is `overflow: visible`) and spills into the 3D column. Streamlit 1.39
offers no `width=min(...)`, so a fixed cap cannot shrink with the column.

**What is used instead.** `st.image(..., use_column_width=True)`, the same call
the pre-existing code used. The image then equals the column width, so the
stack height is a function of the column ratio:

```
stack_height ≈ 3 × (column_width + 26 px heading)
```

**Measured in the running app** (1536×864 screen, 1112 px viewport):

| view | column | image | stack | container | fits |
|---|---|---|---|---|---|
| All | 195 px | 190 px | 685 px | 700 px | yes |
| 2D | 594 px | 289 px | 2×2 grid | 700 px | yes |

So at the chosen `[1, 2]` ratio the three planes fit inside 700 px with ~15 px
to spare. The ratio is doing the work the dropped pixel cap was meant to do.

**Accepted consequence.** On a much wider window the left column grows and the
stack exceeds 700 px. That is fine by design: the fixed-height container
(`st.container(height=VIEWER_HEIGHT_PX, border=False)`) scrolls internally
instead of stretching the page or pushing the 3D view down. This also covers
anisotropic coronal/sagittal planes, whose `to_isotropic` resampling can
multiply their height several-fold.


### 3.5 A view switcher: Both / 2D / 3D

The user can give either side the full width. Three states, driven by one
control:

| State | Left column | Right column | MPR layout |
|---|---|---|---|
| **Both** | 1 part | 2 parts | vertical stack |
| **2D** | full width | collapsed | **2×2 grid** |
| **3D** | collapsed | full width | (hidden) |

The control must live **outside** the two columns. A collapse toggle placed
inside the column it collapses becomes unreachable once that column is 0 px
wide — the user is then stuck in that state.

Verified collapse mechanism: `st.columns([0.0001, 1])` renders the first column
at **0 px** and the second at the full content width, with no error. A literal
`[0, 1]` is rejected (`StreamlitInvalidColumnSpecError`: the spec must be a list
of *positive* numbers), so the epsilon is required, not a stylistic choice.

Proposed control: a single `st.segmented_control` (1.40+ only) would raise the
floor again, so use `st.radio(..., horizontal=True)` or three `st.button`s,
which are available at 1.37. The state lives in `st.session_state`.

**2×2 grid in 2D mode.** With the MPR column at full width the three planes are
laid out as a 2×2 grid (axial, coronal on the first row; sagittal and an empty
cell on the second) instead of a vertical stack. Streamlit has no grid
primitive, so this is two `st.columns(2)` rows. The fourth cell stays empty —
there is no fourth plane, and inventing one (a composite, an overlay) is out of
scope.

Consequence: in 2D mode the image width is set by the *grid cell*, not by the
column, so the planes render larger than in All mode (measured: 289 px vs
190 px). That is the point of the mode.

### 3.6 The slice/spacing caption moves into Slice Options

The per-plane `Slice N/M | Spacing: (…)` caption used to sit under each
image. It is diagnostic text, not a label, and in the stacked layout it costs
~26 px × 3 of height that the images need. It moved into the Slice Options
panel as a compact three-row block, one row per plane.

This drops per-item chrome to just the plane heading (~26 px), which is what
keeps the stack at 685 px inside the 700 px container (see §3.4).

### 3.7 Dependency floor must be raised

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
No new modules.

```
render_viewer_tab(volume, projection_geometry, n_projections, trajectory_downsample)
│
├─ volume is None ──> existing empty / polling states (unchanged, early return)
│
├─ compute axial_max, coronal_max, sagittal_max
├─ clamp_slice_state(...) × 3          ← moved above the widgets
│
├─ view switcher (OUTSIDE the columns): Both | 2D | 3D
│     stored in st.session_state["viewer_view"]
│
├─ col_mpr, col_3d = st.columns(VIEWER_SPECS[view])
│
├─ col_mpr                                            (skipped in 3D)
│   ├─ st.popover("⚙️ Slice Options")
│   │    Display Unit · Energy · Preset · Center · Width · 3 slice sliders
│   │    + slice/spacing readout for the three planes
│   └─ view == "2d" -> two st.columns(2) rows  (2x2 grid)
│      else         -> st.container(height=VIEWER_HEIGHT_PX)  (vertical stack)
│         Axial · Coronal · Sagittal  (heading + image)
│
└─ col_3d                                             (skipped in 2D)
    ├─ st.popover("⚙️ 3D Options")
    │    Render Mode · Camera · Downsample · Opacity · iso levels/threshold
    │    SID · Gantry · Auto Isocenter (+manual) · Auto Source/Detector (+manual)
    └─ create_volume_figure → n_base_traces → overlay traces
       → add_geometry_toggle → st.plotly_chart(height=VIEWER_HEIGHT_PX)
```

The switcher must be rendered before the columns and outside them, so it remains
clickable when one column is collapsed.

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
