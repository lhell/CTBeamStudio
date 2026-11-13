# Audit Findings — 2026-11-13

Findings from a whole-repo audit (backend, visualization, tests, CI, packaging).
Load assumed: one researcher running the app locally. Order: correct, safe,
holds under load, tested, fast, lean. Each item is a candidate for a ledger task
(`docs/plan.md`) when picked up; promote it with the usual Ziel / Dateien /
Abhängig von / Akzeptanz / Status format.

Status values: `open` / `in progress` / `fixed` / `wontfix`.

## Must fix

### 1. Forward projection crashes on every CUDA machine — `open`

- **Where:** `src/backend/parallelproj/projector.py:L82-88`, `src/backend/forward_project.py:L209-210`
- **What:** On a GPU machine the LOR position tensors are created on
  `device="cuda"`, then `ConeBeamProjector.__init__` calls
  `np.asarray(pos_beam_start)` on a CUDA torch tensor.
- **Problem:** numpy cannot convert a CUDA tensor → `TypeError: can't convert
  cuda:0 device type tensor to numpy` on the first "Run Forward Projection".
  The "Use CUDA if available" checkbox defaults to ON, so every GPU user hits
  it. The fix already exists in the same file: `_as_numpy_xyz`
  (`projector.py:L28-38`) does `.detach().cpu().numpy()` — it is never called.
- **Fix:** Wrap both position tensors with the existing `_as_numpy_xyz` helper
  in `ConeBeamProjector.__init__`. Nothing else changes.
- **If skipped:** Forward projection is broken on GPU, right after
  environment.yml and README promise "CUDA when available".
- **Verify:** Cannot be tested on this machine (no CUDA); check in a GPU
  environment or via a mocked-device unit test.

### 2. DICOM loader ignores the file's RescaleSlope / RescaleIntercept — `open`

- **Where:** `src/backend/loaders/dicom.py:L358-376`
  (test: `tests/unit/test_dicom_loader.py:L314-334`)
- **What:** `ds.pixel_array` returns raw stored values; HU = raw × slope +
  intercept. The auto-detected-unit path (the default) applies hardcoded
  slope=1 / intercept=-1024 and never reads the file's tags. Only the
  forced-unit path reads them.
- **Problem:** A series stored with `RescaleSlope=2, RescaleIntercept=-2000`
  loads 500 raw as −524 HU instead of the true −1000 HU. Every HU window,
  display unit, and forward projection downstream is wrong.
  `test_load_dicom_series_custom_rescale` states "Expected HU = −1000" in its
  comment but only asserts the unit label, so the bug hides behind a green test.
- **Fix:** In the auto path, read `RescaleSlope`/`RescaleIntercept` from the
  first slice when present; fall back to the detected defaults when absent.
  Make the test assert the values.
- **If skipped:** Scanners with non-default rescale silently produce wrong HU
  for the tool's core workflow.

### 3. 3D tab crashes for volumes not in HU — `open`

- **Where:** `src/visualization/app.py:L263-275`
- **What:** The iso-threshold slider is built from
  `int(np.min(volume.array))` / `int(np.max(volume.array))`.
- **Problem:** The DICOM loader auto-detects float32 data with small positive
  values as "1/mm". For such a volume both ints are 0, so the slider is created
  with `min_value=0, max_value=0, value=(200, -200)` → `StreamlitAPIException`
  (Streamlit rejects min==max sliders — see the repo's own `index_slider`
  comment in `projection_panel.py:L202-212`). Opening the 3D view kills the
  tab. The label also says "(HU)" for non-HU data. No test covers this.
- **Fix:** Guard the slider the way `index_slider` does (skip or fall back to
  fixed thresholds when the range is too small) and label the unit from
  `volume.meta["unit"]`.
- **If skipped:** Loading an attenuation-unit volume bricks the 3D view.

## Should fix

### 4. Per-slice metrics recomputed on every rerun — `open`

