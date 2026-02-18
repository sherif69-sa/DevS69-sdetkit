from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

try:
    import tomllib as _tomllib
except Exception:  # pragma: no cover
    import tomli as _tomllib  # type: ignore


class ProjectsConfigError(ValueError):
    pass


@dataclass(frozen=True)
class RepoProject:
    name: str
    root: str
    config_path: str | None
    profile: str | None
    packs: tuple[str, ...]
    baseline_path: str | None
    exclude_paths: tuple[str, ...]


@dataclass(frozen=True)
class ResolvedRepoProject:
    name: str
    root: Path
    root_rel: str
    config_path: Path | None
    config_rel: str | None
    profile: str | None
    packs: tuple[str, ...]
    baseline_path: str | None
    baseline_rel: str
    exclude_paths: tuple[str, ...]


def _as_str(value: Any, *, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ProjectsConfigError(f"projects field '{field}' must be a string")
    text = value.strip()
    return text or None


def _as_str_list_or_csv(value: Any, *, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(part.strip() for part in value.split(",") if part.strip())
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return tuple(item.strip() for item in value if item.strip())
    raise ProjectsConfigError(f"projects field '{field}' must be a list of strings or csv string")


def _normalize_rel(path_text: str, *, field: str) -> str:
    raw = path_text.replace("\\", "/").strip()
    while raw.startswith("./"):
        raw = raw[2:]
    if not raw:
        return "."
    if raw.startswith("/"):
        raise ProjectsConfigError(f"projects field '{field}' must be relative")
    parts = [part for part in raw.split("/") if part]
    if any(part == ".." for part in parts):
        raise ProjectsConfigError(f"projects field '{field}' cannot contain traversal")
    return "/".join(parts) or "."


def _load_manifest_doc(repo_root: Path) -> tuple[dict[str, Any], str] | None:
    preferred = repo_root / ".sdetkit" / "projects.toml"
    if preferred.exists():
        data = cast(Any, _tomllib).loads(preferred.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ProjectsConfigError("projects manifest must be a TOML table")
        return data, ".sdetkit/projects.toml"

    pyproject = repo_root / "pyproject.toml"
    if not pyproject.exists():
        return None
    data = cast(Any, _tomllib).loads(pyproject.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    tool = data.get("tool")
    if not isinstance(tool, dict):
        return None
    sdetkit = tool.get("sdetkit")
    if not isinstance(sdetkit, dict):
        return None
    projects = sdetkit.get("projects")
    if projects is None:
        return None
    if not isinstance(projects, dict):
        raise ProjectsConfigError("[tool.sdetkit.projects] must be a table")
    return projects, "pyproject.toml"


_SKIP_DIRS: set[str] = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".sdetkit",
    "dist",
    "build",
}

_AUTODISCOVER_BASES: tuple[str, ...] = ("packages", "apps", "services", "libs", "crates")


def _pyproject_project_name(pyproject: Path) -> str | None:
    try:
        data = cast(Any, _tomllib).loads(pyproject.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    proj = data.get("project")
    if isinstance(proj, dict):
        name = proj.get("name")
        if isinstance(name, str):
            stripped = name.strip()
            if stripped:
                return stripped

    tool = data.get("tool")
    if not isinstance(tool, dict):
        return None

    poetry = tool.get("poetry")
    if isinstance(poetry, dict):
        poetry_name = poetry.get("name")
        if isinstance(poetry_name, str):
            stripped = poetry_name.strip()
            if stripped:
                return stripped

    pdm = tool.get("pdm")
    if isinstance(pdm, dict):
        pdm_name = pdm.get("name")
        if isinstance(pdm_name, str):
            stripped = pdm_name.strip()
            if stripped:
                return stripped

    hatch = tool.get("hatch")
    if isinstance(hatch, dict):
        metadata = hatch.get("metadata")
        if isinstance(metadata, dict):
            hatch_name = metadata.get("name")
            if isinstance(hatch_name, str):
                stripped = hatch_name.strip()
                if stripped:
                    return stripped

    return None


def _package_json_project_name(package_json: Path) -> str | None:
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    name = data.get("name")
    if not isinstance(name, str):
        return None
    stripped = name.strip()
    return stripped or None


def _cargo_project_name(cargo_toml: Path) -> str | None:
    try:
        data = cast(Any, _tomllib).loads(cargo_toml.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    package = data.get("package")
    if not isinstance(package, dict):
        return None
    name = package.get("name")
    if not isinstance(name, str):
        return None
    stripped = name.strip()
    return stripped or None


def _go_module_name(go_mod: Path) -> str | None:
    try:
        content = go_mod.read_text(encoding="utf-8")
    except Exception:
        return None
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        if line.startswith("module "):
            module = line[7:].strip()
            return module or None
        break
    return None


def _maven_project_name(pom_xml: Path) -> str | None:
    try:
        root = ET.fromstring(pom_xml.read_text(encoding="utf-8"))
    except Exception:
        return None

    for child in root:
        tag = child.tag.rsplit("}", 1)[-1]
        if tag != "artifactId":
            continue
        if child.text is None:
            continue
        stripped = child.text.strip()
        if stripped:
            return stripped
    return None


def _gradle_project_name(settings_file: Path) -> str | None:
    try:
        content = settings_file.read_text(encoding="utf-8")
    except Exception:
        return None

    pattern = re.compile(r'rootProject\.name\s*=\s*[\'"]([^\'"]+)[\'"]')
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        match = pattern.search(line)
        if not match:
            continue
        stripped = match.group(1).strip()
        if stripped:
            return stripped
    return None


def _csproj_project_name(csproj: Path) -> str | None:
    try:
        root = ET.fromstring(csproj.read_text(encoding="utf-8"))
    except Exception:
        return csproj.stem or None

    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag != "AssemblyName" or element.text is None:
            continue
        stripped = element.text.strip()
        if stripped:
            return stripped

    return csproj.stem or None


def _autodiscover_roots(*, data: dict[str, Any] | None, field_prefix: str) -> tuple[str, ...]:
    if data is None:
        return _AUTODISCOVER_BASES
    roots = data.get("autodiscover_roots")
    if roots is None:
        return _AUTODISCOVER_BASES
    if isinstance(roots, str):
        values = tuple(part.strip() for part in roots.split(",") if part.strip())
    elif isinstance(roots, list) and all(isinstance(item, str) for item in roots):
        values = tuple(item.strip() for item in roots if item.strip())
    else:
        raise ProjectsConfigError(
            f"{field_prefix}.autodiscover_roots must be a list of strings or csv string"
        )
    if not values:
        return _AUTODISCOVER_BASES
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in values:
        rel = _normalize_rel(raw, field="autodiscover_roots")
        if rel in seen:
            continue
        seen.add(rel)
        normalized.append(rel)
    return tuple(normalized)


def _autodiscover_projects(
    repo_root: Path,
    *,
    base_roots: tuple[str, ...] = _AUTODISCOVER_BASES,
) -> list[RepoProject]:
    bases: list[Path] = []
    for base_name in base_roots:
        d = repo_root / base_name
        if d.is_dir():
            bases.append(d)
    if not bases:
        return []

    found: list[RepoProject] = []
    seen: dict[str, str] = {}

    for base in bases:
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(
                d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")
            )
            has_pyproject = "pyproject.toml" in filenames
            has_cargo_toml = "Cargo.toml" in filenames
            has_go_mod = "go.mod" in filenames
            has_package_json = "package.json" in filenames
            has_pom_xml = "pom.xml" in filenames
            has_gradle_settings = (
                "settings.gradle" in filenames or "settings.gradle.kts" in filenames
            )
            csproj_files = sorted(name for name in filenames if name.endswith(".csproj"))
            if not any(
                (
                    has_pyproject,
                    has_cargo_toml,
                    has_go_mod,
                    has_package_json,
                    has_pom_xml,
                    has_gradle_settings,
                    csproj_files,
                )
            ):
                continue
            project_dir = Path(dirpath)
            name: str | None = None
            if has_pyproject:
                name = _pyproject_project_name(project_dir / "pyproject.toml")
            if not name and has_cargo_toml:
                name = _cargo_project_name(project_dir / "Cargo.toml")
            if not name and has_go_mod:
                name = _go_module_name(project_dir / "go.mod")
            if not name and has_package_json:
                name = _package_json_project_name(project_dir / "package.json")
            if not name and has_pom_xml:
                name = _maven_project_name(project_dir / "pom.xml")
            if not name and has_gradle_settings:
                settings_name = (
                    "settings.gradle" if "settings.gradle" in filenames else "settings.gradle.kts"
                )
                name = _gradle_project_name(project_dir / settings_name)
            if not name and csproj_files:
                name = _csproj_project_name(project_dir / csproj_files[0])
            if not name:
                continue
            root_rel = project_dir.relative_to(repo_root).as_posix()
            if name in seen:
                first_root = seen[name]
                raise ProjectsConfigError(
                    f"duplicate project name: {name} (roots: {first_root} and {root_rel})"
                )
            seen[name] = root_rel
            found.append(
                RepoProject(
                    name=name,
                    root=_normalize_rel(root_rel, field="root"),
                    config_path=None,
                    profile=None,
                    packs=(),
                    baseline_path=None,
                    exclude_paths=(),
                )
            )

    found.sort(key=lambda pr: pr.root)
    return found


def discover_projects(
    repo_root: Path,
    *,
    sort: bool = False,
) -> tuple[str | None, list[RepoProject]]:
    loaded = _load_manifest_doc(repo_root)
    if loaded is None:
        auto_projects = _autodiscover_projects(repo_root)
        if not auto_projects:
            return None, []
        if sort:
            auto_projects.sort(key=lambda p: p.name)
        return "autodiscover", auto_projects

    data, source = loaded
    raw_items = data.get("project")
    autodiscover = data.get("autodiscover")
    if autodiscover is None:
        autodiscover_enabled = False
    elif isinstance(autodiscover, bool):
        autodiscover_enabled = autodiscover
    else:
        raise ProjectsConfigError("[tool.sdetkit.projects].autodiscover must be a boolean")

    autodiscover_roots = _autodiscover_roots(data=data, field_prefix="[tool.sdetkit.projects]")

    if raw_items is None:
        if autodiscover_enabled:
            auto_projects = _autodiscover_projects(repo_root, base_roots=autodiscover_roots)
            if sort:
                auto_projects.sort(key=lambda p: p.name)
            return f"{source} (autodiscover)", auto_projects
        return source, []
    if not isinstance(raw_items, list) or any(not isinstance(item, dict) for item in raw_items):
        raise ProjectsConfigError("projects manifest must define [[project]] entries")

    projects: list[RepoProject] = []
    seen_names: set[str] = set()
    seen_roots: set[str] = set()
    for item in raw_items:
        entry = cast(dict[str, Any], item)
        name = _as_str(entry.get("name"), field="name")
        root = _as_str(entry.get("root"), field="root")
        if not name or not root:
            raise ProjectsConfigError("project entries require 'name' and 'root'")
        if name in seen_names:
            raise ProjectsConfigError(f"duplicate project name: {name}")
        normalized_root = _normalize_rel(root, field="root")
        if normalized_root in seen_roots:
            raise ProjectsConfigError(f"duplicate project root: {normalized_root}")
        seen_names.add(name)
        seen_roots.add(normalized_root)
        projects.append(
            RepoProject(
                name=name,
                root=normalized_root,
                config_path=(
                    _normalize_rel(cfg, field="config")
                    if (cfg := _as_str(entry.get("config"), field="config"))
                    else None
                ),
                profile=_as_str(entry.get("profile"), field="profile"),
                packs=_as_str_list_or_csv(entry.get("packs"), field="packs"),
                baseline_path=(
                    _normalize_rel(base, field="baseline")
                    if (base := _as_str(entry.get("baseline"), field="baseline"))
                    else None
                ),
                exclude_paths=_as_str_list_or_csv(entry.get("exclude"), field="exclude"),
            )
        )

    if autodiscover_enabled:
        for detected in _autodiscover_projects(repo_root, base_roots=autodiscover_roots):
            if detected.name in seen_names or detected.root in seen_roots:
                continue
            seen_names.add(detected.name)
            seen_roots.add(detected.root)
            projects.append(detected)

    if sort:
        projects.sort(key=lambda p: p.name)
    return source, projects


def resolve_project(repo_root: Path, project: RepoProject) -> ResolvedRepoProject:
    root_rel = _normalize_rel(project.root, field="root")
    root = (repo_root / root_rel).resolve(strict=False)
    baseline_rel = project.baseline_path or f"{root_rel}/.sdetkit/audit-baseline.json"
    return ResolvedRepoProject(
        name=project.name,
        root=root,
        root_rel=root_rel,
        config_path=(repo_root / project.config_path).resolve(strict=False)
        if project.config_path
        else None,
        config_rel=project.config_path,
        profile=project.profile,
        packs=project.packs,
        baseline_path=project.baseline_path,
        baseline_rel=_normalize_rel(baseline_rel, field="baseline"),
        exclude_paths=project.exclude_paths,
    )
