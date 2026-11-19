# GPU forward projection — design

Date: 2026-11-19
Ledger task: T-08-01
Status: proposed (not implemented, not in the tested baseline)

## Problem

Forward projection requests CUDA on any machine where `torch.cuda.is_available()`
is true: `forward_project(..., use_cuda=True)` is the default and the UI checkbox
defaults to on. `ConeBeamGeometry.calculate_xray_beam_list(dev="cuda")` therefore
returns CUDA torch tensors. The projector converts them with `np.asarray` in
`src/backend/parallelproj/projector.py:82-88`, which raises
`TypeError: can't convert cuda:0 device type tensor to numpy`. The same
unconditional conversion appears in `apply()` and `adjoint()` (lines 128, 144).

A second, independent failure appears when CUDA is hidden: a **GPU-built**
`parallelproj`/`libparallelproj` hardcodes a CUDA backend, so even numpy CPU
inputs crash with `cudaSetDevice failed: no CUDA-capable device is detected`.
Unticking "Use CUDA if available" is therefore *not* a universal workaround in
a GPU-built env. Audit finding #1
(`docs/audit-2026-11-13-findings.md`) has been open since 2026-11-13; the
2026-11-19 error report reproduced both modes on real hardware.

## Goals

- Forward projection runs on CUDA and produces the same projections as the CPU
  path within float32 tolerance.
- One device-independent code path in the backend: no implicit
  CUDA-tensor → numpy conversion, no duplicate "GPU projector".
- The CPU-only env, the zero-skip test bar and the current results stay unchanged.
- Make the fallback explicit: a GPU-built parallelproj cannot silently fall
  back to CPU inside the same env; docs and the UI must say so, or a CPU-capable
  build must be provided.
- Installation docs drop the known-limitation warning once verified.

## Non-goals

- No parallelproj 2.x migration. The validated dependency set stays conda-forge
  `parallelproj` 1.x / matching `libparallelproj`, Python 3.11.
- No GPU in Docker (`full` stays CPU), no GPU runner in CI, no multi-GPU or
  distributed projection, no changes to the data model or attenuation logic.
- No new skip guards: a skipped test remains a defect (AGENTS.md, D-21).

## Evidence: GPU route error report (2026-11-19)

Investigation only — no fixes were applied. See the ledger status and this
section for the reproduced failures.

**Environment used:** conda env `ct-viewer`, Python 3.12.16, `parallelproj 2.0.2`
+ `libparallelproj 2.0.7 (cuda130)`, `pytorch 2.14.1 (cuda134)`,
`cuda-toolkit 13.5`, 8× NVIDIA RTX A6000, driver CUDA 13.4.
Suite: **19 failed / 340 passed** in GPU mode; **23 failed / 336 passed** with
`CUDA_VISIBLE_DEVICES=""`.

| # | Where | Trigger | Effect |
|---|---|---|---|
| 1 | `projector.py:82-88` | GPU machine, "Use CUDA" on (default) | `TypeError: can't convert cuda:0 device type tensor to numpy` on the first forward projection. `_as_numpy_xyz` (`projector.py:28-38`) already does `.detach().cpu().numpy()` but is never called. |
| 2 | GPU operator `_apply` via `ConeBeamProjector.apply` | CPU numpy input with `CUDA_VISIBLE_DEVICES=""` | `RuntimeError: cudaSetDevice failed: no CUDA-capable device is detected`. The GPU-built parallelproj 2.0.7 operator ignores the env var and cannot run CPU input; API/semantics mismatch with the app's CPU assumptions. |
| 3 | `forward_project.py:132 → 289 → 83` | default `use_cuda=True` on this machine | Same crash as #1, surfacing as test failures. |

Full trace for #3: `tests/unit/test_forward_project.py:66` →
`forward_project.py:132` → `forward_project.py:289` → `projector.py:83`.

