from __future__ import annotations

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


def discover_projects(
    repo_root: Path, *, sort: bool = False
) -> tuple[str | None, list[RepoProject]]:
    loaded = _load_manifest_doc(repo_root)
    if loaded is None:
        return None, []
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
