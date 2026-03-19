from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
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
    project_python_requires: str | None
    current_version: str
    target_version: str
    target_release_date: str | None
    latest_compatible_version: str | None
    latest_compatible_release_date: str | None
    compatibility_status: str
    alignment: str
    constraint_status: str
    latest_version: str
    latest_release_date: str | None
    metadata_source: str
    version_gap: str
    release_age_days: int | None
    upgrade_signal: str
    risk_score: int
    manifest_action: str
    suggested_version: str | None
    impact_area: str
    validation_commands: list[str]
    next_action: str
    notes: list[str]


@dataclass(frozen=True)
class PackageMetadata:
    latest_version: str
    release_date: str | None
    compatible_version: str | None
    compatible_release_date: str | None
    compatibility_status: str
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
    if candidate.startswith(("-e", "--editable")):
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
    return _load_requirements_dependencies_recursive(requirements_path, seen=set())


def _load_requirements_dependencies_recursive(
    requirements_path: Path,
    *,
    seen: set[Path],
) -> list[Dependency]:
    resolved_path = requirements_path.resolve()
    if resolved_path in seen:
        return []
    seen.add(resolved_path)
    deps: list[Dependency] = []
    for raw_line in requirements_path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.split("#", 1)[0].strip()
        if not stripped:
            continue
        include_target = _parse_requirements_include(stripped)
        if include_target is not None:
            include_path = (requirements_path.parent / include_target).resolve()
            if include_path.exists():
                deps.extend(
                    _load_requirements_dependencies_recursive(include_path, seen=seen)
                )
            continue
        candidate = _normalize_requirement_line(stripped)
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


def _parse_requirements_include(line: str) -> str | None:
    for prefix in ("-r ", "--requirement ", "-c ", "--constraint "):
        if line.startswith(prefix):
            include_target = line[len(prefix) :].strip()
            return include_target or None
    return None


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


def _latest_pypi_metadata(
    package: str,
    timeout_s: float,
    *,
    project_python_requires: str | None,
    include_prereleases: bool,
) -> tuple[str, str | None, str | None, str | None, str]:
    url = f"https://pypi.org/pypi/{package}/json"
    request = urllib.request.Request(url, headers={"User-Agent": "sdetkit-upgrade-audit/2.1"})
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
    compatible_version, compatible_release_date, compatibility_status = _latest_compatible_release(
        payload,
        project_python_requires=project_python_requires,
        include_prereleases=include_prereleases,
    )
    return version, release_date, compatible_version, compatible_release_date, compatibility_status


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


def _cache_entry_fresh(
    entry: dict[str, str | float | None],
    ttl_hours: float,
    *,
    include_prereleases: bool,
) -> bool:
    fetched_at = entry.get("fetched_at")
    if not isinstance(fetched_at, (int, float)):
        return False
    if entry.get("include_prereleases") is not include_prereleases:
        return False
    age_s = dt.datetime.now(dt.UTC).timestamp() - float(fetched_at)
    return age_s <= max(ttl_hours, 0) * 3600


def _metadata_from_cache(entry: dict[str, str | float | None], *, source: str) -> PackageMetadata:
    latest_version = entry.get("latest_version")
    release_date = entry.get("release_date")
    compatible_version = entry.get("compatible_version")
    compatible_release_date = entry.get("compatible_release_date")
    compatibility_status = entry.get("compatibility_status")
    if not isinstance(latest_version, str):
        latest_version = "unknown"
    if release_date is not None and not isinstance(release_date, str):
        release_date = None
    if compatible_version is not None and not isinstance(compatible_version, str):
        compatible_version = None
    if compatible_release_date is not None and not isinstance(compatible_release_date, str):
        compatible_release_date = None
    if not isinstance(compatibility_status, str):
        compatibility_status = "unknown"
    return PackageMetadata(
        latest_version=latest_version,
        release_date=release_date,
        compatible_version=compatible_version,
        compatible_release_date=compatible_release_date,
        compatibility_status=compatibility_status,
        source=source,
    )


