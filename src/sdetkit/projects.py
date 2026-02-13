from __future__ import annotations

import json
import os
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


_SCAN_SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".hypothesis",
        ".nox",
        ".tox",
        ".venv",
        "venv",
        "node_modules",
        "dist",
        "build",
    }
)


@dataclass(frozen=True)
class _DiscoveredProject:
    language: str
    root_rel: str
    manifests: tuple[str, ...]


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


def _root_rel(repo_root: Path, path: Path) -> str:
    rel = path.relative_to(repo_root).as_posix().strip("/")
    return rel or "."


def _iter_manifest_paths(repo_root: Path) -> list[Path]:
    manifests: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = sorted(
            d
            for d in dirnames
            if d not in _SCAN_SKIP_DIRS
            and not d.endswith(".egg-info")
            and not d.startswith(".venv")
        )
        for filename in sorted(filenames):
            if filename in {"pyproject.toml", "setup.cfg", "package.json", "go.mod", "Cargo.toml"}:
                manifests.append(Path(dirpath) / filename)
                continue
            if filename.startswith("requirements") and filename.endswith(".txt"):
                manifests.append(Path(dirpath) / filename)
    manifests.sort(key=lambda p: p.relative_to(repo_root).as_posix())
    return manifests


def _node_workspace_members(manifest_path: Path, repo_root: Path) -> tuple[str, ...]:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    if not isinstance(payload, dict):
        return ()
    workspaces = payload.get("workspaces")
    patterns: list[str] = []
    if isinstance(workspaces, list):
        patterns = [item for item in workspaces if isinstance(item, str)]
    elif isinstance(workspaces, dict):
        packages = workspaces.get("packages")
        if isinstance(packages, list):
            patterns = [item for item in packages if isinstance(item, str)]

    members: set[str] = set()
    for pattern in patterns:
        for path in sorted(manifest_path.parent.glob(pattern)):
            pkg = path / "package.json"
            if pkg.is_file() and repo_root in pkg.resolve(strict=False).parents:
                members.add(_root_rel(repo_root, pkg.parent))
    return tuple(sorted(members))


def _rust_workspace_members(manifest_path: Path, repo_root: Path) -> tuple[str, ...]:
    try:
        data = cast(Any, _tomllib).loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    if not isinstance(data, dict):
        return ()
    workspace = data.get("workspace")
    if not isinstance(workspace, dict):
        return ()
    members = workspace.get("members")
    if not isinstance(members, list):
        return ()
    out: set[str] = set()
    for item in members:
        if not isinstance(item, str):
            continue
        for path in sorted(manifest_path.parent.glob(item)):
            cargo = path / "Cargo.toml"
            if cargo.is_file() and repo_root in cargo.resolve(strict=False).parents:
                out.add(_root_rel(repo_root, cargo.parent))
    return tuple(sorted(out))


def _autodiscover_projects(repo_root: Path) -> list[RepoProject]:
    by_key: dict[tuple[str, str], set[str]] = {}

    for manifest in _iter_manifest_paths(repo_root):
        parent_rel = _root_rel(repo_root, manifest.parent)
        filename = manifest.name
        language: str | None = None
        workspace_members: tuple[str, ...] = ()
        if filename in {"pyproject.toml", "setup.cfg"} or (
            filename.startswith("requirements") and filename.endswith(".txt")
        ):
            language = "python"
        elif filename == "package.json":
            language = "node"
            workspace_members = _node_workspace_members(manifest, repo_root)
        elif filename == "go.mod":
            language = "go"
        elif filename == "Cargo.toml":
            language = "rust"
            workspace_members = _rust_workspace_members(manifest, repo_root)
        if language is None:
            continue

        rel_manifest = _root_rel(repo_root, manifest)
        by_key.setdefault((language, parent_rel), set()).add(rel_manifest)
        for member_root in workspace_members:
            member_manifest = (
                f"{member_root}/package.json" if language == "node" else f"{member_root}/Cargo.toml"
            )
            by_key.setdefault((language, member_root), set()).add(member_manifest)

    discovered: list[_DiscoveredProject] = []
    for (language, root_rel), manifests in by_key.items():
        discovered.append(
            _DiscoveredProject(
                language=language,
                root_rel=root_rel,
                manifests=tuple(sorted(manifests)),
            )
        )

    discovered.sort(key=lambda p: (p.root_rel, p.language, p.manifests))
    projects: list[RepoProject] = []
    for item in discovered:
        name = item.language if item.root_rel == "." else f"{item.language}:{item.root_rel}"
        projects.append(
            RepoProject(
                name=name,
                root=item.root_rel,
                config_path=item.manifests[0],
                profile=None,
                packs=(),
                baseline_path=None,
                exclude_paths=(),
            )
        )
    return projects


def discover_projects(
    repo_root: Path, *, sort: bool = False
) -> tuple[str | None, list[RepoProject]]:
    loaded = _load_manifest_doc(repo_root)
    if loaded is None:
        return "auto-discovered", _autodiscover_projects(repo_root)
    data, source = loaded

    raw_items = data.get("project")
    if raw_items is None:
        return source, []
    if not isinstance(raw_items, list) or any(not isinstance(item, dict) for item in raw_items):
        raise ProjectsConfigError("projects manifest must define [[project]] entries")

    projects: list[RepoProject] = []
    seen: set[str] = set()
    for item in raw_items:
        entry = cast(dict[str, Any], item)
        name = _as_str(entry.get("name"), field="name")
        root = _as_str(entry.get("root"), field="root")
        if not name or not root:
            raise ProjectsConfigError("project entries require 'name' and 'root'")
        if name in seen:
            raise ProjectsConfigError(f"duplicate project name: {name}")
        seen.add(name)
        projects.append(
            RepoProject(
                name=name,
                root=_normalize_rel(root, field="root"),
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
