# Image Naming and Release Versioning — Plan

**Date:** 2026-11-17
**Tasks:** T-106 (rename + release automation); builds on T-73 and T-105
**Contract:** `docs/versioning.md` (rules), this file (the work)
**Decision (2026-11-17):** the image is called **`ctbeamstudio`**, not `ct-viewer`.

## Goal

One unambiguous answer to "which image is release 1.0.0?", plus a release
procedure that a CI job can run without a human retyping tags.

## 1. What gets renamed — and what does not

The string `ct-viewer` means three different things in this repo. Only the
container artifact is renamed:

| Thing | Name after this task | Touched? |
|---|---|---|
| Docker image / GHCR package | `ctbeamstudio` | **renamed** |
| Container name (`--name`) | `ctbeamstudio` | **renamed** |
| Cache volume | `ctbeamstudio-cache` | **renamed** |
| Offline tarball | `ctbeamstudio-1.0.0-full.tar` | **renamed** |
| conda env (`environment.yml`, CI, AGENTS.md, `docs/local-environment.md`) | `ct-viewer` | unchanged |
| Python distribution (`pyproject.toml [project] name`) | `ct-viewer` | unchanged |
| Repository directory | `CTOrientationViewer` | unchanged |

Renaming the conda env or the distribution would break every documented command
and the `parallelproj_c.dll` path notes for zero benefit. Files to touch, all
`ct-viewer:` / `--name ct-viewer` / `ct-viewer-cache` / `ct-viewer-*.tar`
occurrences only:

- `Dockerfile` (header comment)
- `README.md` (Docker quick start)
- `INSTALLATION.md` (Docker sections only — conda sections keep `ct-viewer`)
- `docs/versioning.md`
- `docs/customer-docker-guide.md`
- `docs/superpowers/plans/2026-11-17-docker-customer-delivery.md`
- `scripts/run-docker.sh`, `scripts/run-docker.ps1`

## 2. Tag scheme

Version axis from `docs/versioning.md` §1 (git `v1.0.0`, Docker `1.0.0`,
`pyproject.toml` `1.0.0`). Variant axis added because one commit builds two
images:

| Tag | Variant | Rule |
|---|---|---|
| `1.0.0` | `full` | immutable release identity |
| `1.0` | `full` | moving minor alias |
| `latest` | `full` | moving, never deployed |
| `dev`, `sha-a1b2c3d` | `full` | development builds |
| `1.0.0-slim` | `slim` | only if slim is ever published |

Invariants:

- A bare version tag always means `full`. `slim` cannot forward-project, so it
  must never be reachable through `latest` or a plain version.
- No `v` prefix in Docker tags (`v1.0.0` is git spelling only).
- No SemVer build metadata in tags (`+build.7` is not a legal tag character
  set) — that goes into an OCI label.
- Version tags are never repointed; a mistake means a patch bump.

Only `full` is published for now: `slim` stays a local build target until
someone has a real use for it.

## 3. Registry identity

```
ghcr.io/lhell/ctbeamstudio
```

- Package visibility **public**, or the customer needs a GitHub PAT to pull —
  which contradicts "no account, no network".
- Immutable tags enabled in the package settings, so a second push to `1.0.0`
  fails instead of silently replacing the image.
- Deploy and document by digest (`ctbeamstudio@sha256:...`), not by tag.

## 4. Release procedure (manual, until the workflow exists)

```powershell
git status                                   # clean tree, no dirty build
# pyproject.toml version == 1.0.0, tag v1.0.0
git tag -a v1.0.0 -m "CTBeamStudio 1.0.0"
git push origin main --follow-tags

docker build `
  -t ctbeamstudio:1.0.0 `
  -t ctbeamstudio:1.0 `
  -t ctbeamstudio:latest `
  --target full `
  --label org.opencontainers.image.title=ctbeamstudio `
  --label org.opencontainers.image.version=1.0.0 `
  --label org.opencontainers.image.revision=$(git rev-parse HEAD) `
  --label org.opencontainers.image.source=https://github.com/lhell/CTBeamStudio `
  --label com.ctbeamstudio.variant=full `
  .

docker tag ctbeamstudio:1.0.0 ghcr.io/lhell/ctbeamstudio:1.0.0
docker push ghcr.io/lhell/ctbeamstudio:1.0.0
docker push ghcr.io/lhell/ctbeamstudio:1.0
docker push ghcr.io/lhell/ctbeamstudio:latest
docker inspect --format='{{index .RepoDigests 0}}' ctbeamstudio:1.0.0
```

Record the digest in the GitHub Release. Two published variants would mean two
digests per release; the variant label is what tells them apart, because
`1.0.0` no longer can.

Offline route for customers, versioned with the same number:

```powershell
docker save ctbeamstudio:1.0.0 -o ctbeamstudio-1.0.0-full.tar
```

## 5. Automate the lockstep

`.github/workflows/release.yml`, triggered on `v*.*.*`:

1. check out the tagged commit,
2. fail if `pyproject.toml` version differs from the tag without `v`,
3. build `--target full` (after T-73 has verified the image builds at all),
4. push `X.Y.Z`, `X.Y` and `latest` with the labels above,
5. create the GitHub Release containing the digest,
6. upload the `docker save` tarball as a release asset (the offline path).

Separately, T-105 adds the push to `main`/PR builds; the `v*` workflow is the
release path only.

## 6. Platform note

Build `linux/amd64` only. `linux/arm64` becomes an option only if
`libparallelproj` exists for `linux-aarch64` on conda-forge — verify before
promising native Apple Silicon. Otherwise Macs run `linux/amd64` under
emulation, which is slow but functional; say so in the customer guide instead
of shipping a broken arm64 image.

## 7. Acceptance

- [ ] `docker images` shows `ctbeamstudio:*`; no `ct-viewer:*` image reference
      remains in any Docker command in docs, scripts or plans.
- [ ] conda env is still `ct-viewer` everywhere (`AGENTS.md`,
      `environment.yml`, `ci.yml`, `docs/local-environment.md`) and the suite
      still runs with that env name.
- [ ] `ctbeamstudio:1.0.0`, `:1.0`, `:latest` are the same digest.
- [ ] `ghcr.io/lhell/ctbeamstudio` is pullable without authentication.
- [ ] `release.yml` fails when `pyproject.toml` and the tag disagree.
- [ ] Release notes carry the digest and the tarball asset.

## 8. Risks

| Risk | Mitigation |
|---|---|
| `latest` drifts onto a `slim` build | only `full` is tagged `latest`; CI builds `--target full` explicitly |
| Half-renamed repo (`ct-viewer:` in one doc, `ctbeamstudio:` in another) | §1 file list is the checklist; the grep `ct-viewer:` must only hit conda sections |
| Renaming the conda env by accident | §1 marks env and distribution as unchanged |
| Version tag repointed after a bad build | immutable tags in GHCR |
| arm64 promise without a working lib | §6: amd64 only until verified |