**Failing tests (19, GPU mode):**
`tests/integration/test_ui_smoke.py::test_sinogram_inspection_run_button_produces_simulation`,
`tests/test_dummy_measurement.py::TestDummyMeasurement` (10),
`tests/test_dummy_measurement.py::TestDummyMeasurementCache` (4),
`tests/unit/test_forward_project.py` (6).
CPU mode (`CUDA_VISIBLE_DEVICES=""`) additionally breaks
`tests/integration/test_projection_workflow.py` (2) and
`tests/unit/test_parallelproj.py` (2).

**Design contradiction to resolve:** the old plan
`docs/superpowers/plans/2026-10-27-parallelproj-forward-projection.md` specifies
Python ≥ 3.12 and `cuda-toolkit=12.1`, while `AGENTS.md` /
`docs/local-environment.md` specify Python 3.11, CPU-only as the validated
baseline (359 passed, 0 skipped at the time of the report; 387 now). A CUDA path
is documented but untested by design ("Cannot be tested on this machine (no
CUDA)", audit finding #1). `INSTALLATION.md` now records the pinned baseline and
the observed GPU failures.

## Proposed design

1. **One conversion boundary in `backend/parallelproj/projector.py`.**
   Replace `_as_numpy_xyz` (which always moves data to host memory) with two
   helpers, e.g. `_to_operator_input(value, device)` and
   `_from_operator_output(value)`, used by `__init__`, `apply` and `adjoint`.
   - Inputs: keep `float32`, shape `(n, 3)`, C-contiguous; use a torch tensor on
     the selected device when parallelproj 1.x is given CUDA tensors, numpy
     arrays on CPU.
   - Outputs: if the result is a torch tensor, call `.detach().to("cpu").numpy()`
     before reshaping; numpy results pass through as today.
   - The reshape/axis swap `(proj, cols, rows) → (proj, rows, cols)` stays
     unchanged; numerical output must not change on CPU.
2. **Explicit device on `ConeBeamProjector`.** Add a `device` argument (default
   `"cpu"`) and pass the `dev` chosen in `forward_project` into the projector.
   `ConeBeamGeometry` keeps returning tensors on that device. No guessing from
   tensor types inside the projector.
3. **Volume placement in `forward_project`.** Transfer the volume to the
   selected device once, before the chunk loop; keep the existing 32-projection
   chunking, helix centring and progress callback intact. The returned
   `ForwardProjectionResult.projections` stays a CPU numpy array.
4. **Adapter for the upstream API.** Encapsulate the one place that constructs
   `ListmodePETProjector` so a future 2.x migration does not spread through the
   projector. 1.x remains the only supported baseline for this task. Decide
   explicitly how a GPU-built env behaves when the user disables CUDA: either
   install a CPU-capable `libparallelproj` build or report a clear error instead
   of the `cudaSetDevice` crash.
5. **Tests without skips.**
   - Unit tests for the conversion helpers with a fake tensor that raises on
     implicit `numpy()`/`__array__` conversion, asserting the explicit
     `.detach().cpu().numpy()` route is used.
   - Device-parity tests: a fixture selects `cuda:0` when real CUDA is
     available and `cpu` otherwise; every test runs somewhere, none skip.
     On a GPU machine the same test executes the CUDA path.
   - Existing CPU result tests (four-region geometry, non-contiguous indices,
     helix, progress) must stay valid.
   - GPU end-to-end run and browser verification are manual and recorded in the
     ledger status (like T-109's browser checks and T-83's `run_every` note).

**Why these tests pass on a machine without a GPU, with zero skips:**

- A session fixture returns `cuda:0` when `torch.cuda.is_available()` and `cpu`
  otherwise. Every test runs on whichever device exists; nothing is skipped and
  no test asserts CUDA is present.
- The CUDA-specific conversion logic is covered with a fake tensor whose
  `numpy()` / `__array__` raise and whose `.detach().cpu()` yields a plain
  array. Combined with a stubbed `ListmodePETProjector`, this proves the
  projector takes the explicit host-copy route without needing CUDA hardware.
- The numerical assertions (four-region geometry, non-contiguous indices,
  helix, progress) run on real data with the available device; CPU numbers stay
  unchanged. Device results are compared against a reference with a tolerance
  measured on the GPU machine, not a tolerance guessed from a CPU run.
