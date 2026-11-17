#!/bin/bash
# Tag and push a release build to GHCR (T-106, review findings #1-#3).
#
#   release_push.sh VERSION REGISTRY
#   CTBEAMSTUDIO_DRY_RUN=1 release_push.sh ...   # echo instead of pushing
#
# Order and guarantees:
# - tags the locally built image to the registry names first: a workflow must
#   never push names it did not create,
# - moving aliases (X.Y, latest) push with TOLERATED failure: GHCR immutable
#   tags are package-wide, so on release #2 a repoint of an alias must not
#   abort the release identity,
# - the version push (X.Y.Z) is strictly LAST and hard-fails this script,
# - pre-release versions (a "-" suffix, e.g. 1.1.0-rc.1) push the version tag
#   ONLY: latest must never point at an RC, and ${VERSION%.*} of a suffixed
#   version is a bogus alias (1.1.0-rc).
#
# Contract: docs/versioning.md §3; called by .github/workflows/release.yml.
set -uo pipefail

VERSION="${1:?usage: release_push.sh VERSION REGISTRY}"
REGISTRY="${2:?usage: release_push.sh VERSION REGISTRY}"

DOCKER=docker
if [ -n "${CTBEAMSTUDIO_DRY_RUN:-}" ]; then
    DOCKER="echo docker"
fi

case "${VERSION}" in
    *-*) PRERELEASE=1 ;;
    *) PRERELEASE=0 ;;
esac

${DOCKER} tag "ctbeamstudio:${VERSION}" "${REGISTRY}:${VERSION}"
if [ "${PRERELEASE}" -eq 0 ]; then
    ${DOCKER} tag "ctbeamstudio:${VERSION%.*}" "${REGISTRY}:${VERSION%.*}"
    ${DOCKER} tag "ctbeamstudio:latest" "${REGISTRY}:latest"
fi

STATUS=0

# Moving aliases: tolerated failure, identity unaffected.
if [ "${PRERELEASE}" -eq 0 ]; then
    ${DOCKER} push "${REGISTRY}:${VERSION%.*}" \
        || echo "::warning::${REGISTRY}:${VERSION%.*} push failed (immutable tag?) — release identity unaffected" >&2
    ${DOCKER} push "${REGISTRY}:latest" \
        || echo "::warning::${REGISTRY}:latest push failed (immutable tag?) — release identity unaffected" >&2
fi

# Immutable release identity: last, and the only hard failure.
${DOCKER} push "${REGISTRY}:${VERSION}" \
    || { echo "::error::release identity push failed: ${REGISTRY}:${VERSION}" >&2; STATUS=1; }

exit "${STATUS}"
