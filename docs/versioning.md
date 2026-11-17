# Versioning: Git Tags and Docker Tags

How this project numbers releases, tags commits, builds images, and keeps the two
systems from drifting apart.

Last reviewed: 2026-11-17 (image renamed to `ctbeamstudio`, T-106).

---

## 1. One number, three places

A release is only well defined when these three agree:

| Place | Form | Example |
|-------|------|---------|
| `pyproject.toml` | `version = "X.Y.Z"` | `1.0.0` |
| Git tag | `vX.Y.Z` (with `v`) | `v1.0.0` |
| Docker tag | `X.Y.Z` (no `v`, no `+`) | `1.0.0` |

If they disagree, the version number is decoration rather than information.

Semantic versioning: `MAJOR.MINOR.PATCH`.

### Variant axis

The Dockerfile has two targets, but only `full` is published. `slim` cannot
forward-project, so a customer who pulled it would get an image whose main
feature silently returns zeros. `slim` stays a local build target:

```powershell
docker build -t ctbeamstudio:slim --target slim .   # local only, never pushed
```

If `slim` ever ships, the variant becomes part of the tag and the plain version
keeps pointing at `full` — a bare `1.0.0`/`latest` must never be the crippled
image:

| Tag | Image |
|---|---|
| `1.0.0`, `1.0`, `latest` | `full` (parallelproj + torch) |
| `1.0.0-slim` (only if published) | `slim` |

Two published variants mean two digests per release; record both. The version
alone no longer identifies the artifact, so the variant also goes into an OCI
label (`com.ctbeamstudio.variant=full`).

---

## 2. Git tags vs Docker tags

They look similar but are different mechanisms and are **not** synchronised.

| | Git tag | Docker tag |
|---|---------|------------|
| Labels | a commit (immutable point in history) | an image manifest |
| Stored in | repository + remote (`origin`) | local image store + registry |
| Mutable? | only via force-push (discouraged) | yes, retagging silently repoints it |
| Immutable identity | commit SHA | digest `sha256:...` |
| Convention | `v1.0.0` | `1.0.0` |

Docker tags allow `.`, `-`, `_` and alphanumerics. They do **not** allow `+`, so
SemVer build metadata (`1.0.0+build.7`) cannot be a Docker tag. Put that in an
OCI label instead.

---

## 3. Rules

1. **Only released code gets a version tag.** Build from the tagged commit, never
   from a dirty working tree. Check `git status` before tagging.
2. **`latest` is an alias, never an identity.** Tag every release build with both
   the version and `latest`. Never deploy `latest`.
3. **Version tags are history.** Do not rebuild over an existing version tag.
   Bump instead. Enable immutable tags in the registry so this is enforced.
4. **Development builds use commit tags**, not version numbers:
   `ctbeamstudio:dev`, `ctbeamstudio:sha-a1b2c3d`.
5. **Deploy by digest**, not by tag:
   `ctbeamstudio@sha256:...`. The tag is for humans; the digest is for tooling.
6. **The git tag is the source of truth** for a release; Docker tags are derived
   from it (manually today, by CI later).

---

## 4. Choosing the number

| Change | Bump | Example |
|--------|------|---------|
| Bugfix, docs, dependency patch | PATCH | `1.0.0` -> `1.0.1` |
| New feature, backwards compatible | MINOR | `1.0.0` -> `1.1.0` |
| Breaking change (CLI, file formats, config) | MAJOR | `1.0.0` -> `2.0.0` |
| Release candidate | pre-release suffix | `1.1.0-rc.1` |

Pre-release suffixes are valid in both systems: git `v1.1.0-rc.1`, Docker `1.1.0-rc.1`.

---

## 5. Release procedure

### Step 1 - release commit

Edit the version in `pyproject.toml`, then:

```powershell
git add pyproject.toml
git commit -m "chore(release): 1.0.0"
```

### Step 2 - annotated git tag

```powershell
git tag -a v1.0.0 -m "CTBeamStudio 1.0.0"
git push origin main --follow-tags
```

Annotated tags (`-a`) record author, date and message. Lightweight tags
(`git tag v1.0.0`) are bare pointers and are not what release tooling expects.

### Step 3 - build the image

Releases ship the `full` target (parallelproj + torch, forward projection
works). Add `slim` as a second, smaller image if the bare viewer is needed.

```powershell
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
```

`1.0.0` is the immutable release tag. `1.0` is an optional moving alias for
"newest 1.x". `latest` is the moving alias for "newest stable".

