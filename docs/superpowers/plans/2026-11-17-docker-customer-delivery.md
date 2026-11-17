# Docker Customer Delivery — Plan

**Date:** 2026-11-17
**Tasks:** T-73 (build + verify), T-105 (publish), T-74 (run script)
**Guide:** `docs/customer-docker-guide.md`
**Image:** `Dockerfile` targets `slim` (default) and `full` (customer image)

## Goal

A customer receives one image (`ctbeamstudio:full`), loads it, mounts a DICOM
folder read-only, and works — with no Python, no conda and no network. Verified
on a real machine, not assumed.

## Current state (2026-11-17, updated during T-106)

- `Dockerfile` has both targets; `full` installs conda-forge `parallelproj` via
  micromamba at build time and fails the build if
  `backend.forward_project.PARALLELPROJ_AVAILABLE` is not `True`.
- **Docker IS installed on this workstation** (CLI 29.9.2, Docker Desktop) —
  the note below predates the install.
- Step 2 (slim) is done and verified: health `ok`, `PARALLELPROJ_AVAILABLE ==
  False`, measured size **1.43 GiB** — the "well under 400 MiB" expectation
  was unreachable (viewer deps alone are ~790 MB installed: streamlit→pyarrow
  170 MB, scipy 143 MB, pandas 79 MB, plotly 64 MB). The size criterion is
  superseded by the versioning plan: only `full` is published; slim stays a
  local target. All docs now say ~1.43 GB.
- Images/containers/tarballs are named `ctbeamstudio` (T-106); this file's
  commands were updated accordingly.
- CI has no Docker push job yet (T-105). `release.yml` (T-106) covers the
  `v*.*.*` release path; the push-on-main/PR job from T-105 is still open.

## Steps

### 1. Install Docker (one-time, needs admin)

```powershell
winget install --id Docker.DockerDesktop -e
```

Then start Docker Desktop once and wait until `docker info` answers. WSL2 is
required (Docker Desktop offers to install it on first start).

> Docker Desktop licensing: free for personal use and for companies under the
> revenue/employee thresholds; larger companies need a paid subscription.
> Docker Engine on Linux has no such restriction.

### 2. Build and verify `slim` (fast — do this first)

```powershell
docker build -t ctbeamstudio:slim --target slim .
docker run -d --name ctbeamstudio-slim -p 8501:8501 ctbeamstudio:slim
Start-Sleep -Seconds 15
(Invoke-WebRequest http://localhost:8501/_stcore/health -UseBasicParsing).Content
docker exec ctbeamstudio-slim python -c "from backend.forward_project import PARALLELPROJ_AVAILABLE as a; print('slim projection backend:', a)"
docker image inspect ctbeamstudio:slim --format "{{.Size}}"
docker rm -f ctbeamstudio-slim
```

Expect: health endpoint returns `ok`, `slim projection backend: False`,
size well under 400 MiB (T-40/T-73 budget).

### 3. Build and verify `full` (the customer image)

```powershell
docker build -t ctbeamstudio:full --target full .
docker image inspect ctbeamstudio:full --format "{{.Size}}"
docker run -d --name ctbeamstudio -p 8501:8501 `
  -v "C:\data\ct:/data:ro" `
  -v ctbeamstudio-cache:/app/data `
  ctbeamstudio:full
Start-Sleep -Seconds 20
(Invoke-WebRequest http://localhost:8501/_stcore/health -UseBasicParsing).Content
docker exec ctbeamstudio python -c "import parallelproj, torch; print('cuda:', parallelproj.cuda_present, '| torch:', torch.__version__)"
docker exec ctbeamstudio python -c "from backend.forward_project import PARALLELPROJ_AVAILABLE as a; assert a, 'backend does not see parallelproj'; print('full projection backend: True')"
docker logs --tail 30 ctbeamstudio
```

Expect: health `ok`, `cuda: False`, `torch: 2.x.x+cpu`,
`full projection backend: True`, no traceback in the logs.

Then, in the browser at <http://localhost:8501>, enter `/data/<study>` as the
DICOM folder and run one forward projection on a small volume. That is the
check the smoke tests cannot do: a real projection instead of zeros.

### 4. Export for the customer

```powershell
docker save ctbeamstudio:full -o ctbeamstudio-full.tar
```

The tarball is > 1.6 GB. Ship it together with
`docs/customer-docker-guide.md`.

### 5. Publish (T-105, after step 3 passes)

Add a CI job that builds `--target full`, starts it, waits for
`/_stcore/health`, runs the two `PARALLELPROJ_AVAILABLE` checks, and pushes to
GHCR on `main` and on tags. Until then the customer path is the tarball.

### 6. Close the ledger

- `docs/plan.md`: T-73 → Done with measured sizes and timings; T-105 → Done
  once the push job runs; T-74 → Done once `scripts/run-docker.ps1` has been
  used against a real folder.
- `AGENTS.md`: no test-bar change expected (no Python touched).

## Acceptance

- [x] `docker build .` (default = `slim`) succeeds and the container answers on
      `/_stcore/health`. (Step 2, 2026-11-17)
- [x] `:slim` reports `PARALLELPROJ_AVAILABLE == False`. Size: **1.43 GiB**,
      not under 400 MiB — see Current state; criterion superseded by T-106
      (slim is never published).
- [ ] `--target full` succeeds; `PARALLELPROJ_AVAILABLE == True`; `cuda_present
      == False`; container answers on `/_stcore/health`.
- [ ] One real forward projection in the browser returns a non-zero projection.
- [ ] Mounted DICOM folder is readable, and nothing is written into it (`:ro`).
- [ ] `ctbeamstudio-full.tar` loads on a second machine and starts there.

## Risks

| Risk | Mitigation |
|---|---|
| micromamba URL oder conda-Solver ändert sich | `latest` ist ungepinnt; bei Bedarf auf feste Version pinnen |
| torch-CPU-Wheel erwartet `libgomp1` | im `full`-Target installiert |
| conda-Env-NumPy vs. Wheel-NumPy | absichtlich ein einziges Python im Image (kein `PYTHONPATH`-Mischen) |
| Named volume `/app/data` root-owned | `/app/data` wird im Image angelegt und `appuser` gehört |
| Windows-Dateifreigabe fehlt in Docker Desktop | Settings → Resources → File sharing |
| Image > 1.6 GB per Tarball | alternativ GHCR (T-105) |