- What cannot be automated here is real CUDA kernel execution: no test can run
  actual CUDA kernels and also pass on this CPU-only workstation without a
  skip. That is why step 5 of the plan is a manual GPU run recorded in the
  ledger, following the precedent for browser-only checks (T-109, T-83).

**Machine dependence of the suite — current state and target:**

Today the suite is machine-dependent in *outcome*: `forward_project` defaults to
`use_cuda=True` and selects `dev = "cuda"` whenever CUDA is present, while most
tests call it without a device argument. The same commit therefore gives 387
passed / 0 skipped on the CPU workstation and 340 passed / 19 failed on the
A6000 box. The green CPU run does not prove the GPU path works — it proves the
GPU branch was never executed. Zero skips currently hide this by omission, not
by design.

After T-08-01 the *outcome* is machine-independent (green on both), while
*coverage* remains deliberately machine-dependent: the fixture runs `cpu` here
and `cuda:0` there. The fake-tensor/stub tests are deterministic everywhere and
are what actually pin the conversion contract.

**Parity-test caveat (must be resolved before writing the parity test):**

A CPU/GPU parity test that calls the CPU path inside the GPU env assumes both
kernels work in the same environment. Error #2 shows a GPU-built
`libparallelproj` can reject CPU input outright (`cudaSetDevice failed`), so
such a test would fail on exactly the machine we want to verify, regardless of
the projector fix. Step 1's fallback policy decides this:

- If the chosen GPU build also runs CPU input, compute both paths in-env and
  compare with the measured tolerance.
- If it cannot, compare the device result against a small checked-in synthetic
  reference projection produced in the validated CPU env. Do not invoke the
  broken CPU path in the GPU env and do not add a skip guard.
6. **Scripts and docs.** `scripts/verify_forward_projection.py` and
   `scripts/forward_projection_plot.py` get an optional `--cuda` flag (default
   off). `INSTALLATION.md` drops the known-limitation block and the "CUDA is not
   validated by tests" note. Audit finding #1 becomes `fixed` only after a real
   GPU run.

## Risks / open questions

- Which tensor type parallelproj 1.x accepts for LOR coordinates in its CUDA
  build must be confirmed on the GPU machine before settling helper signatures.
- CUDA LOR lists are large; the existing chunking bounds them to 32 projections,
  but peak VRAM must be measured on the A6000.
- CPU/CUDA kernels are not expected to be bit-identical; tolerance needs to be
  chosen from measurements, not guessed.
- A Python 3.11 + CUDA build of `parallelproj`/`libparallelproj`/`pytorch` with
  matching CUDA major is still required; see INSTALLATION.md "GPU setup".
- The CPU fallback in a GPU-built env is broken independently of the projector
  fix (error #2); hiding devices with `CUDA_VISIBLE_DEVICES=""` is not a fix.
- Consequently a same-env CPU/GPU parity test may be impossible on a GPU build;
  the fallback-policy decision in step 1 must say whether parity uses an in-env
  CPU call or a checked-in reference from the CPU env. Both options keep zero
  skips; only the second works when the GPU build cannot do CPU.

## Acceptance

- `forward_project(..., use_cuda=True)` completes on a GPU env without the
  numpy/CUDA TypeError; results match the CPU reference (in-env or checked-in,
  per the step 1 fallback policy) within a documented float32 tolerance.
- Suite is green with zero skips on both the CPU-only and GPU machines; the
  device fixture changes which path runs, not whether tests pass. CPU test count
  only grows by the new tests, and no old test changes its expected result.
- The default and the unchecked CUDA checkbox are both exercised on the GPU
  machine; neither crashes, or the unsupported combination fails with a clear
  message.
- Real browser check on a GPU machine: forward projection with the checkbox on
  produces a non-zero projection.
- Docs: INSTALLATION.md no longer describes the GPU path as broken, audit #1 is
  `fixed`, AGENTS.md test bar updated if the suite count changed.
