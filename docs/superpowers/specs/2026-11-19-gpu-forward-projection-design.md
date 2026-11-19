# GPU forward projection — design

Date: 2026-11-19
Ledger task: T-08-01
Status: implemented and verified on CPU (2026-11-19) and on 8× RTX A6000
(2026-11-19); 398 passed, 0 skipped on both.

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
  `parallelproj` **1.10.x** / matching `libparallelproj` 1.10.x. Python 3.11 on
  the CPU baseline; 3.12 is acceptable on a GPU env when the GPU PyTorch build
  requires it, provided `parallelproj` stays 1.10.x (1.10.x supports >= 3.10).
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

**Dependency deadlock — resolved 19 Nov 2026:** the old plan
`docs/superpowers/plans/2026-10-27-parallelproj-forward-projection.md` specifies
Python ≥ 3.12 and `cuda-toolkit=12.1`, while `AGENTS.md` /
`docs/local-environment.md` specify Python 3.11, CPU-only as the validated
baseline (359 passed, 0 skipped at the time of the report; 390 now). A CUDA path
was documented but untested by design ("Cannot be tested on this machine (no
CUDA)", audit finding #1).

The apparent deadlock — "py3.11 + parallelproj 1.3.5 cannot import; the app
needs 2.x, which has no py3.11 builds" — was caused by a **wrong pin in
`INSTALLATION.md`**, not by the dependencies. Verified in the local `ct-viewer`
env on 19 Nov 2026:

- installed: Python **3.11.18**, `parallelproj` **1.10.2**,
  `libparallelproj` **1.10.2** (cpu), torch 2.10.0 (cpu);
- `from parallelproj.projectors import ListmodePETProjector` and
  `import backend.parallelproj` both succeed.

conda-forge indeed has `parallelproj` 2.0.x only for Python >= 3.12, so 2.x does
force a py3.12 env (the deleted GPU env). It is **not** required: 1.10.x also
ships CUDA library builds (`cuda129*`, `cuda130*`). `environment.yml` and
`INSTALLATION.md` now pin the 1.10.x pair. The green baseline is 390 passed /
0 skipped; four extra local failures in `test_release_push.py` are the known
missing-`bash` environment issue documented in `AGENTS.md`, not a regression.

### GPU install verified with 1.10.2 (2026-11-19)

A fresh `ct-viewer` built by the corrected `INSTALLATION.md` on the 8× RTX A6000
Linux machine (commit `14917ea`) installs and imports cleanly:

| Package | Version / build |
|---|---|
| python | 3.11.18 |
| parallelproj | 1.10.2 `pyha770c72_203` |
| libparallelproj | 1.10.2 `cuda129_h897a41e_203` (matched pair) |
| pytorch | 2.9.1 `cuda129_generic_py311_hc138829_205` |
| cuda-toolkit | 12.9.2 |

Driver 615.71.10, CUDA UMD 13.4. `projectors`, `operators`,
`backend.parallelproj` import; `torch.cuda.is_available()` is True and
`device_count()` is 8. The solver first picked `libparallelproj cuda130` and
re-mixed it to `cuda129` when the GPU pytorch build joined the same solve — the
final pair is matched, as the guide requires.

Suite on that env: **370 passed / 20 failed / 0 skipped** (23.9 s), same
`projector.py:83` traceback as the 2.0.2 run. So the install guide is validated;
the remaining failure is exactly T-08-01's code bug. The 1.10.2 CUDA build was
**not** re-tested with `CUDA_VISIBLE_DEVICES=""` at that point, so error #2's
CPU-fallback behaviour was open for this pair; after the fix the empty-variable
run gave 398 passed / 0 skipped, i.e. the OpenMP fallback works (see
Acceptance).

## Implementation (as built, 2026-11-19)

The installed `parallelproj` 1.10.2 source settled the contract the plan wanted
to measure on the GPU box (`parallelproj/backend.py`, `joseph3d_fwd`):

- the **image** array decides the kernel, not the LOR tensors;
- a **host numpy image** takes the hybrid route: the CUDA library copies it to
  the visible devices and runs the CUDA kernels when the build has them,
  otherwise the OpenMP library runs;
- a **CUDA torch/cupy image** takes the raw cupy kernels, which requires `cupy`
  and a CUDA kernel file.

So the CUDA route for this app is hybrid mode, not CUDA torch tensors. That
needs no `cupy`, no CUDA tensors and no device plumbing for the volume.

1. **One conversion boundary** in `src/backend/parallelproj/projector.py`:
   `_as_host_array`, `_to_operator_input` and `_from_operator_output`. Torch
   tensors are always consumed with `.detach().cpu().numpy()`, so `np.asarray`
   never sees a device tensor. `__init__`, `apply` and `adjoint` use only these
   helpers, which removes the audit's `projector.py:83` crash at its source.
   Inputs stay float32/C-contiguous and the reshape is unchanged, so CPU numbers
   do not move.
2. **No `device` argument on `ConeBeamProjector`.** The original plan added one;
   with host numpy input it would be unused, and an unused flag is worse than
   none. `forward_project` still chooses `dev` for LOR generation only.
3. **Volume placement.** The volume stays a host numpy array. Sending it as a
   CUDA tensor would force the cupy path; parallelproj's hybrid route performs
   the host-to-device copy itself. Chunking (32 projections), helix centring,
   the progress callback and the CPU numpy return value are untouched.