- **Where:** `src/visualization/projection_panel.py:L849-872`
- **What:** When measured and simulated shapes match,
  `compute_metrics_per_slice` (SSIM per projection) runs on every script rerun.
- **Problem:** Every widget interaction in the tab — including the
  projection-index slider — recomputes SSIM for every frame. The demo (60
  frames) costs ~1 s per interaction; a real measured scan (2304 × 512 × 512)
  means ~2300 SSIMs ≈ tens of seconds per slider move, in the app's central tab.
- **Fix:** Compute once per forward-projection run and stash in session state
  next to `forward_projection` (same pattern the result already uses).
- **If skipped:** The comparison tab becomes unusable on real-size data.

### 5. Volume cache never evicts — `open`

- **Where:** `src/visualization/volume_cache.py:L17-42`
- **What:** `_volume_cache` is a module-level dict; every loaded DICOM series
  stays in server memory for the process lifetime.
- **Problem:** A 512³ int16 series is ~256 MB. A few loads (or a few sessions
  on one server) accumulate GBs with no bound.
- **Fix:** Keep only the last 1–2 entries (drop on each new load). The
  restore-last-session logic already handles getting data back.
- **If skipped:** Long sessions leak memory until the process dies.

### 6. Volume origin stored in the wrong frame after the DICOM flip — `open`

- **Where:** `src/backend/loaders/dicom.py:L344-392`,
  `src/backend/forward_project.py:L219-225`
- **What:** The loader transposes and flips the grid into the project frame
  (x = anterior positive) but reports the raw DICOM LPS origin unchanged.
  `forward_project` treats `Volume.origin` as project-frame (x, y, z) of the
  first voxel.
- **Problem:** For the standard isocenter-centered square FOV the numbers
  coincide (origin_x = origin_y = −half-extent), so it works. For anything
  else — off-center reconstruction, rectangular in-plane grid — both in-plane
  axes are placed wrong: the correct project-frame start is
  (−y_LPS − half-extent, x_LPS), the code uses (x_LPS, y_LPS). The simulated
  projections land mirrored/offset relative to the beams, silently corrupting
  the simulated-vs-measured comparison. Verified by hand on a 2×2 example; the
  phantom and centered AAPM data mask it.
- **Fix:** In `load_dicom_series`, compute the project-frame origin for
  standard-axial data (it knows the flip and the spacing there):
  `(-(y0 + (nrows-1)*row_sp), x0, z_first)`.
- **If skipped:** Off-center acquisitions silently produce misaligned
  comparisons.

### 7. Dead autograd layers module with a latent bug — `open`

- **Where:** `src/backend/parallelproj/layers.py` (203 lines)
- **What:** `LinearSingleChannelOperator`, `AdjointLinearSingleChannelOperator`,
  `ReshapeLayer` — no callers anywhere in src or tests (only a reference copy
  under `docs/superpowers/code/`). `from_parallelproj_batch` in shape.py is
  test-only.
- **Problem:** Speculative code that must be read, linted, and kept working for
  nothing. It already rots: the Adjoint layer's `forward` indexes
  `proj[i, ...]` instead of `proj[i, 0, ...]`, so it would pass a 2-D array to
  the adjoint if anyone called it.
- **Fix:** Delete the module (and the stale docstring references to it, e.g.
  `src/backend/parallelproj/__init__.py:L11`). Re-add when the training path
  actually lands.
- **If skipped:** The first user of the adjoint layer inherits a broken
  function with zero tests.

### 8. Dead compat wrappers and shelved PyVista renderer — `open`

- **Where:** `src/visualization/volume3d.py:L1051-1278` (~230 lines)
- **What:** `get_dicom_geometry`, `create_volume_plotter`,
  `create_plotly_figure`, `add_source_detector`, `create_pyvista_volume` — no
  callers anywhere.
- **Problem:** Keeping the shelved PyVista mode "for later" (T-82) is a
  decision, but these lines also contain a provably broken helper:
  `create_plotly_figure` uses `hasattr(plotter_data, "figure")` on a dict,
  which is always False, so it returns the dict instead of the figure.
