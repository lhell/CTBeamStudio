"""Tests for scripts/check_release_tag.py (T-106 release lockstep).

The checker is stdlib-only and runs as a subprocess: the contract under test
is its exit code and stderr, not a function signature. Each test writes its
own minimal pyproject.toml so the suite never depends on the repo's current
version number.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_release_tag.py"


def run_check(tag: str, version: str | None, tmp_path: Path):
    pyproject = f'[project]\nname = "ct-viewer"\nversion = "{version}"\n'
    pyfile = tmp_path / "pyproject.toml"
    if version is None:
        pyfile.write_text('[project]\nname = "ct-viewer"\n')
    else:
        pyfile.write_text(pyproject)
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            tag,
            "--pyproject",
            str(pyfile),
        ],
        capture_output=True,
        text=True,
    )


def test_matching_tag_passes(tmp_path):
    result = run_check("v1.0.0", "1.0.0", tmp_path)
    assert result.returncode == 0, result.stderr


def test_prerelease_tag_matches_prerelease_version(tmp_path):
    result = run_check("v1.1.0-rc.1", "1.1.0-rc.1", tmp_path)
    assert result.returncode == 0, result.stderr


def test_mismatched_tag_fails_and_names_both(tmp_path):
    result = run_check("v1.0.1", "1.0.0", tmp_path)
    assert result.returncode == 1
    assert "1.0.1" in result.stderr
    assert "1.0.0" in result.stderr


def test_tag_without_v_prefix_fails(tmp_path):
    result = run_check("1.0.0", "1.0.0", tmp_path)
    assert result.returncode == 1
    assert "v" in result.stderr


def test_non_semver_tag_fails(tmp_path):
    result = run_check("v1.0", "1.0.0", tmp_path)
    assert result.returncode == 1


def test_missing_version_in_pyproject_fails(tmp_path):
    result = run_check("v1.0.0", None, tmp_path)
    assert result.returncode == 1