4. **Upstream adapter.** `ListmodePETProjector` is still built in exactly one
   place (`ConeBeamProjector.__init__`), so a later 2.x migration stays local.
5. **Tests: 4 added, zero skips** (`tests/unit/test_parallelproj.py`):
   - a fake device tensor whose `__array__` raises (the exact CUDA failure),
     asserting `_to_operator_input` takes the explicit host-copy route;
   - `_from_operator_output` returning host numpy;
   - a stubbed `ListmodePETProjector`, asserting `__init__`, `apply` and
     `adjoint` all receive numpy;
   - `_available_device()` returns `cuda:0` when present and `cpu` otherwise;
     the test builds LORs on that device and compares the projection with
     CPU-built LORs. Here it runs the CPU path; on the A6000 it exercises the
     CUDA LOR boundary that used to raise.
   The fake-tensor and stub tests are deterministic everywhere and are what
   actually pin the contract.
6. **Scripts and UI.** `scripts/verify_forward_projection.py` and
   `scripts/forward_projection_plot.py` auto-select CUDA and accept `--cpu`;
   both print the chosen LOR device and the CUDA device count parallelproj sees.
   The checkbox help text now says it controls LOR geometry only, because the
   kernel is chosen by the installed parallelproj build.

**CPU fallback in a GPU-built env.** In 1.10.2 `num_visible_cuda_devices` comes
from the CUDA library's device count and respects `CUDA_VISIBLE_DEVICES`. With
the variable empty the count is 0, so a numpy image takes the OpenMP path; the
package also ships the CPU library, so `import parallelproj` still resolves
`lib_parallelproj_c_fname`. Error #2 therefore does not apply to 1.10.2, and
the A6000 run with `CUDA_VISIBLE_DEVICES=""` confirmed it (398 passed / 0
skipped).

**Why the tests pass on a machine without a GPU, with zero skips:**

- A helper returns `cuda:0` when `torch.cuda.is_available()` and `cpu`
  otherwise. Every test runs on whichever device exists; nothing is skipped and
  no test asserts CUDA is present.
- The CUDA-specific conversion logic is covered with a fake tensor whose
  `__array__` raises and whose `.detach().cpu()` yields a plain array. Combined
  with a stubbed `ListmodePETProjector`, this proves the host-copy contract
  without CUDA hardware.
- The numerical assertions (four-region geometry, non-contiguous indices,
  helix, progress) run on real data and keep their CPU expectations.
- What cannot be automated here is real CUDA kernel execution: no test can run
  actual CUDA kernels and also pass on this CPU-only workstation without a
  skip. That stays a manual GPU run recorded in the ledger, following the
  precedent for browser-only checks (T-109, T-83).

**Machine dependence of the suite.** Before the fix the outcome was
machine-dependent (green here, 20 red on the A6000) because the CUDA branch was
never executed on this workstation. With the boundary moved to host numpy the
*outcome* is machine-independent: the same code runs on both machines, and the
available-device test changes only *which* LOR path is exercised. Kernel
execution remains deliberately machine-dependent and manual.

## Risks / open questions

- CUDA LOR lists are large; the existing chunking bounds them to 32 projections.
  Measured peak for a full-geometry `(60, 192, 512)` projection: 36.8 MB by
  `torch.cuda.max_memory_allocated`, 386 MB by `nvidia-smi`.
- CPU/CUDA kernels are not expected to be bit-identical, but for this build they
  were: `use_cuda=True`/`False` gave identical output (sum 20.4678, max 0.09999).
  Keep the tolerance, do not assert bit equality in a test.
- A Python 3.11 + `parallelproj` 1.10.2 CUDA build of
  `parallelproj`/`libparallelproj`/`pytorch` with matching CUDA generation is
  required; see INSTALLATION.md "GPU setup". Do not fall back to 1.3.x or 2.x
  to get a CUDA build.
- The checkbox no longer forces CPU in a CUDA-capable build; parallelproj
  chooses the kernel. Running a GPU build on the CPU requires hiding the
  devices before process start (`CUDA_VISIBLE_DEVICES=""`); verified on 1.10.2
  (suite 398 passed, 0 skipped under the empty variable).

## Acceptance

- [x] `np.asarray` on a device tensor is gone; fake-tensor and stub tests pin
  the host-copy boundary (CPU suite green, zero skips).
- [x] CPU numbers unchanged: the existing projection, helix, progress and
  selection tests pass without edits to their expectations.
- [x] Suite: **398 passed, 0 skipped** on the CPU env (the four
  `test_release_push` cases need Git Bash; on Windows without it they fail as
  documented) and **398 passed, 0 skipped** on the A6000 GPU env.
- [x] Scripts auto-select and print the device; `--cpu` overrides.
- [x] `forward_project(..., use_cuda=True)` completes on the A6000 without the
  numpy/CUDA TypeError; its output is non-zero, finite and identical to the CPU
  path (sum 20.4678, max 0.09999).
- [x] GPU suite green with zero skips, including a `CUDA_VISIBLE_DEVICES=""`
  run (398 / 0), which closes the error #2 question for 1.10.2.
- [x] GPU-side check of the checkbox: on and off both produce a non-zero
  projection through the Streamlit process serving the fixed code.
- [x] `INSTALLATION.md` records the verified state and audit #1 is `fixed`.
