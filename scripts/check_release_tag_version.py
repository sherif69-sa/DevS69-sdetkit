from __future__ import annotations

import sys
import tomllib
from pathlib import Path


def _norm_tag(tag: str) -> str:
    t = tag.strip()
    if t.startswith("refs/tags/"):
        t = t[len("refs/tags/") :]
    if t.startswith("v"):
        t = t[1:]
    return t


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not argv[1].strip():
        print("usage: check_release_tag_version.py <tag>", file=sys.stderr)
        return 2

    tag = argv[1].strip()
    py = Path("pyproject.toml")
    data = tomllib.loads(py.read_text(encoding="utf-8"))
    proj = data.get("project", {})
    version = proj.get("version")

    if not isinstance(version, str) or not version.strip():
        print("pyproject.toml missing [project].version", file=sys.stderr)
        return 2

    want = version.strip()
    got = _norm_tag(tag)

    if got != want:
        print(f"release blocked: tag={tag} -> {got} but pyproject.version={want}", file=sys.stderr)
        return 1

    print(f"ok: tag={tag} matches pyproject.version={want}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