def _fetch_package_metadata(
    package: str,
    *,
    timeout_s: float,
    cache: dict[str, dict[str, str | float | None]],
    cache_ttl_hours: float,
    offline: bool,
    project_python_requires: str | None,
    include_prereleases: bool,
) -> PackageMetadata:
    cached_entry = cache.get(package)
    if cached_entry and _cache_entry_fresh(
        cached_entry,
        cache_ttl_hours,
        include_prereleases=include_prereleases,
    ):
        return _metadata_from_cache(cached_entry, source="cache")

    if offline:
        if cached_entry:
            source = (
                "cache"
                if _cache_entry_fresh(
                    cached_entry,
                    cache_ttl_hours,
                    include_prereleases=include_prereleases,
                )
                else "cache-stale"
            )
            return _metadata_from_cache(cached_entry, source=source)
        return PackageMetadata(
            latest_version="offline-no-cache",
            release_date=None,
            compatible_version=None,
            compatible_release_date=None,
            compatibility_status="unknown",
            source="offline",
        )

    try:
        (
            latest_version,
            release_date,
            compatible_version,
            compatible_release_date,
            compatibility_status,
        ) = _latest_pypi_metadata(
            package,
            timeout_s=timeout_s,
            project_python_requires=project_python_requires,
            include_prereleases=include_prereleases,
        )
    except urllib.error.HTTPError as exc:
        latest_version, release_date = f"http-{exc.code}", None
        compatible_version, compatible_release_date, compatibility_status = None, None, "unknown"
    except urllib.error.URLError:
        if cached_entry:
            return _metadata_from_cache(cached_entry, source="cache-stale")
        latest_version, release_date = "network-error", None
        compatible_version, compatible_release_date, compatibility_status = None, None, "unknown"

    cache[package] = {
        "fetched_at": dt.datetime.now(dt.UTC).timestamp(),
        "include_prereleases": include_prereleases,
        "latest_version": latest_version,
        "release_date": release_date,
        "compatible_version": compatible_version,
        "compatible_release_date": compatible_release_date,
        "compatibility_status": compatibility_status,
    }
    return PackageMetadata(
        latest_version=latest_version,
        release_date=release_date,
        compatible_version=compatible_version,
        compatible_release_date=compatible_release_date,
        compatibility_status=compatibility_status,
        source="pypi",
    )


def _collect_package_metadata(
    packages: list[str],
    *,
    timeout_s: float,
    cache_path: Path,
    cache_ttl_hours: float,
    offline: bool,
    max_workers: int,
    project_python_requires: str | None,
    include_prereleases: bool,
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
                project_python_requires=project_python_requires,
                include_prereleases=include_prereleases,
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
                    project_python_requires=project_python_requires,
                    include_prereleases=include_prereleases,
                ): package
                for package in packages
            }
            for future in as_completed(futures):
                metadata[futures[future]] = future.result()

    if not offline:
        _persist_cache(cache_path, cache)
    return metadata


def _load_project_python_requires(pyproject_path: Path) -> str | None:
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = data.get("project", {})
    value = project.get("requires-python")
    return str(value).strip() if isinstance(value, str) and value.strip() else None


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


def _parse_python_constraints(specifier: str | None) -> list[tuple[str, str]]:
    if not specifier:
        return []
    return [(operator, version) for operator, version in CONSTRAINT_RE.findall(specifier)]


def _candidate_repo_python_versions(project_python_requires: str | None) -> list[str]:
    constraints = _parse_python_constraints(project_python_requires)
    if not constraints:
        return []
    minimums = [
        version
        for operator, version in constraints
        if operator in {">=", ">", "~=", "=="}
    ]
    if minimums:
        return [sorted(minimums, key=_version_key)[-1]]
    upper_bounds = [version for operator, version in constraints if operator in {"<", "<="}]
    if upper_bounds:
        upper = sorted(upper_bounds, key=_version_key)[0]
        parts = _major_minor_patch(upper)
        if parts is not None:
            major, minor, _patch = parts
            if minor > 0:
                return [f"{major}.{minor - 1}"]
            if major > 0:
                return [f"{major - 1}.9"]
    return []


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


def _specifier_allows_version(specifier: str | None, version: str) -> bool | None:
    constraints = _parse_python_constraints(specifier)
    if not constraints:
        return None
    return all(_constraint_allows_version(constraint, version) for constraint in constraints)


def _release_is_python_compatible(
    release_files: list[dict[str, object]],
    *,
    project_python_requires: str | None,
) -> tuple[bool | None, str]:
    repo_versions = _candidate_repo_python_versions(project_python_requires)
    if not repo_versions:
        return None, "unknown"
    if not release_files:
        return None, "unknown"

    compatibility_observed = False
    for release_file in release_files:
        if not isinstance(release_file, dict) or bool(release_file.get("yanked")):
            continue
        requires_python = release_file.get("requires_python")
        if requires_python is not None and not isinstance(requires_python, str):
            continue
        compatibility_observed = True
        if all(_specifier_allows_version(requires_python, version) is not False for version in repo_versions):
            return True, "compatible"
    if compatibility_observed:
        return False, "requires-newer-python"
    return None, "unknown"


def _release_date_from_files(release_files: list[dict[str, object]]) -> str | None:
    dates = [
        str(item["upload_time_iso_8601"])
        for item in release_files
        if isinstance(item, dict) and item.get("upload_time_iso_8601")
    ]
    return sorted(dates)[0] if dates else None


def _is_prerelease_version(version: str) -> bool:
    normalized = version.strip().lower()
    return bool(re.search(r"(?<![a-z])(a|alpha|b|beta|rc|c|pre|preview|dev)\d*", normalized))


