#!/usr/bin/env python3
"""Audit dependency manifests and report upgrade planning signals.

This script is intended as a first step for planning repository upgrades.
It reads dependency declarations from ``pyproject.toml`` and one or more
requirements files, highlights cross-manifest drift, and fetches the latest
PyPI release metadata for each package.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import tomllib
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path

REQ_NAME_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)")
PINNED_VERSION_RE = re.compile(r"==\s*([A-Za-z0-9_.!+-]+)")
CONSTRAINT_RE = re.compile(r"(==|~=|>=|<=|>|<)\s*([A-Za-z0-9_.!+-]+)")


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
    current_version: str
    alignment: str
    constraint_status: str
    latest_version: str
    latest_release_date: str | None
    metadata_source: str
    version_gap: str
    release_age_days: int | None
    upgrade_signal: str
    risk_score: int
    next_action: str
    notes: list[str]


@dataclass(frozen=True)
class PackageMetadata:
    latest_version: str
    release_date: str | None
    source: str


SIGNAL_PRIORITY = {
    "critical": 5,
    "high": 4,
    "medium": 3,
    "watch": 2,
    "investigate": 2,
    "unknown": 1,
}
DEFAULT_CACHE_PATH = Path(".sdetkit/cache/upgrade-audit-cache.json")


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


def _extract_minimum_version(raw_requirement: str) -> str | None:
    for token in raw_requirement.split(","):
        candidate = token.strip()
        for operator in (">=", "~=", ">"):
            if operator in candidate:
                _, _, version = candidate.partition(operator)
                normalized = version.strip()
                if normalized:
                    return normalized
    return None


def _parse_requirement_constraints(raw_requirement: str) -> list[tuple[str, str]]:
    base = raw_requirement.split(";", 1)[0].strip()
    if not base:
        return []
    start = REQ_NAME_RE.match(base)
    spec = base[start.end() :] if start else base
    return [(operator, version) for operator, version in CONSTRAINT_RE.findall(spec)]


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


def _load_cache(cache_path: Path) -> dict[str, dict[str, str | float | None]]:
    if not cache_path.exists():
        return {}
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    cache = payload.get("packages", {})
    if not isinstance(cache, dict):
        return {}
    normalized: dict[str, dict[str, str | float | None]] = {}
    for package, item in cache.items():
        if isinstance(package, str) and isinstance(item, dict):
            normalized[package] = item
    return normalized


def _persist_cache(cache_path: Path, cache: dict[str, dict[str, str | float | None]]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "packages": cache,
    }
    cache_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _cache_entry_fresh(entry: dict[str, str | float | None], ttl_hours: float) -> bool:
    fetched_at = entry.get("fetched_at")
    if not isinstance(fetched_at, (int, float)):
        return False
    age_s = dt.datetime.now(dt.UTC).timestamp() - float(fetched_at)
    return age_s <= max(ttl_hours, 0) * 3600


def _metadata_from_cache(entry: dict[str, str | float | None], *, source: str) -> PackageMetadata:
    latest_version = entry.get("latest_version")
    release_date = entry.get("release_date")
    if not isinstance(latest_version, str):
        latest_version = "unknown"
    if release_date is not None and not isinstance(release_date, str):
        release_date = None
    return PackageMetadata(
        latest_version=latest_version,
        release_date=release_date,
        source=source,
    )


def _fetch_package_metadata(
    package: str,
    *,
    timeout_s: float,
    cache: dict[str, dict[str, str | float | None]],
    cache_ttl_hours: float,
    offline: bool,
) -> PackageMetadata:
    cached_entry = cache.get(package)
    if cached_entry and _cache_entry_fresh(cached_entry, cache_ttl_hours):
        return _metadata_from_cache(cached_entry, source="cache")

    if offline:
        if cached_entry:
            return _metadata_from_cache(cached_entry, source="cache-stale")
        return PackageMetadata(
            latest_version="offline-no-cache", release_date=None, source="offline"
        )

    try:
        latest_version, release_date = _latest_pypi_metadata(package, timeout_s=timeout_s)
    except urllib.error.HTTPError as exc:
        latest_version, release_date = f"http-{exc.code}", None
    except urllib.error.URLError:
        if cached_entry:
            return _metadata_from_cache(cached_entry, source="cache-stale")
        latest_version, release_date = "network-error", None

    cache[package] = {
        "fetched_at": dt.datetime.now(dt.UTC).timestamp(),
        "latest_version": latest_version,
        "release_date": release_date,
    }
    return PackageMetadata(latest_version=latest_version, release_date=release_date, source="pypi")


def _collect_package_metadata(
    packages: list[str],
    *,
    timeout_s: float,
    cache_path: Path,
    cache_ttl_hours: float,
    offline: bool,
    max_workers: int,
) -> dict[str, PackageMetadata]:
    cache = _load_cache(cache_path)
    metadata: dict[str, PackageMetadata] = {}
    worker_count = max(1, min(max_workers, len(packages)))
    if worker_count == 1:
        for package in packages:
            metadata[package] = _fetch_package_metadata(
                package,
                timeout_s=timeout_s,
                cache=cache,
                cache_ttl_hours=cache_ttl_hours,
                offline=offline,
            )
    else:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(
                    _fetch_package_metadata,
                    package,
                    timeout_s=timeout_s,
                    cache=cache,
                    cache_ttl_hours=cache_ttl_hours,
                    offline=offline,
                ): package
                for package in packages
            }
            for future in as_completed(futures):
                metadata[futures[future]] = future.result()

    if not offline:
        _persist_cache(cache_path, cache)
    return metadata


def _version_key(version: str) -> tuple[tuple[int, object], ...]:
    parts: list[tuple[int, object]] = []
    for segment in re.split(r"[.+!_-]", version):
        cleaned = segment.strip()
        if not cleaned:
            continue
        if cleaned.isdigit():
            parts.append((0, int(cleaned)))
        else:
            match = re.match(r"^(\d+)([A-Za-z].*)$", cleaned)
            if match:
                parts.append((0, int(match.group(1))))
                parts.append((1, match.group(2).lower()))
            else:
                parts.append((1, cleaned.lower()))
    return tuple(parts)


def _compare_versions(left: str, right: str) -> int:
    left_key = _version_key(left)
    right_key = _version_key(right)
    if left_key < right_key:
        return -1
    if left_key > right_key:
        return 1
    return 0


def _compatible_upper_bound(version: str) -> str | None:
    parts = [int(part) for part in re.findall(r"\d+", version)]
    if not parts:
        return None
    if len(parts) == 1:
        return str(parts[0] + 1)
    upper = parts[:-1]
    upper[-1] += 1
    return ".".join(str(part) for part in upper)


def _constraint_allows_version(constraint: tuple[str, str], version: str) -> bool:
    operator, required = constraint
    cmp = _compare_versions(version, required)
    if operator == "==":
        return cmp == 0
    if operator == ">=":
        return cmp >= 0
    if operator == "<=":
        return cmp <= 0
    if operator == ">":
        return cmp > 0
    if operator == "<":
        return cmp < 0
    if operator == "~=":
        upper = _compatible_upper_bound(required)
        if upper is None:
            return False
        return cmp >= 0 and _compare_versions(version, upper) < 0
    return False


def _requirement_allows_version(raw_requirement: str, version: str) -> bool | None:
    constraints = _parse_requirement_constraints(raw_requirement)
    if not constraints:
        return None
    return all(_constraint_allows_version(constraint, version) for constraint in constraints)


def _pick_current_version(deps: list[Dependency]) -> str:
    pinned_versions = sorted(
        {dep.pinned_version for dep in deps if dep.pinned_version},
        key=_version_key,
    )
    if pinned_versions:
        return pinned_versions[-1]

    lower_bounds = sorted(
        {
            lower_bound
            for dep in deps
            if (lower_bound := _extract_minimum_version(dep.raw)) is not None
        },
        key=_version_key,
    )
    if lower_bounds:
        return lower_bounds[-1]
    return "unbounded"


def _constraint_status(deps: list[Dependency], latest_version: str) -> str:
    if latest_version in {
        "unknown",
        "network-error",
        "offline-no-cache",
    } or latest_version.startswith("http-"):
        return "unknown"
    allowed_results = [
        result
        for dep in deps
        if (result := _requirement_allows_version(dep.raw, latest_version)) is not None
    ]
    if not allowed_results:
        return "unbounded"
    return "allowed" if all(allowed_results) else "blocked"


def _infer_alignment(deps: list[Dependency], current_version: str) -> str:
    requirements = sorted({dep.raw for dep in deps})
    pinned_versions = sorted({dep.pinned_version for dep in deps if dep.pinned_version})
    if len(requirements) == 1:
        return "range-or-unpinned" if not pinned_versions else "aligned"

    if len(pinned_versions) > 1:
        return "drift"

    allowed_results = [
        result
        for dep in deps
        if current_version != "unbounded"
        and (result := _requirement_allows_version(dep.raw, current_version)) is not None
    ]
    if allowed_results and all(allowed_results):
        return "compatible"
    return "drift"


def _major_minor_patch(version: str) -> tuple[int, int, int] | None:
    match = re.match(r"^\s*(\d+)(?:\.(\d+))?(?:\.(\d+))?", version)
    if not match:
        return None
    major = int(match.group(1))
    minor = int(match.group(2) or 0)
    patch = int(match.group(3) or 0)
    return major, minor, patch


def _classify_version_gap(current_version: str, latest_version: str) -> str:
    if (
        current_version in {"unbounded", "unknown"}
        or latest_version
        in {
            "unknown",
            "network-error",
            "offline-no-cache",
        }
        or latest_version.startswith("http-")
    ):
        return "unknown"
    if current_version == latest_version:
        return "up-to-date"
    current_triplet = _major_minor_patch(current_version)
    latest_triplet = _major_minor_patch(latest_version)
    if current_triplet is None or latest_triplet is None:
        return "different"
    if latest_triplet[0] != current_triplet[0]:
        return "major"
    if latest_triplet[1] != current_triplet[1]:
        return "minor"
    if latest_triplet[2] != current_triplet[2]:
        return "patch"
    return "different"


def _release_age_days(release_date: str | None) -> int | None:
    if not release_date:
        return None
    normalized = release_date.replace("Z", "+00:00")
    try:
        uploaded = dt.datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if uploaded.tzinfo is None:
        uploaded = uploaded.replace(tzinfo=dt.UTC)
    now = dt.datetime.now(dt.UTC)
    return max((now - uploaded).days, 0)


def _build_package_report(
    name: str,
    deps: list[Dependency],
    latest_version: str,
    release_date: str | None,
    *,
    metadata_source: str = "pypi",
) -> PackageReport:
    sources = sorted({dep.source for dep in deps})
    groups = sorted({dep.group for dep in deps})
    requirements = sorted({dep.raw for dep in deps})
    pinned_versions = sorted({dep.pinned_version for dep in deps if dep.pinned_version})
    current_version = _pick_current_version(deps)
    version_gap = _classify_version_gap(current_version, latest_version)
    release_age_days = _release_age_days(release_date)
    alignment = _infer_alignment(deps, current_version)
    constraint_status = _constraint_status(deps, latest_version)

    notes: list[str] = []
    if alignment == "drift":
        notes.append("Cross-manifest requirement drift detected.")
    elif alignment == "compatible":
        notes.append("Cross-manifest requirements differ but remain mutually compatible.")
    if alignment == "range-or-unpinned":
        notes.append("Package is not pinned to a single exact version.")
    if constraint_status == "allowed":
        notes.append("Latest PyPI release is already allowed by the declared version policy.")
    elif constraint_status == "blocked":
        notes.append("Latest PyPI release falls outside the currently declared version policy.")
    if version_gap == "major":
        notes.append("Latest PyPI release is a major-version jump from the repo baseline.")
    elif version_gap == "minor":
        notes.append("Latest PyPI release is a minor-version jump from the repo baseline.")
    elif version_gap == "patch":
        notes.append("Latest PyPI release is a patch-level bump from the repo baseline.")
    if release_age_days is not None and release_age_days <= 30:
        notes.append("Latest PyPI release is recent enough to merit fast follow-up validation.")

    upgrade_signal = "watch"
    if alignment == "drift":
        upgrade_signal = "critical" if version_gap == "major" else "high"
    elif constraint_status == "allowed":
        upgrade_signal = "watch" if "default" not in groups else "medium"
    elif version_gap == "major":
        upgrade_signal = "high" if "default" in groups else "medium"
    elif version_gap == "minor":
        upgrade_signal = "medium" if "default" in groups else "watch"
    elif version_gap == "patch":
        upgrade_signal = "watch"
    elif latest_version == "unknown":
        upgrade_signal = "unknown"
    elif latest_version == "network-error" or latest_version.startswith("http-"):
        upgrade_signal = "investigate"
    elif latest_version == "offline-no-cache":
        upgrade_signal = "investigate"

    risk_score = 0
    if alignment == "drift":
        risk_score += 45
    elif alignment == "compatible":
        risk_score += 10
    elif alignment == "range-or-unpinned":
        risk_score += 15
    if constraint_status == "blocked":
        risk_score += 15

    risk_score += {
        "major": 35,
        "minor": 20,
        "patch": 10,
        "different": 15,
        "unknown": 5,
    }.get(version_gap, 0)

    if "default" in groups:
        risk_score += 10
    if release_age_days is not None and release_age_days <= 30:
        risk_score += 10
    if upgrade_signal == "investigate":
        risk_score += 10

    next_action = "Keep under observation; no immediate action required."
    if upgrade_signal == "critical":
        next_action = (
            "Resolve manifest drift first, then validate the major upgrade in a dedicated branch."
        )
    elif upgrade_signal == "high":
        next_action = "Plan an upgrade spike with regression coverage before the next release cut."
    elif upgrade_signal == "medium":
        next_action = (
            "Queue the upgrade for the next maintenance batch and validate targeted smoke tests."
        )
    elif upgrade_signal == "watch":
        next_action = (
            "Keep the package on watch; the declared version policy already covers the latest release."
            if constraint_status == "allowed"
            else "Track the package and batch it with nearby dependency maintenance work."
        )
    elif upgrade_signal == "investigate":
        next_action = "Retry metadata collection and inspect package naming, cache freshness, or connectivity issues."
    elif upgrade_signal == "unknown":
        next_action = (
            "Review the declared version range manually because the gap could not be classified."
        )

    return PackageReport(
        name=name,
        sources=sources,
        groups=groups,
        requirements=requirements,
        pinned_versions=pinned_versions,
        current_version=current_version,
        alignment=alignment,
        constraint_status=constraint_status,
        latest_version=latest_version,
        latest_release_date=release_date,
        metadata_source=metadata_source,
        version_gap=version_gap,
        release_age_days=release_age_days,
        upgrade_signal=upgrade_signal,
        risk_score=risk_score,
        next_action=next_action,
        notes=notes,
    )


def _priority_queue(reports: list[PackageReport], *, limit: int = 5) -> list[dict[str, object]]:
    queue: list[dict[str, object]] = []
    for report in reports[: max(limit, 0)]:
        queue.append(
            {
                "name": report.name,
                "signal": report.upgrade_signal,
                "risk_score": report.risk_score,
                "alignment": report.alignment,
                "policy": report.constraint_status,
                "current_version": report.current_version,
                "latest_version": report.latest_version,
                "next_action": report.next_action,
            }
        )
    return queue


def _filter_reports(
    reports: list[PackageReport],
    *,
    signals: list[str] | None = None,
    policies: list[str] | None = None,
    top: int | None = None,
) -> list[PackageReport]:
    filtered = reports
    if signals:
        allowed_signals = {item.strip() for item in signals if item.strip()}
        filtered = [report for report in filtered if report.upgrade_signal in allowed_signals]
    if policies:
        allowed_policies = {item.strip() for item in policies if item.strip()}
        filtered = [report for report in filtered if report.constraint_status in allowed_policies]
    if top is not None:
        filtered = filtered[: max(top, 0)]
    return filtered


def _render_markdown(
    reports: list[PackageReport],
    *,
    pyproject_path: Path,
    requirement_paths: list[Path],
) -> str:
    drift_count = sum(1 for report in reports if report.alignment == "drift")
    compatible_count = sum(1 for report in reports if report.alignment == "compatible")
    high_priority = sum(1 for report in reports if report.upgrade_signal == "high")
    critical_priority = sum(1 for report in reports if report.upgrade_signal == "critical")
    medium_priority = sum(1 for report in reports if report.upgrade_signal == "medium")
    investigate_priority = sum(1 for report in reports if report.upgrade_signal == "investigate")
    policy_covered = sum(1 for report in reports if report.constraint_status == "allowed")
    policy_blocked = sum(1 for report in reports if report.constraint_status == "blocked")
    cached_results = sum(
        1 for report in reports if any("cache" in note.lower() for note in report.notes)
    )
    lines = [
        "# Upgrade audit",
        "",
        f"Source pyproject: `{pyproject_path}`",
        f"Requirement manifests: {', '.join(f'`{path}`' for path in requirement_paths) if requirement_paths else '`none`'}",
        "",
        f"- packages audited: {len(reports)}",
        f"- manifest drift packages: {drift_count}",
        f"- compatible multi-manifest packages: {compatible_count}",
        f"- policy-covered latest releases: {policy_covered}",
        f"- policy-blocked latest releases: {policy_blocked}",
        f"- critical upgrade signals: {critical_priority}",
        f"- high-priority upgrade signals: {high_priority}",
        f"- medium-priority upgrade signals: {medium_priority}",
        f"- investigate signals: {investigate_priority}",
        f"- packages using cached metadata: {cached_results}",
        "",
        "| Package | Current | Latest PyPI | Source | Gap | Alignment | Policy | Signal | Risk | Release age (days) | Requirements |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for report in reports:
        release_age = "-" if report.release_age_days is None else str(report.release_age_days)
        requirements = " <br> ".join(f"`{item}`" for item in report.requirements)
        lines.append(
            "| "
            f"`{report.name}` | `{report.current_version}` | `{report.latest_version}` | {report.metadata_source} | {report.version_gap} | "
            f"{report.alignment} | {report.constraint_status} | {report.upgrade_signal} | {report.risk_score} | {release_age} | {requirements} |"
        )
    lines.extend(["", "## Priority queue", ""])
    for item in _priority_queue(reports):
        lines.append(
            f"- `{item['name']}` [{item['signal']}, risk {item['risk_score']}] → {item['next_action']}"
        )
    lines.extend(["", "## Focus notes", ""])
    for report in reports:
        note_text = " ".join(report.notes) if report.notes else "No additional notes."
        lines.append(f"- `{report.name}` ({report.next_action}) {note_text}")
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
            "compatible_constraint_packages": sum(
                1 for report in reports if report.alignment == "compatible"
            ),
            "policy_covered_packages": sum(
                1 for report in reports if report.constraint_status == "allowed"
            ),
            "policy_blocked_packages": sum(
                1 for report in reports if report.constraint_status == "blocked"
            ),
            "critical_upgrade_signals": sum(
                1 for report in reports if report.upgrade_signal == "critical"
            ),
            "high_priority_upgrade_signals": sum(
                1 for report in reports if report.upgrade_signal == "high"
            ),
            "medium_priority_upgrade_signals": sum(
                1 for report in reports if report.upgrade_signal == "medium"
            ),
            "investigate_upgrade_signals": sum(
                1 for report in reports if report.upgrade_signal == "investigate"
            ),
            "cached_metadata_packages": sum(
                1 for report in reports if any("cache" in note.lower() for note in report.notes)
            ),
            "max_risk_score": max((report.risk_score for report in reports), default=0),
        },
        "priority_queue": _priority_queue(reports),
        "packages": [asdict(report) for report in reports],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _sort_reports(reports: list[PackageReport]) -> list[PackageReport]:
    return sorted(
        reports,
        key=lambda report: (
            -report.risk_score,
            -SIGNAL_PRIORITY.get(report.upgrade_signal, 0),
            report.name,
        ),
    )


def _should_fail(reports: list[PackageReport], fail_on: str) -> bool:
    if fail_on == "never":
        return False
    threshold = SIGNAL_PRIORITY[fail_on]
    return any(SIGNAL_PRIORITY.get(report.upgrade_signal, 0) >= threshold for report in reports)


def run(
    pyproject_path: Path,
    timeout_s: float,
    *,
    requirement_paths: list[Path],
    output_format: str,
    fail_on: str = "never",
    cache_path: Path = DEFAULT_CACHE_PATH,
    cache_ttl_hours: float = 24.0,
    offline: bool = False,
    max_workers: int = 8,
    signals: list[str] | None = None,
    policies: list[str] | None = None,
    top: int | None = None,
) -> int:
    dependencies = _load_dependencies(pyproject_path, requirement_paths)

    if not dependencies:
        print("No dependencies found in the configured manifests.")
        return 0

    by_package: dict[str, list[Dependency]] = {}
    for dep in dependencies:
        by_package.setdefault(dep.name, []).append(dep)

    packages = sorted(by_package)
    metadata_by_package = _collect_package_metadata(
        packages,
        timeout_s=timeout_s,
        cache_path=cache_path,
        cache_ttl_hours=cache_ttl_hours,
        offline=offline,
        max_workers=max_workers,
    )
    reports: list[PackageReport] = []
    for package in packages:
        metadata = metadata_by_package[package]
        reports.append(
            _build_package_report(
                package,
                by_package[package],
                latest_version=metadata.latest_version,
                release_date=metadata.release_date,
                metadata_source=metadata.source,
            )
        )
        report = reports[-1]
        if metadata.source != "pypi":
            report.notes.append(f"Latest metadata source: {metadata.source}.")

    reports = _sort_reports(reports)
    reports = _filter_reports(reports, signals=signals, policies=policies, top=top)

    rendered = {
        "json": _render_json(
            reports, pyproject_path=pyproject_path, requirement_paths=requirement_paths
        ),
        "md": _render_markdown(
            reports, pyproject_path=pyproject_path, requirement_paths=requirement_paths
        ),
    }[output_format]
    sys.stdout.write(rendered)
    return 1 if _should_fail(reports, fail_on) else 0


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
    parser.add_argument(
        "--fail-on",
        choices=["critical", "high", "medium", "watch", "investigate", "unknown", "never"],
        default="never",
        help="Exit with code 1 when a package meets or exceeds this signal threshold.",
    )
    parser.add_argument(
        "--cache-path",
        type=Path,
        default=DEFAULT_CACHE_PATH,
        help=f"Path to the metadata cache file (default: {DEFAULT_CACHE_PATH})",
    )
    parser.add_argument(
        "--cache-ttl-hours",
        type=float,
        default=24.0,
        help="Hours before cached metadata is considered stale (default: 24).",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip PyPI calls and use cached metadata when available.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=8,
        help="Maximum number of parallel PyPI metadata requests (default: 8).",
    )
    parser.add_argument(
        "--signal",
        action="append",
        choices=["critical", "high", "medium", "watch", "investigate", "unknown"],
        default=None,
        help="Show only packages with the selected upgrade signal(s). Can be passed multiple times.",
    )
    parser.add_argument(
        "--policy",
        action="append",
        choices=["allowed", "blocked", "unknown", "unbounded"],
        default=None,
        help="Show only packages with the selected policy status(es). Can be passed multiple times.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=None,
        help="Limit output to the highest-risk N packages after filtering.",
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
        fail_on=args.fail_on,
        cache_path=args.cache_path,
        cache_ttl_hours=args.cache_ttl_hours,
        offline=bool(args.offline),
        max_workers=max(args.max_workers, 1),
        signals=args.signal,
        policies=args.policy,
        top=args.top,
    )


if __name__ == "__main__":
    raise SystemExit(main())
