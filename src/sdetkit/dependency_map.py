"""Which declared dependencies a repository uses, where, and what proves a change to them.

`sdetkit kits radar` and `sdetkit kits route-map` used to return fixed values: one
"Dependency risk" card, `runtime_core_packages: 1`, the query echoed back as the hotspot,
and `pytest -q` as the validation for every package. This module answers from the
repository instead: the dependencies pyproject.toml declares (runtime, extras and PEP 735
groups), the versions its lockfiles pin, the Python files that import each one (read with
`ast`, not by substring), and the narrowest pytest command that exercises it.
"""

from __future__ import annotations

import ast
import re
import warnings
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import metadata
from pathlib import Path
from typing import Any

from ._toml import loads as toml_loads
from .lockfiles import normalize_name, pinned_python_packages, python_lockfiles

RUNTIME_GROUP = "runtime"
# Directories that hold someone else's code or generated files, not the repository's.
_SKIPPED_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".venv",
        "venv",
        ".tox",
        ".nox",
        "build",
        "dist",
        "node_modules",
        "site-packages",
        "__pycache__",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
    }
)
_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
# Usage tiers by how many of the repository's files import a package.
HOT_PATH_MIN_FILES = 3
# A package exercised by more test files than this is validated by the whole suite.
NARROW_TEST_LIMIT = 10
TIERS = ("hot-path", "balanced", "edge")


@dataclass(frozen=True)
class Dependency:
    name: str
    spec: str
    groups: tuple[str, ...]
    locked: str | None
    files: tuple[str, ...]
    test_files: tuple[str, ...]

    @property
    def tier(self) -> str:
        if len(self.files) >= HOT_PATH_MIN_FILES:
            return "hot-path"
        return "edge" if len(self.files) <= 1 else "balanced"

    @property
    def pinned(self) -> bool:
        return "==" in self.spec

    def primary_validation(self) -> str:
        """The narrowest command that runs the tests importing this package."""

        if not self.test_files:
            return "python -m sdetkit gate fast"
        if len(self.test_files) > NARROW_TEST_LIMIT:
            return "python -m sdetkit gate fast --only pytest"
        return "python -m pytest -q " + " ".join(self.test_files)


@dataclass
class DependencyMap:
    dependencies: list[Dependency]
    lockfiles: list[str]
    scanned_files: int
    errors: list[str] = field(default_factory=list)

    def select(self, query: str = "", *, tier: str = "", impact_area: str = "") -> list[Dependency]:
        """Dependencies matching every filter given; an empty filter matches all."""

        tokens = [token.lower() for token in query.split() if token]
        group = _impact_group(impact_area)
        chosen = []
        for dep in self.dependencies:
            if group and group not in dep.groups:
                continue
            if tier and tier != "balanced" and dep.tier != tier:
                continue
            if tokens and not any(
                token in dep.name or token in dep.groups or any(token in f for f in dep.files)
                for token in tokens
            ):
                continue
            chosen.append(dep)
        return chosen


def _impact_group(impact_area: str) -> str:
    area = impact_area.strip().lower()
    if area in {"", "all", "any"}:
        return ""
    return RUNTIME_GROUP if area in {"runtime", "runtime-core"} else area


def _requirement_name(spec: str) -> str | None:
    match = _NAME.match(spec)
    return normalize_name(match[1]) if match else None


def declared_dependencies(root: Path) -> dict[str, tuple[str, list[str]]]:
    """name -> (first spec seen, groups) from pyproject.toml."""

    path = root / "pyproject.toml"
    try:
        data = toml_loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, ValueError):
        data = {}
    raw_project = data.get("project")
    project: dict[str, Any] = raw_project if isinstance(raw_project, dict) else {}
    sections: list[tuple[str, object]] = [(RUNTIME_GROUP, project.get("dependencies"))]
    extras = project.get("optional-dependencies")
    if isinstance(extras, dict):
        sections += [(str(name), specs) for name, specs in extras.items()]
    groups = data.get("dependency-groups")
    if isinstance(groups, dict):
        sections += [(str(name), specs) for name, specs in groups.items()]
    found: dict[str, tuple[str, list[str]]] = {}
    own = _requirement_name(str(project.get("name", ""))) if project.get("name") else None
    for group, specs in sections:
        for spec in specs if isinstance(specs, list) else []:
            if not isinstance(spec, str):  # a PEP 735 {include-group = ...} table
                continue
            name = _requirement_name(spec)
            if name is None or name == own:  # `project[extra]` self-references
                continue
            entry = found.setdefault(name, (spec.strip(), []))
            if group not in entry[1]:
                entry[1].append(group)
    return found


def _python_files(root: Path) -> Iterable[Path]:
    """The repository's own Python files: not vendored, generated, fixture or nested projects."""

    nested = {
        marker.parent
        for name in ("pyproject.toml", "setup.py")
        for marker in root.rglob(name)
        if marker.parent != root
    }
    for path in sorted(root.rglob("*.py")):
        parts = path.relative_to(root).parts
        if any(part in _SKIPPED_DIRS or part == "fixtures" for part in parts[:-1]):
            continue
        if any(parent in nested for parent in path.parents):
            continue
        yield path


def _imports(path: Path) -> set[str]:
    with warnings.catch_warnings():  # invalid escapes in the scanned code are not ours
        warnings.simplefilter("ignore")
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            found.add(node.module.split(".", 1)[0])
    return found


def _is_test_file(rel: str) -> bool:
    """A file pytest collects by default (helpers and conftest.py are not run on their own)."""

    name = rel.rsplit("/", 1)[-1]
    return name.startswith("test_") or name.endswith("_test.py")


def _module_names(dist: str, installed: dict[str, tuple[str, ...]]) -> set[str]:
    """Import names for a distribution: what the environment says, else the usual guess."""

    names = {module for module, dists in installed.items() if dist in dists}
    return names or {dist.replace("-", "_")}


@lru_cache(maxsize=1)
def _installed_modules() -> dict[str, tuple[str, ...]]:
    """Import name -> distributions installed in this environment (read once)."""

    return {
        module: tuple(normalize_name(dist) for dist in dists)
        for module, dists in metadata.packages_distributions().items()
    }


def build_map(root: Path) -> DependencyMap:
    declared = declared_dependencies(root)
    locked: dict[str, str] = {}
    for pin in pinned_python_packages(root):
        locked.setdefault(pin.name, pin.version)
    installed = _installed_modules()
    users: dict[str, set[str]] = {}
    errors: list[str] = []
    scanned = 0
    for path in _python_files(root):
        rel = path.relative_to(root).as_posix()
        try:
            modules = _imports(path)
        except (SyntaxError, ValueError, OSError) as exc:
            errors.append(f"{rel}: {type(exc).__name__}")
            continue
        scanned += 1
        for module in modules:
            users.setdefault(module, set()).add(rel)
    dependencies = []
    for name, (spec, groups) in sorted(declared.items()):
        files = sorted(
            {f for module in _module_names(name, installed) for f in users.get(module, ())}
        )
        dependencies.append(
            Dependency(
                name=name,
                spec=spec,
                groups=tuple(groups),
                locked=locked.get(name),
                files=tuple(files),
                test_files=tuple(f for f in files if _is_test_file(f)),
            )
        )
    return DependencyMap(dependencies, python_lockfiles(root), scanned, errors)