def _latest_compatible_release(
    payload: dict[str, object],
    *,
    project_python_requires: str | None,
    include_prereleases: bool,
) -> tuple[str | None, str | None, str]:
    releases = payload.get("releases", {})
    if not isinstance(releases, dict):
        return None, None, "unknown"

    latest_compatible_version: str | None = None
    latest_compatible_release_date: str | None = None
    latest_status = "unknown"
    for version, release_files in sorted(releases.items(), key=lambda item: _version_key(str(item[0])), reverse=True):
        if not isinstance(version, str) or not isinstance(release_files, list):
            continue
        if not include_prereleases and _is_prerelease_version(version):
            continue
        compatible, status = _release_is_python_compatible(
            release_files,
            project_python_requires=project_python_requires,
        )
        if compatible is True:
            latest_compatible_version = version
            latest_compatible_release_date = _release_date_from_files(release_files)
            latest_status = (
                "compatible-latest"
                if version == str(payload.get("info", {}).get("version") or "")
                else "compatible-available"
            )
            break
        if status == "requires-newer-python" and latest_status == "unknown":
            latest_status = status
    return latest_compatible_version, latest_compatible_release_date, latest_status


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
        has_pin = any(dep.pinned_version for dep in deps)
        has_range = any(dep.pinned_version is None for dep in deps)
        if has_pin and has_range:
            return "floor-lock"
        return "compatible"
    return "drift"


def _manifest_action(
    *,
    current_version: str,
    latest_version: str,
    alignment: str,
    constraint_status: str,
    version_gap: str,
) -> tuple[str, str | None]:
    unavailable_versions = {"unknown", "network-error", "offline-no-cache"}
    if latest_version in unavailable_versions or latest_version.startswith("http-"):
        return "investigate-metadata", None
    if current_version in {"unbounded", "unknown"}:
        return "establish-baseline", latest_version if latest_version != current_version else None
    if current_version == latest_version:
        return "none", None
    if constraint_status == "allowed":
        if alignment in {"floor-lock", "range-or-unpinned"}:
            return "raise-floor", latest_version
        return "refresh-pin", latest_version
    if version_gap == "major":
        return "plan-major-upgrade", latest_version
    return "stage-upgrade", latest_version


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
    project_python_requires: str | None = None,
    compatible_version: str | None = None,
    compatible_release_date: str | None = None,
    compatibility_status: str = "unknown",
    metadata_source: str = "pypi",
) -> PackageReport:
    sources = sorted({dep.source for dep in deps})
    groups = sorted({dep.group for dep in deps})
    requirements = sorted({dep.raw for dep in deps})
    pinned_versions = sorted({dep.pinned_version for dep in deps if dep.pinned_version})
    current_version = _pick_current_version(deps)
    target_version = compatible_version or latest_version
    target_release_date = compatible_release_date if compatible_version else release_date
    version_gap = _classify_version_gap(current_version, target_version)
    release_age_days = _release_age_days(target_release_date)
    alignment = _infer_alignment(deps, current_version)
    constraint_status = _constraint_status(deps, target_version)

    notes: list[str] = []
    if alignment == "drift":
        notes.append("Cross-manifest requirement drift detected.")
    elif alignment == "compatible":
        notes.append("Cross-manifest requirements differ but remain mutually compatible.")
    elif alignment == "floor-lock":
        notes.append(
            "Cross-manifest requirements follow a floor-and-lock pattern with a tested pinned baseline."
        )
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
    if project_python_requires:
        notes.append(f"Repo Python support policy: {project_python_requires}.")
    if compatibility_status == "compatible-available" and compatible_version and compatible_version != latest_version:
        notes.append(
            "Newest PyPI release requires a newer Python baseline than this repo; "
            f"using compatible target {compatible_version} for action planning."
        )
    elif compatibility_status == "requires-newer-python":
        notes.append(
            "Available PyPI releases appear to require a newer Python baseline than this repo currently declares."
        )

    upgrade_signal = "watch"
    if alignment == "drift":
        upgrade_signal = "critical" if version_gap == "major" else "high"
    elif alignment == "floor-lock" and constraint_status == "allowed":
        upgrade_signal = "watch"
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
    elif alignment == "floor-lock":
        risk_score += 5
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

    manifest_action, suggested_version = _manifest_action(
        current_version=current_version,
        latest_version=target_version,
        alignment=alignment,
        constraint_status=constraint_status,
        version_gap=version_gap,
    )
    impact_area = _impact_area(
        PackageReport(
            name=name,
            sources=sources,
            groups=groups,
            requirements=requirements,
            pinned_versions=pinned_versions,
            project_python_requires=project_python_requires,
            current_version=current_version,
            target_version=target_version,
            target_release_date=target_release_date,
            latest_compatible_version=compatible_version,
            latest_compatible_release_date=compatible_release_date,
            compatibility_status=compatibility_status,
            alignment=alignment,
            constraint_status=constraint_status,
            latest_version=latest_version,
            latest_release_date=release_date,
            metadata_source=metadata_source,
            version_gap=version_gap,
            release_age_days=release_age_days,
            upgrade_signal=upgrade_signal,
            risk_score=risk_score,
            manifest_action=manifest_action,
            suggested_version=suggested_version,
            impact_area="repo-tooling",
            validation_commands=[],
            next_action="",
            notes=[],
        )
    )
    validation_commands = _validation_commands_for_impact(impact_area)

    next_action = "Keep under observation; no immediate action required."
    if manifest_action == "raise-floor":
        next_action = (
            "Raise the tested floor in flexible manifests, refresh pins, and validate the package in the next maintenance window."
        )
    elif manifest_action == "refresh-pin":
        next_action = "Refresh pinned manifests to the newer tested version and rerun targeted validation."
    elif upgrade_signal == "critical":
        next_action = (
            "Resolve manifest drift first, then validate the major upgrade in a dedicated branch."
        )
    elif manifest_action == "plan-major-upgrade":
        next_action = "Plan an upgrade spike with regression coverage before the next release cut."
    elif manifest_action == "stage-upgrade":
        next_action = (
            "Queue the upgrade for the next maintenance batch and validate targeted smoke tests."
        )
    elif upgrade_signal == "watch":
        next_action = (
            "Keep the package on watch; the declared version policy already covers the latest release."
            if constraint_status == "allowed"
            else "Track the package and batch it with nearby dependency maintenance work."
        )
    elif manifest_action == "investigate-metadata":
        next_action = "Retry metadata collection and inspect package naming, cache freshness, or connectivity issues."
    elif upgrade_signal == "unknown":
        next_action = (
            "Review the declared version range manually because the gap could not be classified."
        )
    elif manifest_action == "establish-baseline":
        next_action = "Pin or bound the package explicitly before attempting future upgrade automation."

    if manifest_action != "none":
        notes.append(f"Recommended manifest action: {manifest_action}.")
    if suggested_version is not None:
        notes.append(f"Suggested target version: {suggested_version}.")
    notes.append(f"Repo impact area: {impact_area}.")

    return PackageReport(
        name=name,
        sources=sources,
        groups=groups,
        requirements=requirements,
        pinned_versions=pinned_versions,
        project_python_requires=project_python_requires,
        current_version=current_version,
        target_version=target_version,
        target_release_date=target_release_date,
        latest_compatible_version=compatible_version,
        latest_compatible_release_date=compatible_release_date,
        compatibility_status=compatibility_status,
        alignment=alignment,
        constraint_status=constraint_status,
        latest_version=latest_version,
        latest_release_date=release_date,
        metadata_source=metadata_source,
        version_gap=version_gap,
        release_age_days=release_age_days,
        upgrade_signal=upgrade_signal,
        risk_score=risk_score,
        manifest_action=manifest_action,
        suggested_version=suggested_version,
        impact_area=impact_area,
        validation_commands=validation_commands,
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
                "manifest_action": report.manifest_action,
                "suggested_version": report.suggested_version,
                "impact_area": report.impact_area,
                "validation_commands": report.validation_commands,
                "next_action": report.next_action,
                "lane": _recommended_lane(report),
            }
        )
    return queue


