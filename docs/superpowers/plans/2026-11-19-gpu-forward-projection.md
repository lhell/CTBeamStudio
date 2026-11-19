# Implement GPU forward projection — plan

Date: 2026-11-19
Ledger task: T-08-01
Design: [2026-11-19-gpu-forward-projection-design.md](../specs/2026-11-19-gpu-forward-projection-design.md)

Prerequisite: a working CUDA conda env built as described in `INSTALLATION.md`
("GPU setup"), with Python 3.11 and a matched `parallelproj`/`libparallelproj`
1.x pair. Without a GPU device, steps 5 and 6 can only be prepared, not verified.

Suite-machine dependence: the current suite is green on CPU and red on GPU
because `forward_project` selects CUDA from `torch.cuda.is_available()` while
most tests omit the device argument. The goal is a green, zero-skip suite on
both machines; the device fixture changes *which* path each test exercises, not
whether it passes. Real CUDA kernel execution stays a manual verification gate
(step 5), by precedent with browser-only checks (T-109, T-83).

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

1. **Confirm the upstream contract on the GPU machine.**
   - Inspect the installed `parallelproj` 1.x `ListmodePETProjector`: which
     input types (numpy vs torch CPU vs torch CUDA) it accepts, and what type
     `__call__`/`adjoint` return for each.
   - Run a minimal 1-projection call with CUDA LOR coordinates and record the
     outcome here before changing the projector. Repeat with CPU input to
     establish whether error #2 also applies to the 1.x build.
   - Decide the CPU-fallback policy for a GPU-built env (install a CPU-capable
     `libparallelproj`, or fail with an explicit message). This also fixes the
     parity-test question below: can the GPU build run CPU input in the same
     env, or must the reference come from the validated CPU env? Record the
     decision here before step 4 is written.

2. **Introduce the conversion helpers in `src/backend/parallelproj/projector.py`.**
   - Replace `_as_numpy_xyz` with `_to_operator_input` / `_from_operator_output`.
   - `__init__`, `apply` and `adjoint` use only those helpers; remove every bare
     `np.asarray(...)` on tensors that can live on CUDA.
   - Keep numpy output shape/order and CPU numbers identical.

3. **Thread the device through `src/backend/forward_project.py`.**
   - `ConeBeamProjector(..., device=dev)`; place the volume on `dev` once before
     the chunk loop.
   - Keep `dev = "cuda" if torch.cuda.is_available() and use_cuda else "cpu"`,
     the 32-projection chunking, z/helix centring, and the progress callback.
   - Return `projections` as a CPU numpy array as today.

4. **Add tests without adding skips.**
   - `tests/unit/test_parallelproj.py`: helper tests with a fake CUDA tensor
     that raises on implicit numpy conversion; device fixture selects `cuda:0`
     when available, `cpu` otherwise.
   - `tests/unit/test_forward_project.py`: device-vs-reference parity with a
     measured tolerance; keep existing CPU cases unchanged. Do **not** call the
     CPU path inside a GPU env unless step 1 confirmed it works there — error
     #2 makes that test fail on the target machine otherwise. If the GPU build
     cannot do CPU, use a small checked-in synthetic reference projection
     produced in the validated CPU env and compare the device result to it.
     Either way: zero skips, no conditional assertions on CUDA presence.
   - `tests/integration/test_projection_workflow.py`: one end-to-end flow on
     the selected device (chunked run + progress).
   - `tests/integration/test_ui_smoke.py` and `tests/test_dummy_measurement.py`:
     update the 15 cases named in the error report so the default `use_cuda=True`
     no longer crashes on GPU.
   - Run in the conda env: `python -m pytest -q -rs` — must report no skips.

5. **Verify on the real GPU machine.**
   - Suite in the GPU env (zero skips), plus a run with `CUDA_VISIBLE_DEVICES=""`
     to check error #2 did not reappear under the chosen fallback policy.
   - Peak VRAM during a full-geometry run.
   - Streamlit: `Use CUDA if available` on → non-zero projection; off → either
     a working CPU projection or an explicit unsupported-build message, never
     a `cudaSetDevice` crash. Record output sums and device in the ledger status.

6. **Update the scripts and docs after verification passes.**
   - `scripts/verify_forward_projection.py`, `scripts/forward_projection_plot.py`:
     optional `--cuda` flag, default off.
   - `INSTALLATION.md`: remove the known-limitation blockquote and rewrite the
     "CUDA in the test suite and helper scripts" note to match the new state,
     including the `CUDA_VISIBLE_DEVICES` finding.
   - `docs/audit-2026-11-13-findings.md` finding 1 → `fixed`.
   - `AGENTS.md` test bar: new total if the suite count changed.

## Done when

All steps complete, both CPU and GPU runs report zero skips, CPU numbers are
unchanged, GPU results match CPU within the measured tolerance, the unchecked
CUDA path is safe, and the ledger status records the manual GPU/browser
verification with date and device.