- **Fix:** Delete all five functions (and `PYVISTA_AVAILABLE`). Git history
  keeps them. Re-add the renderer if the PyVista mode returns.
- **If skipped:** ~230 lines of dead weight, one of them broken.

### 9. Three unused dependencies — `open`

- **Where:** `pyproject.toml:L26-38`
- **What:** `pandas`, `streamlit-image-coordinates`, and `array-api-compat`
  are imported nowhere in src or tests (`array-api-compat` only in the docs
  reference copy).
- **Problem:** Each is installed, resolved, and updated on every environment
  build for nothing, and widens the supply-chain surface.
- **Fix:** Remove the three lines.
- **If skipped:** Slower installs, more CVE surface, none of it used.

### 10. `load_npy` reads every file twice — `open`

- **Where:** `src/backend/loaders/npy.py:L170-171`
- **What:** `original_dtype = np.load(path).dtype` re-reads the whole array
  from disk only to get the dtype it already had before rescaling.
- **Problem:** Doubles I/O for large volumes, for one attribute.
- **Fix:** Capture `arr.dtype` at the first `np.load` and reuse it.
- **If skipped:** Pure waste, but free to fix.

## Nice to have

### 11. `phantom.py` __main__ block needs matplotlib, which is not a dependency — `open`

- **Where:** `src/visualization/phantom.py:L509-523`
- **Problem:** `python -m visualization.phantom` dies with
  `ModuleNotFoundError: matplotlib`.
- **Fix:** Delete the block (its output PNG is already committed in the repo
  root) or add matplotlib to `[dev]`.

### 12. Unreachable branch in `_detect_unit` — `open`

- **Where:** `src/backend/loaders/dicom.py:L226-228`
- **Problem:** The second float32 check (`max < 1`) can never run — the
  previous check (`max < 10`) already returned.
- **Fix:** Delete 3 lines.

### 13. Debug leftovers — `open`

- **Where:** `src/visualization/app.py:L6,L23-26`, `tests/conftest.py:L18-23`
- **Problem:** `uuid` imported in app.py and never used (F401 is in the flake8
  ignore set, so lint won't flag it); the "Debug: log where modules are loaded
  from" lines log on every app start; conftest prints a debug line on every
  pytest run.
- **Fix:** Delete.

### 14. Docs out of date with the code — `open`

- **Where:** `README.md`, `AGENTS.md`
- **Problem:**
  - README Roadmap says forward-projection UI and the comparison are
    "planned" — both are implemented (Sinogram Inspection tab).
  - Usage says `streamlit run app.py` (actual:
    `src/visualization/app.py`) and "folder picker" (it's a text input).
  - README advertises NumPy volumes as an input; the UI only loads DICOM
    (`load_npy` has no UI caller).
  - AGENTS.md test bar says "7 slow tests are deselected by default" — no
    `@pytest.mark.slow` marker exists anywhere, and collection is 351 tests,
    not the documented 345+7=352.
- **Fix:** One README and one AGENTS.md edit.

## Summary

- **Must fix:** 1–3 (CUDA crash, wrong HU for non-default rescale, 3D crash
  for non-HU volumes). Fix 1 and 2 before trusting the simulated-vs-measured
  comparison on real data.
- **Should fix:** 4–10 (speed, memory, origin frame, dead code, dependencies).
- **Nice to have:** 11–14.
- **Lean total:** ~450 lines and 3 dependencies removable (7, 8, 9, 10, 12, 13).
- **Not audited / not re-verified:** browser UI (no live run — `run_every`
  fragments and modebar toggles need manual verification), the CUDA path (no
  GPU on the audit machine), `scripts/`, `docs/` (plan.md, geometry.md,
  superpowers specs), `.streamlit/` config, INSTALLATION/LINTING/SECURITY/
  CITATION files, and the anatomical correctness of the MPR/3D orientation
  letters (covered by existing tests and screenshots).