def _recommended_lane(report: PackageReport) -> str:
    if report.alignment == "drift":
        return "stabilize-manifests"
    if report.manifest_action in {"raise-floor", "refresh-pin"}:
        return "refresh-baselines"
    if report.upgrade_signal in {"critical", "high"}:
        return "upgrade-now"
    if report.upgrade_signal == "medium":
        return "next-maintenance-batch"
    if report.upgrade_signal == "investigate":
        return "investigate-metadata"
    if report.constraint_status == "allowed":
        return "policy-covered-watchlist"
    return "backlog-watchlist"


def _impact_area(report: PackageReport) -> str:
    groups = set(report.groups)
    package = report.name

    if "default" in groups:
        return "runtime-core"
    if groups & {"telegram", "whatsapp"} or package in {"python-telegram-bot", "twilio"}:
        return "integration-adapters"
    if "docs" in groups or package.startswith("mkdocs"):
        return "docs-tooling"
    if "packaging" in groups or package in {"build", "twine", "check-wheel-contents"}:
        return "packaging-release"
    if package in {"pip-audit", "cyclonedx-bom"}:
        return "security-compliance"
    if package in {
        "pytest",
        "pytest-asyncio",
        "pytest-cov",
        "hypothesis",
        "mutmut",
        "ruff",
        "mypy",
        "pre-commit",
    }:
        return "quality-tooling"
    return "repo-tooling"


def _validation_commands_for_impact(impact_area: str) -> list[str]:
    if impact_area == "runtime-core":
        return [
            "bash ci.sh quick --skip-docs --artifact-dir build",
            "bash quality.sh cov",
        ]
    if impact_area == "integration-adapters":
        return [
            "bash ci.sh quick --skip-docs --artifact-dir build",
            "python -m pytest -q tests/test_notify_plugins.py tests/test_notify_plugins_extra.py",
        ]
    if impact_area == "docs-tooling":
        return [
            "bash ci.sh all --artifact-dir build",
            "make docs-build",
        ]
    if impact_area == "packaging-release":
        return [
            "make package-validate",
            "make release-preflight",
        ]
    if impact_area == "security-compliance":
        return [
            "bash security.sh",
            "python -m sdetkit security enforce --format json",
        ]
    if impact_area == "quality-tooling":
        return [
            "bash quality.sh ci",
            "bash quality.sh cov",
        ]
    return [
        "bash ci.sh quick --skip-docs --artifact-dir build",
        "bash quality.sh ci",
    ]


