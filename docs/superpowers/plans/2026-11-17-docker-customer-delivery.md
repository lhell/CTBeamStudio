# Docker Customer Delivery — Plan

**Date:** 2026-11-17
**Tasks:** T-73 (build + verify), T-105 (publish), T-74 (run script)
**Guide:** `docs/customer-docker-guide.md`
**Image:** `Dockerfile` targets `slim` (default) and `full` (customer image)

## Goal

A customer receives one image (`ct-viewer:full`), loads it, mounts a DICOM
folder read-only, and works — with no Python, no conda and no network. Verified
on a real machine, not assumed.

## Current state (2026-11-17)

- `Dockerfile` has both targets; `full` installs conda-forge `parallelproj` via
  micromamba at build time and fails the build if
  `backend.forward_project.PARALLELPROJ_AVAILABLE` is not `True`.
- Nothing has been built: Docker is not installed on the workstation
  (`docker` not found, no `com.docker.service`, `winget` available).
- CI has no Docker job (T-73) and no registry push (T-105). `ci.yml` contains
  only data-guard, lint and tests.

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
docker build -t ct-viewer:slim --target slim .
docker run -d --name ct-viewer-slim -p 8501:8501 ct-viewer:slim
Start-Sleep -Seconds 15
(Invoke-WebRequest http://localhost:8501/_stcore/health -UseBasicParsing).Content
docker exec ct-viewer-slim python -c "from backend.forward_project import PARALLELPROJ_AVAILABLE as a; print('slim projection backend:', a)"
docker image inspect ct-viewer:slim --format "{{.Size}}"
docker rm -f ct-viewer-slim
```

Expect: health endpoint returns `ok`, `slim projection backend: False`,
size well under 400 MiB (T-40/T-73 budget).

### 3. Build and verify `full` (the customer image)

```powershell
docker build -t ct-viewer:full --target full .
docker image inspect ct-viewer:full --format "{{.Size}}"
docker run -d --name ct-viewer -p 8501:8501 `
  -v "C:\data\ct:/data:ro" `
  -v ct-viewer-cache:/app/data `
  ct-viewer:full
Start-Sleep -Seconds 20
(Invoke-WebRequest http://localhost:8501/_stcore/health -UseBasicParsing).Content
docker exec ct-viewer python -c "import parallelproj, torch; print('cuda:', parallelproj.cuda_present, '| torch:', torch.__version__)"
docker exec ct-viewer python -c "from backend.forward_project import PARALLELPROJ_AVAILABLE as a; assert a, 'backend does not see parallelproj'; print('full projection backend: True')"
docker logs --tail 30 ct-viewer
```

Expect: health `ok`, `cuda: False`, `torch: 2.x.x+cpu`,
`full projection backend: True`, no traceback in the logs.

Then, in the browser at <http://localhost:8501>, enter `/data/<study>` as the
DICOM folder and run one forward projection on a small volume. That is the
check the smoke tests cannot do: a real projection instead of zeros.

### 4. Export for the customer

```powershell
docker save ct-viewer:full -o ct-viewer-full.tar
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

- [ ] `docker build .` (default = `slim`) succeeds and the container answers on
      `/_stcore/health`.
- [ ] `:slim` reports `PARALLELPROJ_AVAILABLE == False` and stays under 400 MiB.
- [ ] `--target full` succeeds; `PARALLELPROJ_AVAILABLE == True`; `cuda_present
      == False`; container answers on `/_stcore/health`.
- [ ] One real forward projection in the browser returns a non-zero projection.
- [ ] Mounted DICOM folder is readable, and nothing is written into it (`:ro`).
- [ ] `ct-viewer-full.tar` loads on a second machine and starts there.

## Risks

| Risk | Mitigation |
|---|---|
| micromamba URL oder conda-Solver ändert sich | `latest` ist ungepinnt; bei Bedarf auf feste Version pinnen |
| torch-CPU-Wheel erwartet `libgomp1` | im `full`-Target installiert |
| conda-Env-NumPy vs. Wheel-NumPy | absichtlich ein einziges Python im Image (kein `PYTHONPATH`-Mischen) |
| Named volume `/app/data` root-owned | `/app/data` wird im Image angelegt und `appuser` gehört |
| Windows-Dateifreigabe fehlt in Docker Desktop | Settings → Resources → File sharing |
| Image > 1.6 GB per Tarball | alternativ GHCR (T-105) |
