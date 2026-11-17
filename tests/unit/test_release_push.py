"""Tests for scripts/release_push.sh (T-106 review findings #1–#3).

The script owns the registry tag-and-push order:
- tag the locally built image to the registry names (the workflow must not
  push names it never created),
- moving aliases (`X.Y`, `latest`) push first with tolerated failure —
  GHCR immutable tags are package-wide and would otherwise kill the release
  identity on release #2,
- the version push (`X.Y.Z`) is strictly last and hard-fails the step,
- pre-release versions (`-suffix`) push the version tag ONLY: `latest` must
  never point at an RC and `${VERSION%.*}` of a suffix is a bogus alias.

Docker is not available in the test environment, so the behavior seam is
either CTBEAMSTUDIO_DRY_RUN=1 (echo the commands) or a PATH shim whose exit
code is steered via SHIM_FAIL_SUFFIXES.
"""

import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "release_push.sh"
REGISTRY = "ghcr.io/lhell/ctbeamstudio"


def run_push(
    version: str, tmp_path: Path, dry_run: bool = False, fail_suffixes: str = ""
):
    env = os.environ.copy()
    env.pop("CTBEAMSTUDIO_DRY_RUN", None)
    if dry_run:
        env["CTBEAMSTUDIO_DRY_RUN"] = "1"
    elif fail_suffixes:
        shim = tmp_path / "bin"
        shim.mkdir(exist_ok=True)
        docker = shim / "docker"
        docker.write_text(
            "#!/bin/sh\n"
            'echo "$@" >> "$SHIM_LOG"\n'
            "for t in $SHIM_FAIL_SUFFIXES; do\n"
            '  case "$2" in *$t) exit 1;; esac\n'
            "done\n"
            "exit 0\n"
        )
        docker.chmod(0o755)
        env["PATH"] = f"{shim}:{env.get('PATH', '')}"
        env["SHIM_FAIL_SUFFIXES"] = fail_suffixes
        env["SHIM_LOG"] = str(tmp_path / "docker-calls.log")
    return subprocess.run(
        ["bash", str(SCRIPT), version, REGISTRY],
        capture_output=True,
        text=True,
        env=env,
    )


def docker_calls(tmp_path: Path) -> list[str]:
    return (tmp_path / "docker-calls.log").read_text().splitlines()


def push_targets(result):
    return [
        line.split()[-1] for line in result.stdout.splitlines() if "docker push" in line
    ]


def test_full_version_tags_then_pushes_identity_last(tmp_path):
    result = run_push("1.0.0", tmp_path, dry_run=True)
    assert result.returncode == 0, result.stderr
    assert f"docker tag ctbeamstudio:1.0.0 {REGISTRY}:1.0.0" in result.stdout
    assert f"docker tag ctbeamstudio:1.0 {REGISTRY}:1.0" in result.stdout
    assert f"docker tag ctbeamstudio:latest {REGISTRY}:latest" in result.stdout
    targets = push_targets(result)
    assert targets == [f"{REGISTRY}:1.0", f"{REGISTRY}:latest", f"{REGISTRY}:1.0.0"]


def test_prerelease_pushes_identity_only(tmp_path):
    result = run_push("1.1.0-rc.1", tmp_path, dry_run=True)
    assert result.returncode == 0, result.stderr
    assert f"docker tag ctbeamstudio:1.1.0-rc.1 {REGISTRY}:1.1.0-rc.1" in result.stdout
    assert push_targets(result) == [f"{REGISTRY}:1.1.0-rc.1"]
    assert ":latest" not in result.stdout
    assert ":1.1.0-rc " not in result.stdout


def test_alias_push_failure_is_tolerated(tmp_path):
    result = run_push("1.0.0", tmp_path, fail_suffixes=":1.0 :latest")
    assert result.returncode == 0, result.stderr
    assert "::warning::" in result.stderr
    pushes = [c for c in docker_calls(tmp_path) if c.startswith("push")]
    # both aliases attempted and tolerated, identity attempted last
    assert pushes == [
        f"push {REGISTRY}:1.0",
        f"push {REGISTRY}:latest",
        f"push {REGISTRY}:1.0.0",
    ]


def test_identity_push_failure_fails_the_step(tmp_path):
    result = run_push("1.0.0", tmp_path, fail_suffixes=":1.0.0")
    assert result.returncode != 0
    assert "::error::" in result.stderr
    pushes = [c for c in docker_calls(tmp_path) if c.startswith("push")]
    assert pushes == [
        f"push {REGISTRY}:1.0",
        f"push {REGISTRY}:latest",
        f"push {REGISTRY}:1.0.0",
    ]