def _lane_summary(reports: list[PackageReport]) -> list[dict[str, object]]:
    buckets: dict[str, list[PackageReport]] = {}
    for report in reports:
        buckets.setdefault(_recommended_lane(report), []).append(report)
    ordered = sorted(
        buckets.items(),
        key=lambda item: (-max((r.risk_score for r in item[1]), default=0), item[0]),
    )
    return [
        {
            "lane": lane,
            "count": len(items),
            "max_risk_score": max((r.risk_score for r in items), default=0),
            "packages": [r.name for r in items[:5]],
        }
        for lane, items in ordered
    ]


def _impact_summary(reports: list[PackageReport]) -> list[dict[str, object]]:
    buckets: dict[str, list[PackageReport]] = {}
    for report in reports:
        buckets.setdefault(report.impact_area, []).append(report)
    ordered = sorted(
        buckets.items(),
        key=lambda item: (
            -max((report.risk_score for report in item[1]), default=0),
            -sum(1 for report in item[1] if _is_actionable_upgrade(report)),
            item[0],
        ),
    )
    return [
        {
            "impact_area": impact_area,
            "count": len(items),
            "actionable_packages": sum(1 for report in items if _is_actionable_upgrade(report)),
            "max_risk_score": max((report.risk_score for report in items), default=0),
            "packages": [report.name for report in items[:5]],
            "validation_commands": items[0].validation_commands if items else [],
        }
        for impact_area, items in ordered
    ]


def _is_actionable_upgrade(report: PackageReport) -> bool:
    return report.manifest_action != "none"


def _report_summary(reports: list[PackageReport]) -> dict[str, int]:
    return {
        "packages_audited": len(reports),
        "manifest_drift_packages": sum(1 for report in reports if report.alignment == "drift"),
        "compatible_constraint_packages": sum(
            1 for report in reports if report.alignment == "compatible"
        ),
        "floor_lock_packages": sum(1 for report in reports if report.alignment == "floor-lock"),
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
            1 for report in reports if report.metadata_source.startswith("cache")
        ),
        "stale_metadata_packages": sum(
            1 for report in reports if report.metadata_source == "cache-stale"
        ),
        "python_compatible_latest_packages": sum(
            1 for report in reports if report.compatibility_status == "compatible-latest"
        ),
        "python_compatible_fallback_packages": sum(
            1 for report in reports if report.compatibility_status == "compatible-available"
        ),
        "python_incompatible_latest_packages": sum(
            1 for report in reports if report.compatibility_status == "requires-newer-python"
        ),
        "actionable_packages": sum(1 for report in reports if _is_actionable_upgrade(report)),
        "runtime_core_packages": sum(1 for report in reports if report.impact_area == "runtime-core"),
        "quality_tooling_packages": sum(
            1 for report in reports if report.impact_area == "quality-tooling"
        ),
        "integration_adapter_packages": sum(
            1 for report in reports if report.impact_area == "integration-adapters"
        ),
        "max_risk_score": max((report.risk_score for report in reports), default=0),
    }


def _group_summary(reports: list[PackageReport]) -> list[dict[str, object]]:
    buckets: dict[str, list[PackageReport]] = {}
    for report in reports:
        for group in report.groups:
            buckets.setdefault(group, []).append(report)
    ordered = sorted(
        buckets.items(),
        key=lambda item: (
            -max((report.risk_score for report in item[1]), default=0),
            -len(item[1]),
            item[0],
        ),
    )
    return [
        {
            "group": group,
            "count": len(items),
            "max_risk_score": max((report.risk_score for report in items), default=0),
            "actionable_packages": sum(1 for report in items if _is_actionable_upgrade(report)),
            "packages": [report.name for report in items[:5]],
        }
        for group, items in ordered
    ]


def _source_summary(reports: list[PackageReport]) -> list[dict[str, object]]:
    buckets: dict[str, list[PackageReport]] = {}
    for report in reports:
        for source in report.sources:
            buckets.setdefault(source, []).append(report)
    ordered = sorted(
        buckets.items(),
        key=lambda item: (
            -max((report.risk_score for report in item[1]), default=0),
            -len(item[1]),
            item[0],
        ),
    )
    return [
        {
            "source": source,
            "count": len(items),
            "max_risk_score": max((report.risk_score for report in items), default=0),
            "actionable_packages": sum(1 for report in items if _is_actionable_upgrade(report)),
            "packages": [report.name for report in items[:5]],
        }
        for source, items in ordered
    ]


def _matches_package_filters(report: PackageReport, package_filters: list[str] | None) -> bool:
    if not package_filters:
        return True
    normalized = report.name.lower()
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in package_filters)


