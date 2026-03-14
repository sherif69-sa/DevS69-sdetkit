#!/usr/bin/env python3
"""Audit direct dependencies and report latest PyPI versions.

This script is intended as a first step for planning repository upgrades.
It reads direct dependencies from pyproject.toml and fetches each package's
latest release metadata from PyPI.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


REQ_NAME_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)")


@dataclass(frozen=True)
class Dependency:
    group: str
    raw: str
    name: str


def _parse_dep_name(raw_requirement: str) -> str:
    match = REQ_NAME_RE.match(raw_requirement)
    if not match:
        return raw_requirement.strip()
    return match.group(1).lower().replace("_", "-")


def _load_dependencies(pyproject_path: Path) -> list[Dependency]:
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    project = data.get("project", {})
    deps: list[Dependency] = []

    for dep in project.get("dependencies", []):
        deps.append(Dependency(group="default", raw=dep, name=_parse_dep_name(dep)))

    for group, group_deps in project.get("optional-dependencies", {}).items():
        for dep in group_deps:
            deps.append(Dependency(group=group, raw=dep, name=_parse_dep_name(dep)))

    return deps


def _latest_pypi_version(package: str, timeout_s: float) -> str:
    url = f"https://pypi.org/pypi/{package}/json"
    request = urllib.request.Request(url, headers={"User-Agent": "sdetkit-upgrade-audit/1.0"})
    with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    version = payload.get("info", {}).get("version")
    if not version:
        return "unknown"
    return str(version)


def run(pyproject_path: Path, timeout_s: float) -> int:
    dependencies = _load_dependencies(pyproject_path)

    if not dependencies:
        print("No dependencies found in pyproject.toml.")
        return 0

    print("# Upgrade audit (direct dependencies)")
    print()
    print(f"Source: `{pyproject_path}`")
    print()
    print("| Group | Requirement | Latest PyPI |")
    print("|---|---|---|")

    for dep in dependencies:
        try:
            latest = _latest_pypi_version(dep.name, timeout_s=timeout_s)
        except urllib.error.HTTPError as exc:
            latest = f"http-{exc.code}"
        except urllib.error.URLError:
            latest = "network-error"

        print(f"| `{dep.group}` | `{dep.raw}` | `{latest}` |")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report the latest PyPI versions for direct dependencies in pyproject.toml."
    )
    parser.add_argument(
        "--pyproject",
        type=Path,
        default=Path("pyproject.toml"),
        help="Path to pyproject.toml (default: ./pyproject.toml)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="HTTP timeout in seconds for each PyPI request (default: 10)",
    )
    args = parser.parse_args()

    if not args.pyproject.exists():
        print(f"error: file not found: {args.pyproject}", file=sys.stderr)
        return 2

    return run(args.pyproject, timeout_s=args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
