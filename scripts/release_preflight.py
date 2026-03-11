from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path


def _load_version(pyproject_path: Path) -> str:
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = data.get("project", {})
    version = project.get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("pyproject.toml missing [project].version")
    return version.strip()


def _normalize_tag(tag: str) -> str:
    normalized = tag.strip()
    if normalized.startswith("refs/tags/"):
        normalized = normalized[len("refs/tags/") :]
    return normalized


def _validate_tag(tag: str, version: str) -> None:
    normalized = _normalize_tag(tag)
    if not re.fullmatch(r"v\d+\.\d+\.\d+", normalized):
        raise ValueError(f"release tag must look like vX.Y.Z (got: {tag})")
    if normalized[1:] != version:
        raise ValueError(f"release tag {normalized} does not match pyproject version {version}")


def _validate_changelog(changelog_path: Path, version: str) -> None:
    text = changelog_path.read_text(encoding="utf-8")
    pattern = re.compile(rf"^##\s+\[?v?{re.escape(version)}\]?\s*$", re.MULTILINE)
    if not pattern.search(text):
        raise ValueError(
            "CHANGELOG.md missing release heading for version "
            f"{version} (expected: `## [{version}]` or `## v{version}`)"
        )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Validate release preflight metadata.")
    parser.add_argument("--tag", help="Release tag to validate (example: v1.0.2)")
    parser.add_argument("--pyproject", default="pyproject.toml")
    parser.add_argument("--changelog", default="CHANGELOG.md")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--out", help="Optional path for JSON output (requires --format json)")
    args = parser.parse_args(argv[1:])

    if args.out and args.format != "json":
        print("release preflight failed: --out requires --format json", file=sys.stderr)
        return 2

    pyproject = Path(args.pyproject)
    changelog = Path(args.changelog)

    try:
        version = _load_version(pyproject)
        _validate_changelog(changelog, version)
        if args.tag:
            _validate_tag(args.tag, version)
    except (FileNotFoundError, tomllib.TOMLDecodeError, ValueError) as exc:
        print(f"release preflight failed: {exc}", file=sys.stderr)
        return 1

    payload = {
        "ok": True,
        "version": version,
        "tag": _normalize_tag(args.tag) if args.tag else None,
        "pyproject": str(pyproject),
        "changelog": str(changelog),
    }

    if args.format == "json":
        text = json.dumps(payload, indent=2, sort_keys=True)
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(f"{text}\n", encoding="utf-8")
        else:
            print(text)
        return 0

    print(f"release preflight ok: version={version}")
    if args.tag:
        print(f"release preflight ok: tag={_normalize_tag(args.tag)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