def _matches_any_filter(values: list[str], allowed_filters: list[str] | None) -> bool:
    if not allowed_filters:
        return True
    normalized_values = {value.lower() for value in values}
    return any(filter_value in normalized_values for filter_value in allowed_filters)


def _matches_dependency_filters(
    deps: list[Dependency],
    *,
    packages: list[str] | None = None,
    groups: list[str] | None = None,
    sources: list[str] | None = None,
) -> bool:
    if packages:
        package_filters = [item.strip().lower() for item in packages if item.strip()]
        if package_filters and not any(
            fnmatch.fnmatch(dep.name.lower(), pattern) for pattern in package_filters for dep in deps
        ):
            return False
    if groups:
        group_filters = {item.strip().lower() for item in groups if item.strip()}
        if group_filters and not any(dep.group.lower() in group_filters for dep in deps):
            return False
    if sources:
        source_filters = {item.strip().lower() for item in sources if item.strip()}
        if source_filters and not any(dep.source.lower() in source_filters for dep in deps):
            return False
    return True


def _action_summary(reports: list[PackageReport]) -> list[dict[str, object]]:
    buckets: dict[str, list[PackageReport]] = {}
    for report in reports:
        buckets.setdefault(report.manifest_action, []).append(report)
    ordered = sorted(
        buckets.items(),
        key=lambda item: (
            -sum(1 for report in item[1] if _is_actionable_upgrade(report)),
            -max((report.risk_score for report in item[1]), default=0),
            item[0],
        ),
    )
    return [
        {
            "manifest_action": action,
            "count": len(items),
            "actionable_packages": sum(1 for report in items if _is_actionable_upgrade(report)),
            "max_risk_score": max((report.risk_score for report in items), default=0),
            "packages": [report.name for report in items[:5]],
        }
        for action, items in ordered
    ]


def _filter_reports(
    reports: list[PackageReport],
    *,
    signals: list[str] | None = None,
    policies: list[str] | None = None,
    packages: list[str] | None = None,
    groups: list[str] | None = None,
    sources: list[str] | None = None,
    metadata_sources: list[str] | None = None,
    impact_areas: list[str] | None = None,
    manifest_actions: list[str] | None = None,
    outdated_only: bool = False,
    top: int | None = None,
) -> list[PackageReport]:
    filtered = reports
    if signals:
        allowed_signals = {item.strip() for item in signals if item.strip()}
        filtered = [report for report in filtered if report.upgrade_signal in allowed_signals]
    if policies:
        allowed_policies = {item.strip() for item in policies if item.strip()}
        filtered = [report for report in filtered if report.constraint_status in allowed_policies]
    if packages:
        package_filters = [item.strip().lower() for item in packages if item.strip()]
        filtered = [
            report for report in filtered if _matches_package_filters(report, package_filters)
        ]
    if groups:
        group_filters = [item.strip().lower() for item in groups if item.strip()]
        filtered = [report for report in filtered if _matches_any_filter(report.groups, group_filters)]
    if sources:
        source_filters = [item.strip().lower() for item in sources if item.strip()]
        filtered = [
            report for report in filtered if _matches_any_filter(report.sources, source_filters)
        ]
    if metadata_sources:
        allowed_sources = {item.strip() for item in metadata_sources if item.strip()}
        filtered = [report for report in filtered if report.metadata_source in allowed_sources]
    if impact_areas:
        allowed_impact_areas = {item.strip() for item in impact_areas if item.strip()}
        filtered = [report for report in filtered if report.impact_area in allowed_impact_areas]
    if manifest_actions:
        allowed_actions = {item.strip() for item in manifest_actions if item.strip()}
        filtered = [report for report in filtered if report.manifest_action in allowed_actions]
    if outdated_only:
        filtered = [report for report in filtered if _is_actionable_upgrade(report)]
    if top is not None:
        filtered = filtered[: max(top, 0)]
    return filtered


