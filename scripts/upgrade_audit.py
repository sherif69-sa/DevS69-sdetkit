#!/usr/bin/env python3
"""Audit dependency manifests and report upgrade planning signals.

This script is intended as a first step for planning repository upgrades.
It reads dependency declarations from ``pyproject.toml`` and one or more
requirements files, highlights cross-manifest drift, and fetches the latest
PyPI release metadata for each package.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

REQ_NAME_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)")
PINNED_VERSION_RE = re.compile(r"==\s*([A-Za-z0-9_.!+-]+)")


@dataclass(frozen=True)
class Dependency:
    source: str
    group: str
    raw: str
    name: str
    pinned_version: str | None


@dataclass(frozen=True)
class PackageReport:
    name: str
    sources: list[str]
    groups: list[str]
    requirements: list[str]
    pinned_versions: list[str]
    alignment: str
    latest_version: str
    latest_release_date: str | None
    upgrade_signal: str


def _parse_dep_name(raw_requirement: str) -> str:
    match = REQ_NAME_RE.match(raw_requirement)
    if not match:
        return raw_requirement.strip()
    return match.group(1).lower().replace("_", "-")


def _extract_pinned_version(raw_requirement: str) -> str | None:
    match = PINNED_VERSION_RE.search(raw_requirement)
    if match:
        return match.group(1)
    return None


def _normalize_requirement_line(line: str) -> str | None:
    candidate = line.split("#", 1)[0].strip()
    if not candidate:
        return None
    if candidate.startswith(("-e", "--editable", "-r", "--requirement", "-c", "--constraint")):
        return None
    if candidate.startswith(("http://", "https://", "git+", ".", "/")):
        return None
    return candidate


def _load_pyproject_dependencies(pyproject_path: Path) -> list[Dependency]:
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = data.get("project", {})
    deps: list[Dependency] = []

    for dep in project.get("dependencies", []):
        deps.append(
            Dependency(
                source=pyproject_path.name,
                group="default",
                raw=dep,
                name=_parse_dep_name(dep),
                pinned_version=_extract_pinned_version(dep),
            )
        )

    for group, group_deps in project.get("optional-dependencies", {}).items():
        for dep in group_deps:
            deps.append(
                Dependency(
                    source=pyproject_path.name,
                    group=str(group),
                    raw=dep,
                    name=_parse_dep_name(dep),
                    pinned_version=_extract_pinned_version(dep),
                )
            )

    return deps


def _load_requirements_dependencies(requirements_path: Path) -> list[Dependency]:
    deps: list[Dependency] = []
    for raw_line in requirements_path.read_text(encoding="utf-8").splitlines():
        candidate = _normalize_requirement_line(raw_line)
        if candidate is None:
            continue
        deps.append(
            Dependency(
                source=requirements_path.name,
                group="requirements",
                raw=candidate,
                name=_parse_dep_name(candidate),
                pinned_version=_extract_pinned_version(candidate),
            )
        )
    return deps


def _discover_requirement_files(root: Path, include_lockfiles: bool) -> list[Path]:
    files = sorted(root.glob("requirements*.txt"))
    if not include_lockfiles:
        files = [path for path in files if not path.name.endswith(".lock")]
    return files


def _load_dependencies(
    pyproject_path: Path,
    requirement_paths: list[Path],
) -> list[Dependency]:
    deps = _load_pyproject_dependencies(pyproject_path)
    for path in requirement_paths:
        deps.extend(_load_requirements_dependencies(path))
    return deps


def _latest_pypi_metadata(package: str, timeout_s: float) -> tuple[str, str | None]:
    url = f"https://pypi.org/pypi/{package}/json"
    request = urllib.request.Request(url, headers={"User-Agent": "sdetkit-upgrade-audit/2.0"})
    with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))

    info = payload.get("info", {})
    version = str(info.get("version") or "unknown")
    release_date: str | None = None
    releases = payload.get("releases", {})
    if isinstance(releases, dict):
        release_files = releases.get(version) or []
        if isinstance(release_files, list):
            for item in release_files:
                if isinstance(item, dict) and item.get("upload_time_iso_8601"):
                    release_date = str(item["upload_time_iso_8601"])
                    break
    return version, release_date


def _build_package_report(
    name: str, deps: list[Dependency], latest_version: str, release_date: str | None
) -> PackageReport:
    sources = sorted({dep.source for dep in deps})
    groups = sorted({dep.group for dep in deps})
    requirements = sorted({dep.raw for dep in deps})
    pinned_versions = sorted({dep.pinned_version for dep in deps if dep.pinned_version})

    alignment = "aligned"
    if len(requirements) > 1:
        alignment = "drift"
    elif not pinned_versions:
        alignment = "range-or-unpinned"

    upgrade_signal = "watch"
    if alignment == "drift":
        upgrade_signal = "high"
    elif len(pinned_versions) == 1 and latest_version not in {"unknown", pinned_versions[0]}:
        upgrade_signal = "high" if "default" in groups else "medium"
    elif latest_version == "unknown":
        upgrade_signal = "unknown"

    return PackageReport(
        name=name,
        sources=sources,
        groups=groups,
        requirements=requirements,
        pinned_versions=pinned_versions,
        alignment=alignment,
        latest_version=latest_version,
        latest_release_date=release_date,
        upgrade_signal=upgrade_signal,
    )


def _render_markdown(
    reports: list[PackageReport],
    *,
    pyproject_path: Path,
    requirement_paths: list[Path],
) -> str:
    drift_count = sum(1 for report in reports if report.alignment == "drift")
    high_priority = sum(1 for report in reports if report.upgrade_signal == "high")
    lines = [
        "# Upgrade audit",
        "",
        f"Source pyproject: `{pyproject_path}`",
        f"Requirement manifests: {', '.join(f'`{path}`' for path in requirement_paths) if requirement_paths else '`none`'}",
        "",
        f"- packages audited: {len(reports)}",
        f"- manifest drift packages: {drift_count}",
        f"- high-priority upgrade signals: {high_priority}",
        "",
        "| Package | Alignment | Upgrade signal | Latest PyPI | Release date | Requirements |",
        "|---|---|---|---|---|---|",
    ]
    for report in reports:
        release_date = report.latest_release_date or "-"
        requirements = " <br> ".join(f"`{item}`" for item in report.requirements)
        lines.append(
            "| "
            f"`{report.name}` | {report.alignment} | {report.upgrade_signal} | `{report.latest_version}` | {release_date} | {requirements} |"
        )
    return "\n".join(lines) + "\n"


def _render_json(
    reports: list[PackageReport],
    *,
    pyproject_path: Path,
    requirement_paths: list[Path],
) -> str:
    payload = {
        "pyproject": str(pyproject_path),
        "requirements": [str(path) for path in requirement_paths],
        "summary": {
            "packages_audited": len(reports),
            "manifest_drift_packages": sum(1 for report in reports if report.alignment == "drift"),
            "high_priority_upgrade_signals": sum(
                1 for report in reports if report.upgrade_signal == "high"
            ),
        },
        "packages": [asdict(report) for report in reports],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def run(
    pyproject_path: Path,
    timeout_s: float,
    *,
    requirement_paths: list[Path],
    output_format: str,
) -> int:
    dependencies = _load_dependencies(pyproject_path, requirement_paths)

    if not dependencies:
        print("No dependencies found in the configured manifests.")
        return 0

    by_package: dict[str, list[Dependency]] = {}
    for dep in dependencies:
        by_package.setdefault(dep.name, []).append(dep)

    reports: list[PackageReport] = []
    for package in sorted(by_package):
        try:
            latest_version, release_date = _latest_pypi_metadata(package, timeout_s=timeout_s)
        except urllib.error.HTTPError as exc:
            latest_version, release_date = f"http-{exc.code}", None
        except urllib.error.URLError:
            latest_version, release_date = "network-error", None

        reports.append(
            _build_package_report(
                package,
                by_package[package],
                latest_version=latest_version,
                release_date=release_date,
            )
        )

    rendered = {
        "json": _render_json(
            reports, pyproject_path=pyproject_path, requirement_paths=requirement_paths
        ),
        "md": _render_markdown(
            reports, pyproject_path=pyproject_path, requirement_paths=requirement_paths
        ),
    }[output_format]
    sys.stdout.write(rendered)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit dependency manifests, highlight drift, and report the latest PyPI versions "
            "for each declared package."
        )
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
    parser.add_argument(
        "--format",
        choices=["md", "json"],
        default="md",
        help="Output format (default: md)",
    )
    parser.add_argument(
        "--requirements",
        type=Path,
        action="append",
        default=None,
        help="Additional requirements file to scan. Can be passed multiple times.",
    )
    parser.add_argument(
        "--include-lockfiles",
        action="store_true",
        help="Include requirements*.txt.lock files discovered in the repo root.",
    )
    args = parser.parse_args()

    if not args.pyproject.exists():
        print(f"error: file not found: {args.pyproject}", file=sys.stderr)
        return 2

    requirement_paths = args.requirements
    if requirement_paths is None:
        requirement_paths = _discover_requirement_files(
            args.pyproject.parent,
            include_lockfiles=bool(args.include_lockfiles),
        )

    missing = [path for path in requirement_paths if not path.exists()]
    if missing:
        for path in missing:
            print(f"error: requirements file not found: {path}", file=sys.stderr)
        return 2

    return run(
        args.pyproject,
        timeout_s=args.timeout,
        requirement_paths=requirement_paths,
        output_format=args.format,
    )


if __name__ == "__main__":
    raise SystemExit(main())
