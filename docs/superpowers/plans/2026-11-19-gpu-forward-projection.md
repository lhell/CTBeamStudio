# Implement GPU forward projection — plan

Date: 2026-11-19
Ledger task: T-08-01
Design: [2026-11-19-gpu-forward-projection-design.md](../specs/2026-11-19-gpu-forward-projection-design.md)

Prerequisite: a working CUDA conda env built as described in `INSTALLATION.md`
("GPU setup"), with Python 3.11 and a matched `parallelproj` /
`libparallelproj` **1.10.x** pair. The earlier 1.3.x pin was wrong — those
builds do not provide `parallelproj.projectors`; 2.x would force Python 3.12 and
is not the validated baseline. Without a GPU device, steps 5 and 6 can only be
prepared, not verified.

Status of that prerequisite (2026-11-19): a fresh 1.10.2 / `libparallelproj
1.10.2=cuda129` env on 8× RTX A6000 installs and imports cleanly (`projectors`,
`operators`, `backend.parallelproj`; 8 devices). Before the fix the suite there
was **370 passed / 20 failed / 0 skipped**, all the same `projector.py:83`
crash; after T-08-01 it is **398 passed / 0 skipped** (step 5).

Suite-machine dependence: before the fix the suite was green on CPU and red on
GPU because `forward_project` selected CUDA from `torch.cuda.is_available()`
while most tests omit the device argument. The fix makes it green with zero
skips on both machines; the device fixture changes *which* path each test
exercises, not whether it passes. Real CUDA kernel execution stays a manual
verification gate (step 5, now passed), by precedent with browser-only checks
(T-109, T-83).

## Evidence to reproduce first

The 2026-11-19 error report (recorded in the design spec) found three failures
on 8× RTX A6000, Python 3.12.16, `parallelproj 2.0.2` + `libparallelproj 2.0.7
(cuda130)`, `pytorch 2.14.1 (cuda134)`, `cuda-toolkit 13.5`:

1. `projector.py:82-88` — `np.asarray(pos_beam_start)` on a CUDA tensor →
   `TypeError: can't convert cuda:0 device type tensor to numpy`. The existing
   `_as_numpy_xyz` helper is never called.
2. GPU-built operator `_apply` via `ConeBeamProjector.apply` — even with
   `CUDA_VISIBLE_DEVICES=""`, CPU numpy input crashes with
   `RuntimeError: cudaSetDevice failed: no CUDA-capable device is detected`.
   Hiding CUDA devices is **not** a workaround. Suite then: 23 failed /
   336 passed (vs 19 failed / 340 passed with GPUs visible).
3. `forward_project()` defaults to `use_cuda=True`, so the crash above reaches
   the tests: 19 failures spanning `test_ui_smoke.py` (1),
   `test_dummy_measurement.py` (14), `test_forward_project.py` (6).

## Steps

1. **[x] Confirm the upstream contract.** Done by reading the installed 1.10.2
   source, which is more precise than one run:
   `parallelproj.backend.joseph3d_fwd` dispatches on the *image* array. Host
   numpy takes the hybrid route (CUDA library when devices are visible, OpenMP
   otherwise); a CUDA torch image needs `cupy`. Feeding host numpy therefore
   runs on a GPU build without cupy. `CUDA_VISIBLE_DEVICES=""` should fall back
   to OpenMP because the device count becomes 0 — source-verified, empirical
   check in step 5.
2. **[x] Introduce the conversion helpers in
   `src/backend/parallelproj/projector.py`.** `_as_host_array`,
   `_to_operator_input` and `_from_operator_output`; `__init__`, `apply` and
   `adjoint` use only those. Every bare `np.asarray` on a possibly-CUDA tensor
   is gone. Numpy output shape/order and CPU numbers are unchanged.
3. **[x] Thread the device through `src/backend/forward_project.py`.** `dev`
   still selects where the LOR geometry is built; the volume intentionally stays
   host numpy because parallelproj's hybrid route copies it to the devices
   itself. Chunking, z/helix centring and the progress callback are untouched.
   No `device` argument on `ConeBeamProjector`: with host numpy input it would be
   unused.
4. **[x] Add tests without adding skips.** Four tests in
   `tests/unit/test_parallelproj.py`: fake device tensor with a raising
   `__array__`, `_from_operator_output`, a stubbed `ListmodePETProjector`, and
   an available-device LOR comparison. `python -m pytest -q -rs` in `ct-viewer`:
   398 passed, 0 skipped with Git Bash (without it, the 4 `test_release_push`
   cases fail as documented on Windows).
5. **[x] Verify on the real GPU machine.** 2026-11-19, 8× RTX A6000, fresh
   py3.11.18 + `parallelproj 1.10.2` + `libparallelproj 1.10.2=cuda129` +
   `pytorch 2.9.1=cuda129` env at commit `d184122`:
   - Suite: **398 passed / 0 skipped** (~25.6 s). With
     `CUDA_VISIBLE_DEVICES=""`: **398 passed / 0 skipped** (~15.5 s), which
     confirms the OpenMP fallback and closes the error #2 question for 1.10.2.
   - Peak VRAM for a full-geometry `(60, 192, 512)` projection: **36.8 MB**
     (`torch.cuda.max_memory_allocated`) / **386 MB** (`nvidia-smi` delta).
   - Checkbox check via the projection API: `use_cuda=True` and `False` produce
     bit-identical, non-zero, finite projections (sum 20.4678, max 0.09999).
     The Streamlit server on that machine served the fixed code and projected
     successfully.
6. **[x] Update the scripts and docs.**
   - `scripts/verify_forward_projection.py`, `scripts/forward_projection_plot.py`:
     auto-select CUDA, `--cpu` override, print the chosen LOR device and the CUDA
     device count parallelproj sees.
   - `INSTALLATION.md`, audit finding #1 and the `AGENTS.md` test bar now record
     the verified state: GPU status is "verified", finding #1 is `fixed`, and
     the suite baseline is 398.

## Done when

All steps complete, both CPU and GPU runs report zero skips, CPU numbers are
unchanged, GPU results match CPU within the measured tolerance, the unchecked
CUDA path is safe, and the ledger status records the manual GPU/browser
verification with date and device.