def _render_markdown(
    reports: list[PackageReport],
    *,
    pyproject_path: Path,
    requirement_paths: list[Path],
) -> str:
    summary = _report_summary(reports)
    lines = [
        "# Upgrade audit",
        "",
        f"Source pyproject: `{pyproject_path}`",
        f"Requirement manifests: {', '.join(f'`{path}`' for path in requirement_paths) if requirement_paths else '`none`'}",
        "",
        f"- packages audited: {summary['packages_audited']}",
        f"- manifest drift packages: {summary['manifest_drift_packages']}",
        f"- compatible multi-manifest packages: {summary['compatible_constraint_packages']}",
        f"- floor-and-lock baseline packages: {summary['floor_lock_packages']}",
        f"- policy-covered latest releases: {summary['policy_covered_packages']}",
        f"- policy-blocked latest releases: {summary['policy_blocked_packages']}",
        f"- critical upgrade signals: {summary['critical_upgrade_signals']}",
        f"- high-priority upgrade signals: {summary['high_priority_upgrade_signals']}",
        f"- medium-priority upgrade signals: {summary['medium_priority_upgrade_signals']}",
        f"- investigate signals: {summary['investigate_upgrade_signals']}",
        f"- packages using cached metadata: {summary['cached_metadata_packages']}",
        f"- stale cached metadata packages: {summary['stale_metadata_packages']}",
        f"- latest releases compatible with repo Python policy: {summary['python_compatible_latest_packages']}",
        f"- fallback compatible targets below latest: {summary['python_compatible_fallback_packages']}",
        f"- latest releases requiring newer Python: {summary['python_incompatible_latest_packages']}",
        f"- actionable upgrade candidates: {summary['actionable_packages']}",
        f"- runtime core packages: {summary['runtime_core_packages']}",
        f"- quality tooling packages: {summary['quality_tooling_packages']}",
        f"- integration adapter packages: {summary['integration_adapter_packages']}",
        "",
        "| Package | Impact | Current | Target | Latest PyPI | Py policy | Source | Gap | Alignment | Policy | Signal | Risk | Action | Suggested | Release age (days) | Requirements |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for report in reports:
        release_age = "-" if report.release_age_days is None else str(report.release_age_days)
        requirements = " <br> ".join(f"`{item}`" for item in report.requirements)
        lines.append(
            "| "
            f"`{report.name}` | {report.impact_area} | `{report.current_version}` | `{report.target_version}` | `{report.latest_version}` | {report.compatibility_status} | {report.metadata_source} | {report.version_gap} | "
            f"{report.alignment} | {report.constraint_status} | {report.upgrade_signal} | {report.risk_score} | {report.manifest_action} | {report.suggested_version or '-'} | {release_age} | {requirements} |"
        )
    lines.extend(["", "## Priority queue", ""])
    for item in _priority_queue(reports):
        lines.append(
            f"- `{item['name']}` [{item['signal']}, risk {item['risk_score']}, lane {item['lane']}, action {item['manifest_action']}]"
            + (f" target `{item['suggested_version']}`" if item['suggested_version'] else "")
            + f" → {item['next_action']}"
        )
    lines.extend(["", "## Recommended upgrade lanes", ""])
    for item in _lane_summary(reports):
        pkg_list = ", ".join(f"`{name}`" for name in item["packages"])
        lines.append(
            f"- **{item['lane']}**: {item['count']} package(s), max risk {item['max_risk_score']}"
            + (f" — {pkg_list}" if pkg_list else "")
        )
    lines.extend(["", "## Repo impact map", ""])
    for item in _impact_summary(reports):
        pkg_list = ", ".join(f"`{name}`" for name in item["packages"])
        validations = ", ".join(f"`{command}`" for command in item["validation_commands"])
        lines.append(
            f"- **{item['impact_area']}**: {item['count']} package(s), actionable {item['actionable_packages']}, max risk {item['max_risk_score']}"
            + (f" — {pkg_list}" if pkg_list else "")
            + (f" — validate with {validations}" if validations else "")
        )
    lines.extend(["", "## Manifest actions", ""])
    for item in _action_summary(reports):
        pkg_list = ", ".join(f"`{name}`" for name in item["packages"])
        lines.append(
            f"- **{item['manifest_action']}**: {item['count']} package(s), actionable {item['actionable_packages']}, max risk {item['max_risk_score']}"
            + (f" — {pkg_list}" if pkg_list else "")
        )
    lines.extend(["", "## Dependency groups", ""])
    for item in _group_summary(reports):
        pkg_list = ", ".join(f"`{name}`" for name in item["packages"])
        lines.append(
            f"- **{item['group']}**: {item['count']} package(s), actionable {item['actionable_packages']}, max risk {item['max_risk_score']}"
            + (f" — {pkg_list}" if pkg_list else "")
        )
    lines.extend(["", "## Manifest sources", ""])
    for item in _source_summary(reports):
        pkg_list = ", ".join(f"`{name}`" for name in item["packages"])
        lines.append(
            f"- **{item['source']}**: {item['count']} package(s), actionable {item['actionable_packages']}, max risk {item['max_risk_score']}"
            + (f" — {pkg_list}" if pkg_list else "")
        )
    lines.extend(["", "## Focus notes", ""])
    for report in reports:
        note_text = " ".join(report.notes) if report.notes else "No additional notes."
        validations = ", ".join(f"`{command}`" for command in report.validation_commands)
        lines.append(
            f"- `{report.name}` [{report.impact_area}] ({report.next_action}) {note_text}"
            + (f" Validate with {validations}." if validations else "")
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
        "summary": _report_summary(reports),
        "priority_queue": _priority_queue(reports),
        "lanes": _lane_summary(reports),
        "impact": _impact_summary(reports),
        "actions": _action_summary(reports),
        "groups": _group_summary(reports),
        "sources": _source_summary(reports),
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
    packages: list[str] | None = None,
    groups: list[str] | None = None,
    sources: list[str] | None = None,
    metadata_sources: list[str] | None = None,
    impact_areas: list[str] | None = None,
    manifest_actions: list[str] | None = None,
    outdated_only: bool = False,
    top: int | None = None,
    include_prereleases: bool = False,
) -> int:
    dependencies = _load_dependencies(pyproject_path, requirement_paths)
    project_python_requires = _load_project_python_requires(pyproject_path)

    if not dependencies:
        print("No dependencies found in the configured manifests.")
        return 0

    by_package: dict[str, list[Dependency]] = {}
    for dep in dependencies:
        by_package.setdefault(dep.name, []).append(dep)

    package_filters = packages
    if packages or groups or sources:
        by_package = {
            name: deps
            for name, deps in by_package.items()
            if _matches_dependency_filters(
                deps,
                packages=packages,
                groups=groups,
                sources=sources,
            )
        }
    package_names = sorted(by_package)
    if not package_names:
        rendered = {
            "json": _render_json(
                [], pyproject_path=pyproject_path, requirement_paths=requirement_paths
            ),
            "md": _render_markdown(
                [], pyproject_path=pyproject_path, requirement_paths=requirement_paths
            ),
        }[output_format]
        sys.stdout.write(rendered)
        return 0

    metadata_by_package = _collect_package_metadata(
        package_names,
        timeout_s=timeout_s,
        cache_path=cache_path,
        cache_ttl_hours=cache_ttl_hours,
        offline=offline,
        max_workers=max_workers,
        project_python_requires=project_python_requires,
        include_prereleases=include_prereleases,
    )
    reports: list[PackageReport] = []
    for package in package_names:
        metadata = metadata_by_package[package]
        reports.append(
            _build_package_report(
                package,
                by_package[package],
                latest_version=metadata.latest_version,
                release_date=metadata.release_date,
                project_python_requires=project_python_requires,
                compatible_version=metadata.compatible_version,
                compatible_release_date=metadata.compatible_release_date,
                compatibility_status=metadata.compatibility_status,
                metadata_source=metadata.source,
            )
        )
        report = reports[-1]
        if metadata.source != "pypi":
            report.notes.append(f"Latest metadata source: {metadata.source}.")

    reports = _sort_reports(reports)
    reports = _filter_reports(
        reports,
        signals=signals,
        policies=policies,
        packages=package_filters,
        groups=groups,
        sources=sources,
        metadata_sources=metadata_sources,
        impact_areas=impact_areas,
        manifest_actions=manifest_actions,
        outdated_only=outdated_only,
        top=top,
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
    return 1 if _should_fail(reports, fail_on) else 0


def build_parser(*, prog: str = "upgrade-audit") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description=(
            "Audit dependency manifests, highlight drift, and report the latest PyPI versions "
            "for each declared package."
        ),
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
        "--include-prereleases",
        action="store_true",
        help="Include prerelease/dev versions when choosing compatible upgrade targets.",
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
        "--package",
        action="append",
        default=None,
        help="Show only packages matching the provided name or glob pattern. Can be passed multiple times.",
    )
    parser.add_argument(
        "--group",
        action="append",
        default=None,
        help="Show only packages declared in the selected dependency group(s). Can be passed multiple times.",
    )
    parser.add_argument(
        "--source",
        action="append",
        default=None,
        help="Show only packages declared in the selected manifest source file(s). Can be passed multiple times.",
    )
    parser.add_argument(
        "--metadata-source",
        action="append",
        choices=["pypi", "cache", "cache-stale", "offline"],
        default=None,
        help="Show only packages resolved from the selected metadata source(s).",
    )
    parser.add_argument(
        "--impact-area",
        action="append",
        choices=[
            "runtime-core",
            "quality-tooling",
            "integration-adapters",
            "docs-tooling",
            "packaging-release",
            "security-compliance",
            "repo-tooling",
        ],
        default=None,
        help="Show only packages in the selected repo impact area(s).",
    )
    parser.add_argument(
        "--manifest-action",
        action="append",
        choices=[
            "none",
            "refresh-pin",
            "raise-floor",
            "stage-upgrade",
            "plan-major-upgrade",
            "establish-baseline",
            "investigate-metadata",
        ],
        default=None,
        help="Show only packages with the selected manifest action(s).",
    )
    parser.add_argument(
        "--outdated-only",
        action="store_true",
        help="Show only actionable upgrade candidates and baseline-establishment work.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=None,
        help="Limit output to the highest-risk N packages after filtering.",
    )
    return parser


def _resolve_requirement_paths(args: argparse.Namespace) -> list[Path] | None:
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
        return None
    return requirement_paths


def main(argv: list[str] | None = None) -> int:
    parser = build_parser(prog="upgrade-audit")
    args = parser.parse_args(argv)

    if not args.pyproject.exists():
        print(f"error: file not found: {args.pyproject}", file=sys.stderr)
        return 2

    requirement_paths = _resolve_requirement_paths(args)
    if requirement_paths is None:
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
        packages=args.package,
        groups=args.group,
        sources=args.source,
        metadata_sources=args.metadata_source,
        impact_areas=args.impact_area,
        outdated_only=bool(args.outdated_only),
        top=args.top,
        include_prereleases=bool(args.include_prereleases),
    )


if __name__ == "__main__":
    raise SystemExit(main())
