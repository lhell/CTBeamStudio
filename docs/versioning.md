# Versioning: Git Tags and Docker Tags

How this project numbers releases, tags commits, builds images, and keeps the two
systems from drifting apart.

Last reviewed: 2026-10-29 (after Docker/WSL setup, image `ct-viewer:1.0.0`).

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
   `ct-viewer:dev`, `ct-viewer:sha-a1b2c3d`.
5. **Deploy by digest**, not by tag:
   `ct-viewer@sha256:...`. The tag is for humans; the digest is for tooling.
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
git tag -a v1.0.0 -m "BeamStudio 1.0.0"
git push origin main --follow-tags
```

Annotated tags (`-a`) record author, date and message. Lightweight tags
(`git tag v1.0.0`) are bare pointers and are not what release tooling expects.

### Step 3 - build the image

```powershell
docker build `
  -t ct-viewer:1.0.0 `
  -t ct-viewer:1.0 `
  -t ct-viewer:latest `
  --label org.opencontainers.image.title=ct-viewer `
  --label org.opencontainers.image.version=1.0.0 `
  --label org.opencontainers.image.revision=$(git rev-parse HEAD) `
  --label org.opencontainers.image.source=https://github.com/lhell/CTOrientationViewer `
  .
```

`1.0.0` is the immutable release tag. `1.0` is an optional moving alias for
"newest 1.x". `latest` is the moving alias for "newest stable".

### Step 4 - verify, then push

```powershell
docker inspect ct-viewer:1.0.0 --format '{{index .Config.Labels "org.opencontainers.image.version"}}'
docker push ghcr.io/lhell/ct-viewer:1.0.0
docker push ghcr.io/lhell/ct-viewer:1.0
docker push ghcr.io/lhell/ct-viewer:latest
docker inspect --format='{{index .RepoDigests 0}}' ct-viewer:1.0.0
```

Record the digest from the last command in the release notes.

### Step 5 - GitHub Release

Create a release for the tag `v1.0.0` and paste the image digest into the notes.

---

## 6. Development builds

Never spend a version number on a build that is not a release:

```powershell
docker build -t ct-viewer:dev -t ct-viewer:sha-$(git rev-parse --short HEAD) .
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

## 9. State of this repository (2026-10-29)

| Item | State |
|------|-------|
| `pyproject.toml` version | `1.0.0` |
| Git release tags | none (`archive/MPR` exists and is a **tag**, not a branch) |
| Local image tags | `ct-viewer:latest`, `ct-viewer:v1.0.0` |
| Docker tag convention | use `1.0.0` (no `v`); `v1.0.0` is a git-style spelling |
| CI | `.github/workflows/ci.yml` - data guard, flake8/black/isort, pytest |
| Container release | not automated; no Docker job in CI |

Known follow-ups:

- Retag the local image from `v1.0.0` to `1.0.0`.
- Create annotated git tag `v1.0.0` when the release commit is ready.
- Update `README.md` and `INSTALLATION.md` commands to use `ct-viewer:1.0.0`.

---

## 10. Automating the lockstep (outline)

A `.github/workflows/release.yml` triggered on `v*.*.*` should:

1. check out the tagged commit,
2. fail if `pyproject.toml` version != tag without the leading `v`,
3. build the image from that commit with version, minor alias and `latest` tags,
4. push to the registry with OCI labels,
5. create the GitHub Release with the resulting digest.

Until that exists, the manual procedure in section 5 is the contract.

---

## 11. Quick reference

```powershell
git status                                  # must be clean before tagging
git tag -a v1.0.0 -m "BeamStudio 1.0.0"
git push origin main --follow-tags

docker build -t ct-viewer:1.0.0 -t ct-viewer:latest .
docker push  ct-viewer:1.0.0
docker inspect --format='{{index .RepoDigests 0}}' ct-viewer:1.0.0
```

Related: [`INSTALLATION.md`](../INSTALLATION.md) for setup, [`README.md`](../README.md)
for usage.