### Step 4 - verify, then push

```powershell
docker inspect ctbeamstudio:1.0.0 --format '{{index .Config.Labels "org.opencontainers.image.version"}}'
docker push ghcr.io/lhell/ctbeamstudio:1.0.0
docker push ghcr.io/lhell/ctbeamstudio:1.0
docker push ghcr.io/lhell/ctbeamstudio:latest
docker inspect --format='{{index .RepoDigests 0}}' ctbeamstudio:1.0.0
```

Record the digest from the last command in the release notes.

### Step 5 - GitHub Release

Create a release for the tag `v1.0.0` and paste the image digest into the notes.

---

## 6. Development builds

Never spend a version number on a build that is not a release:

```powershell
docker build -t ctbeamstudio:dev -t ctbeamstudio:sha-$(git rev-parse --short HEAD) --target full .
```

---

## 7. Immutability and digests

A Docker tag is a pointer that can be repointed. Pushing again to the same tag
silently replaces the image in the registry, so two machines can pull
`1.0.0` and receive different code.

- Enable **immutable tags** on the registry (GHCR, Docker Hub and ECR all offer
  this). Then a second push to `1.0.0` fails and forces a version bump.
- The digest (`sha256:...`) is the only immutable identity. Pull and deploy by
  digest when reproducibility matters.

Note: immutability is a registry policy, not a local Docker feature. Locally you
can always retag.

---

## 8. Failure modes

| Failure | Symptom |
|---------|---------|
| Building from a dirty tree | `1.0.0` cannot be rebuilt from the tag |
| Retagging a released version | same tag, different behaviour on different machines |
| Bumping the image but not `pyproject.toml` | reported version and image version differ |
| Only tagging `latest` | rollbacks become guesswork |
| Git tag and Docker tag drift | "we deployed 1.0.0" is ambiguous |
| Confusing a tag with a branch | a "branch" like `archive/MPR` is actually a tag |

---

## 9. State of this repository (2026-11-17)

| Item | State |
|------|-------|
| `pyproject.toml` version | `1.0.0` |
| Git release tags | none (`archive/MPR` exists and is a **tag**, not a branch) |
| Local image tags | `ctbeamstudio:slim` (retagged 2026-11-17, T-73/T-106); stale `ct-viewer:latest`, `ct-viewer:v1.0.0` from pre-split builds still on disk |
| Docker tag convention | use `1.0.0` (no `v`); `v1.0.0` is a git-style spelling |
| Dockerfile targets | `full` (customer, published) and `slim` (local only) |
| Published images | none — no Docker job in CI, see T-73/T-105 in `docs/plan.md` |
| CI | `.github/workflows/ci.yml` - data guard, flake8/black/isort, pytest |
| Container release | not automated |

Known follow-ups:

- Remove or retag the stale local images `ct-viewer:latest` / `ct-viewer:v1.0.0`
  (pre-dates the two-target split; `docker rmi` when no longer needed).
- Create annotated git tag `v1.0.0` when the release commit is ready — the
  first `v*.*.*` push exercises `release.yml`.

---

## 10. Automating the lockstep

`.github/workflows/release.yml` (T-106) implements this for real, triggered on
`v*.*.*`:

1. checks out the tagged commit,
2. fails if `pyproject.toml` version != tag without the leading `v`
   (via `scripts/check_release_tag.py`, tested in
   `tests/unit/test_release_tag_check.py`),
3. builds the image from that commit with version, minor alias and `latest`
   tags, plus the OCI labels,
4. pushes to `ghcr.io/lhell/ctbeamstudio`,
5. creates the GitHub Release with the resulting digest,
6. uploads the `docker save` tarball as the offline asset.

The first `v*.*.*` tag push is the workflow's first real run; until then the
manual procedure in section 5 is the contract (and the fallback).

---

## 11. Quick reference

```powershell
git status                                  # must be clean before tagging
git tag -a v1.0.0 -m "CTBeamStudio 1.0.0"
git push origin main --follow-tags

docker build -t ctbeamstudio:1.0.0 -t ctbeamstudio:latest --target full .
docker tag  ctbeamstudio:1.0.0 ghcr.io/lhell/ctbeamstudio:1.0.0
docker push ghcr.io/lhell/ctbeamstudio:1.0.0
docker inspect --format='{{index .RepoDigests 0}}' ctbeamstudio:1.0.0
```

Related: [`INSTALLATION.md`](../INSTALLATION.md) for setup, [`README.md`](../README.md)
for usage.
