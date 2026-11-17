#!/usr/bin/env python
"""Check that a git release tag and pyproject.toml agree (T-106).

The release workflow calls this before building the image, so a release
cannot carry a tag that disagrees with the distribution version:

    python scripts/check_release_tag.py v1.0.0 [--pyproject pyproject.toml]

Rules (docs/versioning.md):
- the tag must start with ``v`` (``v1.0.0`` is git spelling only),
- the rest must be ``X.Y.Z`` with an optional pre-release suffix
  (``v1.1.0-rc.1``),
- after stripping the ``v`` it must equal the ``[project] version``.

Exit codes: 0 = agree, 1 = any disagreement, with the reason on stderr.
"""

import re
import sys
import tomllib
from pathlib import Path

TAG_PATTERN = re.compile(r"^v(\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?)$")


def main(argv: list[str]) -> int:
    tag = argv[0]
    pyproject = Path("pyproject.toml")
    if len(argv) == 3 and argv[1] == "--pyproject":
        pyproject = Path(argv[2])
    elif len(argv) != 1:
        print(
            f"usage: check_release_tag.py <git-tag> [--pyproject PATH]", file=sys.stderr
        )
        return 1

    match = TAG_PATTERN.match(tag)
    if not match:
        print(
            f"tag '{tag}' is not a release tag: expected 'vX.Y.Z' "
            "(v-prefix required, three numbers, optional -suffix)",
            file=sys.stderr,
        )
        return 1
    tag_version = match.group(1)

    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        pyproject_version = data["project"]["version"]
    except (OSError, tomllib.TOMLDecodeError, KeyError) as exc:
        print(f"cannot read version from {pyproject}: {exc}", file=sys.stderr)
        return 1

    if tag_version != pyproject_version:
        print(
            f"tag/version mismatch: git tag says {tag_version}, "
            f"{pyproject} says {pyproject_version}",
            file=sys.stderr,
        )
        return 1

    print(f"tag and version agree: {tag} == {pyproject_version}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
