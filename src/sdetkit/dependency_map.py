"""Which declared dependencies a repository uses, where, and what proves a change to them.

Also provides predictive test selection (PTS) and AST dependency impact analysis
(`sdetkit verify impact` and `sdetkit test-impact`).

`sdetkit kits radar` and `sdetkit kits route-map` used to return fixed values: one
"Dependency risk" card, `runtime_core_packages: 1`, the query echoed back as the hotspot,
and `pytest -q` as the validation for every package. This module answers from the
repository instead: the dependencies pyproject.toml declares (runtime, extras and PEP 735
groups), the versions its lockfiles pin, the Python files that import each one (read with
`ast`, not by substring), and the narrowest pytest command that exercises it.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import warnings
from collections import defaultdict, deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import metadata
from pathlib import Path
from typing import Any

from ._toml import loads as toml_loads
from .gates.project_env import resolve_project_python
from .lockfiles import normalize_name, pinned_python_packages, python_lockfiles

RUNTIME_GROUP = "runtime"
# Directories that hold someone else's code or generated files, not the repository's.
_SKIPPED_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
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

SCHEMA_VERSION = "sdetkit.test_impact.v1"
JsonObject = dict[str, Any]

# Files whose changes invalidate the entire test suite
GLOBAL_CONFIG_FILES = frozenset(
    {
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "pytest.ini",
        "conftest.py",
        "tox.ini",
    }
)


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


# =============================================================================
# Predictive Test Selection (PTS) & AST Dependency Impact Engine
# =============================================================================


@dataclass(slots=True)
class ImportGraph:
    root: Path
    module_to_file: dict[str, str] = field(default_factory=dict)
    file_to_module: dict[str, str] = field(default_factory=dict)
    forward_graph: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    reverse_graph: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    test_files: set[str] = field(default_factory=set)
    source_files: set[str] = field(default_factory=set)


def _normalize_rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _is_test_path(rel_posix: str) -> bool:
    name = Path(rel_posix).name
    return (
        rel_posix.startswith("tests/")
        or "/tests/" in rel_posix
        or name.startswith("test_")
        or name.endswith("_test.py")
    )


def _resolve_relative_import(rel_path: str, module: str | None, level: int) -> str:
    parts = Path(rel_path).parent.parts
    if parts and parts[0] in ("src", "lib"):
        pkg_parts = list(parts[1:])
    else:
        pkg_parts = list(parts)

    if level > 0:
        if level <= len(pkg_parts):
            base_pkg = pkg_parts[: len(pkg_parts) - level + 1]
        else:
            base_pkg = []
        if base_pkg and module:
            return ".".join(base_pkg + [module])
        if base_pkg:
            return ".".join(base_pkg)
        return module or ""
    return module or ""


def build_import_graph(root: Path) -> ImportGraph:
    resolved_root = root.resolve()
    graph = ImportGraph(root=resolved_root)

    candidates: list[tuple[str, Path]] = []
    for path in resolved_root.rglob("*.py"):
        if any(skip in path.parts for skip in _SKIPPED_DIRS):
            continue
        rel = _normalize_rel(path, resolved_root)
        candidates.append((rel, path))

        parts = Path(rel).parts
        if parts and parts[0] in ("src", "lib"):
            parts = parts[1:]
        mod_parts = list(parts)
        if mod_parts and mod_parts[-1].endswith(".py"):
            mod_parts[-1] = mod_parts[-1][:-3]
        if mod_parts and mod_parts[-1] == "__init__":
            mod_parts.pop()
        mod_name = ".".join(mod_parts)
        if mod_name:
            graph.module_to_file[mod_name] = rel
            graph.file_to_module[rel] = mod_name

        if _is_test_path(rel):
            graph.test_files.add(rel)
        else:
            graph.source_files.add(rel)

    for rel, path in candidates:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (SyntaxError, OSError):
            # Skip unparseable or unreadable files during dependency graph construction.
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target_file = graph.module_to_file.get(alias.name)
                    if target_file and target_file != rel:
                        graph.forward_graph[rel].add(target_file)
                        graph.reverse_graph[target_file].add(rel)
            elif isinstance(node, ast.ImportFrom):
                resolved = _resolve_relative_import(rel, node.module, node.level)
                if resolved in graph.module_to_file and graph.module_to_file[resolved] != rel:
                    target_file = graph.module_to_file[resolved]
                    graph.forward_graph[rel].add(target_file)
                    graph.reverse_graph[target_file].add(rel)
                for alias in node.names:
                    sub_mod = f"{resolved}.{alias.name}" if resolved else alias.name
                    if sub_mod in graph.module_to_file and graph.module_to_file[sub_mod] != rel:
                        target_file = graph.module_to_file[sub_mod]
                        graph.forward_graph[rel].add(target_file)
                        graph.reverse_graph[target_file].add(rel)

    return graph


def detect_changed_files(root: Path, base: str | None = None) -> list[str]:
    changed: set[str] = set()

    # Query uncommitted working tree changes
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                if len(line) >= 4:
                    raw_path = line[3:].strip()
                    if " -> " in raw_path:
                        raw_path = raw_path.split(" -> ")[1].strip()
                    changed.add(raw_path.replace("\\", "/"))
    except (OSError, subprocess.TimeoutExpired):
        # Best-effort git check; proceed to base diff if available.
        pass

    # Query git diff against base ref if specified
    if base:
        try:
            diff_proc = subprocess.run(
                ["git", "diff", "--name-only", base],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            if diff_proc.returncode == 0:
                for line in diff_proc.stdout.splitlines():
                    clean_line = line.strip().replace("\\", "/")
                    if clean_line:
                        changed.add(clean_line)
        except (OSError, subprocess.TimeoutExpired):
            # Best-effort git diff.
            pass

    return sorted(changed)


def analyze_impact(
    root: Path,
    *,
    files: Sequence[str | Path] | None = None,
    base: str | None = None,
    graph: ImportGraph | None = None,
) -> JsonObject:
    resolved_root = root.resolve()
    active_graph = graph or build_import_graph(resolved_root)

    if files is not None:
        target_files = [
            (
                _normalize_rel(Path(f), resolved_root)
                if Path(f).is_absolute()
                else str(f).replace("\\", "/")
            )
            for f in files
        ]
    else:
        target_files = detect_changed_files(resolved_root, base=base)

    total_tests = len(active_graph.test_files)

    if not target_files:
        return {
            "schema_version": SCHEMA_VERSION,
            "clean": True,
            "changed_files": [],
            "directly_impacted_tests": [],
            "transitively_impacted_tests": [],
            "all_impacted_tests": [],
            "total_tests_count": total_tests,
            "selected_tests_count": 0,
            "reduction_pct": 100.0,
            "recommended_pytest_command": "",
            "confidence": "high",
            "reason": "Working tree is clean; no changed files detected.",
            "global_config_changed": False,
        }

    # Check for global configuration files
    has_global_change = any(Path(f).name in GLOBAL_CONFIG_FILES for f in target_files)
    if has_global_change:
        all_tests = sorted(active_graph.test_files)
        return {
            "schema_version": SCHEMA_VERSION,
            "clean": False,
            "changed_files": target_files,
            "directly_impacted_tests": all_tests,
            "transitively_impacted_tests": [],
            "all_impacted_tests": all_tests,
            "total_tests_count": total_tests,
            "selected_tests_count": len(all_tests),
            "reduction_pct": 0.0,
            "recommended_pytest_command": "python -m pytest",
            "confidence": "high",
            "reason": "Global build/test configuration modified; all tests must run.",
            "global_config_changed": True,
        }

    direct_tests: set[str] = set()
    transitive_tests: set[str] = set()
    impacted_sources: set[str] = set()

    for changed in target_files:
        # If the changed file is itself a test, it is directly impacted
        if changed in active_graph.test_files:
            direct_tests.add(changed)

        # Direct dependents
        direct_deps = active_graph.reverse_graph.get(changed, set())
        for dep in direct_deps:
            if dep in active_graph.test_files:
                direct_tests.add(dep)
            else:
                impacted_sources.add(dep)

        # Transitive dependents via BFS traversal
        queue: deque[str] = deque(direct_deps)
        visited: set[str] = set(direct_deps)
        visited.add(changed)

        while queue:
            curr = queue.popleft()
            for parent in active_graph.reverse_graph.get(curr, set()):
                if parent not in visited:
                    visited.add(parent)
                    queue.append(parent)
                    if parent in active_graph.test_files:
                        if parent not in direct_tests:
                            transitive_tests.add(parent)
                    else:
                        impacted_sources.add(parent)

    all_impacted = sorted(direct_tests | transitive_tests)
    selected_count = len(all_impacted)
    reduction = round((1.0 - (selected_count / total_tests)) * 100.0, 2) if total_tests > 0 else 0.0

    recommended_cmd = f"python -m pytest {' '.join(all_impacted)}" if all_impacted else ""

    return {
        "schema_version": SCHEMA_VERSION,
        "clean": False,
        "changed_files": target_files,
        "directly_impacted_tests": sorted(direct_tests),
        "transitively_impacted_tests": sorted(transitive_tests),
        "all_impacted_tests": all_impacted,
        "impacted_source_files": sorted(impacted_sources),
        "total_tests_count": total_tests,
        "selected_tests_count": selected_count,
        "reduction_pct": reduction,
        "recommended_pytest_command": recommended_cmd,
        "confidence": "high",
        "reason": f"Selected {selected_count} impacted tests from {len(target_files)} changed files.",
        "global_config_changed": False,
    }


def run_impacted_tests(
    impact_report: JsonObject,
    *,
    root: Path,
    timeout: int = 180,
    fail_fast: bool = False,
    extra_args: Sequence[str] | None = None,
) -> JsonObject:
    selected = impact_report.get("all_impacted_tests") or []
    if not selected:
        return {
            "ok": True,
            "executed": False,
            "returncode": 0,
            "duration_seconds": 0.0,
            "selected_tests_count": 0,
            "message": "No impacted tests to run.",
            "stdout": "",
            "stderr": "",
        }

    env = resolve_project_python(root)
    cmd = [
        env.executable,
        "-m",
        "pytest",
        "-q",
        *(["-x"] if fail_fast else []),
        *(list(extra_args) if extra_args else []),
        *selected,
    ]

    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        duration = round(time.monotonic() - t0, 3)
        return {
            "ok": proc.returncode == 0,
            "executed": True,
            "returncode": proc.returncode,
            "duration_seconds": duration,
            "selected_tests_count": len(selected),
            "command": " ".join(cmd),
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except subprocess.TimeoutExpired as exc:
        duration = round(time.monotonic() - t0, 3)
        return {
            "ok": False,
            "executed": True,
            "returncode": 124,
            "duration_seconds": duration,
            "selected_tests_count": len(selected),
            "command": " ".join(cmd),
            "error": f"Test run timed out after {timeout} seconds",
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
        }
    except OSError as err:
        return {
            "ok": False,
            "executed": False,
            "returncode": 1,
            "duration_seconds": 0.0,
            "selected_tests_count": len(selected),
            "error": f"Failed executing test command: {err}",
            "stdout": "",
            "stderr": "",
        }


def render_markdown(report: JsonObject, execution: JsonObject | None = None) -> str:
    clean = report.get("clean", False)
    if clean:
        return (
            "### SDETKit Predictive Test Selection: CLEAN\n\n"
            "Working tree is clean; no changes detected and no tests required."
        )

    changed = report.get("changed_files") or []
    direct = report.get("directly_impacted_tests") or []
    transitive = report.get("transitively_impacted_tests") or []
    total = report.get("total_tests_count", 0)
    selected = report.get("selected_tests_count", 0)
    reduction = report.get("reduction_pct", 0.0)
    cmd = report.get("recommended_pytest_command", "")

    lines: list[str] = [
        "### SDETKit Predictive Test Selection Report",
        "",
        f"- **Changed files**: `{len(changed)}`",
        f"- **Selected tests**: `{selected}` of `{total}` total (`{reduction}%` skipped)",
        f"- **Confidence**: `{report.get('confidence', 'high')}`",
        "",
    ]

    if changed:
        lines.append("<details><summary><b>Changed Files</b></summary>\n")
        for f in changed[:20]:
            lines.append(f"- `{f}`")
        if len(changed) > 20:
            lines.append(f"- ... and {len(changed) - 20} more")
        lines.append("\n</details>\n")

    if direct:
        lines.append(f"**Directly Impacted Tests ({len(direct)})**:")
        for t in direct:
            lines.append(f"- `{t}`")
        lines.append("")

    if transitive:
        lines.append(f"**Transitively Impacted Tests ({len(transitive)})**:")
        for t in transitive:
            lines.append(f"- `{t}`")
        lines.append("")

    if cmd:
        lines.append(f"**Recommended Command**:\n```bash\n{cmd}\n```\n")

    if execution and execution.get("executed"):
        ok = execution.get("ok", False)
        verdict = "PASSED" if ok else "FAILED"
        dur = execution.get("duration_seconds", 0.0)
        lines.append(
            f"**Execution Verdict**: `{verdict}` in `{dur}s` (rc={execution.get('returncode')})\n"
        )

    return "\n".join(lines).strip()


# =============================================================================
# Release Blast Radius & Semantic Risk Radar Engine
# =============================================================================

BLAST_RADIUS_SCHEMA_VERSION = "sdetkit.blast_radius.v1"

CRITICAL_INFRASTRUCTURE_PATTERNS = frozenset(
    {
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "conftest.py",
        "tox.ini",
        "quality.sh",
        "uv.lock",
    }
)

PUBLIC_SURFACE_PREFIXES = (
    "src/sdetkit/__init__.py",
    "src/sdetkit/cli/",
    "src/sdetkit/mcp_server.py",
)


def evaluate_blast_radius(
    root: Path,
    *,
    files: Sequence[str | Path] | None = None,
    base: str | None = None,
    graph: ImportGraph | None = None,
) -> JsonObject:
    resolved_root = root.resolve()
    active_graph = graph or build_import_graph(resolved_root)

    if files is not None:
        target_files = [
            (
                _normalize_rel(Path(f), resolved_root)
                if Path(f).is_absolute()
                else str(f).replace("\\", "/")
            )
            for f in files
        ]
    else:
        target_files = detect_changed_files(resolved_root, base=base)

    total_repo_files = len(active_graph.source_files) + len(active_graph.test_files)

    if not target_files:
        return {
            "schema_version": BLAST_RADIUS_SCHEMA_VERSION,
            "clean": True,
            "changed_files": [],
            "blast_radius_index": 0.0,
            "risk_tier": "LOW",
            "fanout_pct": 0.0,
            "transitive_files_count": 0,
            "total_repo_files": total_repo_files,
            "impacted_sources_count": 0,
            "impacted_tests_count": 0,
            "test_defense_health": "STRONG",
            "test_to_source_ratio": 10.0,
            "public_surface_exposed": False,
            "critical_infra_modified": False,
            "recommended_strategy": "FAST_TRACK",
            "recommended_command": "python -m sdetkit gate fast",
            "recommendation": "Working tree is clean; zero architectural blast radius.",
            "directly_impacted_files": [],
            "transitively_impacted_files": [],
            "all_impacted_tests": [],
            "summary": "Working tree is clean; zero architectural blast radius.",
        }

    sources_changed: list[str] = []
    tests_changed: list[str] = []
    configs_changed: list[str] = []
    docs_changed: list[str] = []

    for f in target_files:
        fname = Path(f).name
        if fname in CRITICAL_INFRASTRUCTURE_PATTERNS or ".github/" in f:
            configs_changed.append(f)
        elif _is_test_path(f):
            tests_changed.append(f)
        elif f.endswith((".md", ".rst", ".txt")):
            docs_changed.append(f)
        elif f.endswith((".py", ".c", ".cpp", ".h", ".hpp", ".js", ".ts", ".go", ".rs")):
            sources_changed.append(f)
        else:
            configs_changed.append(f)

    direct_dependents: set[str] = set()
    transitive_dependents: set[str] = set()
    impacted_tests: set[str] = set()
    impacted_sources: set[str] = set()

    for changed in target_files:
        if changed in active_graph.test_files:
            impacted_tests.add(changed)

        direct = active_graph.reverse_graph.get(changed, set())
        for dep in direct:
            direct_dependents.add(dep)
            if dep in active_graph.test_files:
                impacted_tests.add(dep)
            else:
                impacted_sources.add(dep)

        queue: deque[str] = deque(direct)
        visited: set[str] = set(direct)
        visited.add(changed)

        while queue:
            curr = queue.popleft()
            for parent in active_graph.reverse_graph.get(curr, set()):
                if parent not in visited:
                    visited.add(parent)
                    queue.append(parent)
                    transitive_dependents.add(parent)
                    if parent in active_graph.test_files:
                        impacted_tests.add(parent)
                    else:
                        impacted_sources.add(parent)

    critical_infra_modified = len(configs_changed) > 0

    if critical_infra_modified:
        all_impacted_files = sorted(
            set(target_files) | set(active_graph.source_files) | set(active_graph.test_files)
        )
        impacted_tests = set(active_graph.test_files)
        impacted_sources = set(active_graph.source_files)
    else:
        all_impacted_files = sorted(set(target_files) | direct_dependents | transitive_dependents)

    transitive_count = len(all_impacted_files)
    fanout_pct = (
        round((transitive_count / total_repo_files) * 100.0, 2) if total_repo_files > 0 else 0.0
    )

    public_surface_exposed = any(
        any(f.startswith(prefix) for prefix in PUBLIC_SURFACE_PREFIXES) for f in target_files
    )

    changed_src_count = len(sources_changed)
    impacted_tests_count = len(impacted_tests)
    if changed_src_count == 0:
        test_defense_health = "STRONG"
        test_ratio = 10.0
    else:
        test_ratio = round(impacted_tests_count / changed_src_count, 2)
        if test_ratio >= 3.0:
            test_defense_health = "STRONG"
        elif test_ratio >= 1.0:
            test_defense_health = "MODERATE"
        else:
            test_defense_health = "WEAK"

    fanout_score = min(35.0, fanout_pct * 0.7)
    critical_score = 45.0 if critical_infra_modified else 0.0
    public_score = 20.0 if public_surface_exposed else 0.0

    if changed_src_count > 0:
        if impacted_tests_count == 0:
            test_gap_score = 15.0
        elif test_defense_health == "WEAK":
            test_gap_score = 10.0
        elif test_defense_health == "MODERATE":
            test_gap_score = 5.0
        else:
            test_gap_score = 0.0
    else:
        test_gap_score = 0.0

    raw_score = fanout_score + critical_score + public_score + test_gap_score

    if docs_changed and not sources_changed and not configs_changed and not tests_changed:
        raw_score = min(5.0, raw_score)

    blast_radius_index = round(max(0.0, min(100.0, raw_score)), 1)

    if critical_infra_modified:
        risk_tier = "CRITICAL" if blast_radius_index >= 80.0 else "HIGH"
        strategy = "FULL_RELEASE_GATE"
        recommended_cmd = "python -m sdetkit gate release && python -m sdetkit verify mutation"
        recommendation = "Critical build/CI infrastructure modified. Full release gate and deep verification required."
    elif docs_changed and not sources_changed and not configs_changed and not tests_changed:
        risk_tier = "LOW"
        strategy = "DOCS_FAST_LANE"
        recommended_cmd = "python -m sdetkit gate fast"
        recommendation = "Documentation changes only. Zero architectural or test execution risk."
    elif blast_radius_index <= 25.0:
        risk_tier = "LOW"
        strategy = "FAST_TRACK"
        recommended_cmd = (
            f"python -m sdetkit test-impact {' '.join(sorted(impacted_tests))} --run"
            if impacted_tests
            else "python -m sdetkit gate fast"
        )
        recommendation = (
            "Low architectural fan-out. Safe to fast-track merge with predictive test selection."
        )
    elif blast_radius_index <= 60.0:
        risk_tier = "MEDIUM"
        strategy = "STANDARD_GATE"
        recommended_cmd = "python -m sdetkit gate fast"
        recommendation = "Moderate fan-out across dependencies. Require standard fast quality gate."
    elif blast_radius_index <= 85.0:
        risk_tier = "HIGH"
        strategy = "RELEASE_GATE"
        recommended_cmd = (
            "python -m sdetkit gate release && python -m sdetkit verify quarantine audit"
        )
        recommendation = (
            "High architectural reach. Require release gate and quarantine audit before merge."
        )
    else:
        risk_tier = "CRITICAL"
        strategy = "FULL_RELEASE_GATE"
        recommended_cmd = "python -m sdetkit gate release && python -m sdetkit verify mutation"
        recommendation = "Critical infrastructure or massive fan-out (>60% reach). Require full release gate and mutation audit."

    return {
        "schema_version": BLAST_RADIUS_SCHEMA_VERSION,
        "clean": False,
        "changed_files": target_files,
        "blast_radius_index": blast_radius_index,
        "risk_tier": risk_tier,
        "fanout_pct": fanout_pct,
        "transitive_files_count": transitive_count,
        "total_repo_files": total_repo_files,
        "impacted_sources_count": len(impacted_sources),
        "impacted_tests_count": impacted_tests_count,
        "test_defense_health": test_defense_health,
        "test_to_source_ratio": test_ratio,
        "public_surface_exposed": public_surface_exposed,
        "critical_infra_modified": critical_infra_modified,
        "recommended_strategy": strategy,
        "recommended_command": recommended_cmd,
        "recommendation": recommendation,
        "directly_impacted_files": sorted(direct_dependents),
        "transitively_impacted_files": sorted(transitive_dependents),
        "all_impacted_tests": sorted(impacted_tests),
        "summary": f"Blast radius {blast_radius_index}% [{risk_tier}] touching {len(target_files)} file(s) with {fanout_pct}% repository reach.",
    }


def render_blast_radius_markdown(report: JsonObject) -> str:
    clean = report.get("clean", False)
    if clean:
        return (
            "### [RISK: CLEAN (0.0%)] SDETKit Release Blast Radius\n\n"
            "Working tree is clean; zero architectural blast radius."
        )

    score = report.get("blast_radius_index", 0.0)
    tier = report.get("risk_tier", "LOW")
    changed = report.get("changed_files") or []
    fanout = report.get("fanout_pct", 0.0)
    transitive = report.get("transitive_files_count", 0)
    total_repo = report.get("total_repo_files", 0)
    tests_count = report.get("impacted_tests_count", 0)
    defense = report.get("test_defense_health", "UNKNOWN")
    public = "YES" if report.get("public_surface_exposed") else "NO"
    critical = "YES" if report.get("critical_infra_modified") else "NO"
    cmd = report.get("recommended_command", "")
    rec = report.get("recommendation", "")
    strategy = report.get("recommended_strategy", "STANDARD_GATE")

    lines = [
        f"### [RISK: {tier} ({score}%)] SDETKit Release Blast Radius",
        "",
        f"- **Changed Files**: `{len(changed)}`",
        f"- **Transitive Reach**: `{transitive}` of `{total_repo}` repo files (`{fanout}%` fan-out)",
        f"- **Impacted Tests**: `{tests_count}` tests (`{defense}` defense density)",
        f"- **Public Surface Exposed**: `{public}`",
        f"- **Critical Infrastructure Modified**: `{critical}`",
        f"- **Recommended Strategy**: `{strategy}`",
        "",
        f"> **Policy Decision**: {rec}",
        "",
    ]

    if cmd:
        lines.append(f"**Recommended Verification Command**:\n```bash\n{cmd}\n```\n")

    if changed:
        lines.append("<details><summary><b>Changed Files & Impact Details</b></summary>\n")
        for f in changed[:15]:
            lines.append(f"- `{f}`")
        if len(changed) > 15:
            lines.append(f"- ... and {len(changed) - 15} more")
        lines.append("\n</details>\n")

    return "\n".join(lines).strip() + "\n"


def blast_radius_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit blast-radius",
        description="Score architectural blast radius, fan-out risk, and test strategy.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Root directory of the repository (default: current directory)",
    )
    parser.add_argument(
        "--files",
        nargs="*",
        help="Specific files to analyze instead of querying git status",
    )
    parser.add_argument(
        "--base",
        help="Git base reference to diff against (e.g. main, origin/main, HEAD~1)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "md"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--out",
        help="Path to write JSON blast radius report",
    )

    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()

    files_arg: list[str] | None = None
    if args.files:
        files_arg = []
        for item in args.files:
            for piece in item.split(","):
                clean = piece.strip()
                if clean:
                    files_arg.append(clean)

    report = evaluate_blast_radius(root, files=files_arg, base=args.base)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.format == "json":
        print(json.dumps(report, indent=2))
    elif args.format in ("md", "markdown"):
        print(render_blast_radius_markdown(report))
    else:
        print(render_blast_radius_markdown(report))

    return 1 if report.get("risk_tier") == "CRITICAL" else 0


# =============================================================================
# Duration-Weighted Predictive Test Sharding & Subtree Caching Engine
# =============================================================================

SHARD_SCHEMA_VERSION = "sdetkit.shard.v1"
CACHE_SCHEMA_VERSION = "sdetkit.test_cache.v1"
DEFAULT_TEST_CACHE_PATH = ".sdetkit/test_cache.json"


def _estimate_test_duration(test_path: Path) -> float:
    """Estimate test execution duration from code metrics or historical records."""
    if not test_path.is_file():
        return 1.0

    try:
        content = test_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 1.0

    lines = content.splitlines()
    num_lines = len(lines)
    num_tests = len(
        [
            line
            for line in lines
            if line.strip().startswith("def test_") or line.strip().startswith("async def test_")
        ]
    )
    if num_tests == 0:
        num_tests = 1

    # Base duration 0.5s + 0.15s per test function + 0.002s per line of code
    est = 0.5 + (num_tests * 0.15) + (num_lines * 0.002)
    return round(max(0.2, est), 3)


def _file_sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


sha256_file = _file_sha256


def compute_ast_closure_hash(
    test_rel: str,
    root: Path,
    file_dep_graph: Mapping[str, set[str]],
    file_hashes: dict[str, str],
) -> str:
    visited: set[str] = set()
    queue = deque([test_rel])
    while queue:
        curr = queue.popleft()
        if curr in visited:
            continue
        visited.add(curr)
        for dep in file_dep_graph.get(curr, set()):
            if dep not in visited:
                queue.append(dep)

    combined_entries: list[str] = []
    for f in sorted(visited):
        if f not in file_hashes:
            file_hashes[f] = _file_sha256(root / f)
        combined_entries.append(f"{f}:{file_hashes[f]}")

    return hashlib.sha256(";".join(combined_entries).encode("utf-8")).hexdigest()


NON_PYTHON_FIXTURE_EXTENSIONS: tuple[str, ...] = (
    ".sql",
    ".json",
    ".yaml",
    ".yml",
    ".csv",
    ".toml",
    ".xml",
    ".txt",
    ".graphql",
    ".proto",
)

FIXTURE_DIRECTORY_NAMES: tuple[str, ...] = (
    "fixtures",
    "data",
    "test_data",
    "testdata",
    "cassettes",
    "snapshots",
)


def find_associated_fixtures(test_rel: str, root: Path) -> list[str]:
    """Discover non-Python fixture files associated with a test module."""
    test_path = root / test_rel
    parent = test_path.parent
    discovered: set[str] = set()

    stem = test_path.stem
    clean_stem = stem[5:] if stem.startswith("test_") else stem

    # 1. Direct name-matching fixtures in the same directory
    if parent.is_dir():
        try:
            for item in parent.iterdir():
                if item.is_file() and item.suffix in NON_PYTHON_FIXTURE_EXTENSIONS:
                    if item.stem.startswith(stem) or item.stem.startswith(clean_stem):
                        discovered.add(str(item.relative_to(root)).replace("\\", "/"))
        except OSError:
            # Skip test directory inspection if directory traversal error occurs.
            pass

        # 2. Adjacent fixture directories
        for fix_dir_name in FIXTURE_DIRECTORY_NAMES:
            fix_dir = parent / fix_dir_name
            if fix_dir.is_dir():
                try:
                    for item in fix_dir.rglob("*"):
                        if item.is_file() and item.suffix in NON_PYTHON_FIXTURE_EXTENSIONS:
                            discovered.add(str(item.relative_to(root)).replace("\\", "/"))
                except OSError:
                    # Skip sub-directory inspection if directory traversal error occurs.
                    pass

    # 3. Global project fixture directories
    for glob_dir in (root / "tests" / "fixtures", root / "fixtures", root / "tests" / "data"):
        if glob_dir.is_dir():
            try:
                for item in glob_dir.rglob("*"):
                    if item.is_file() and item.suffix in NON_PYTHON_FIXTURE_EXTENSIONS:
                        discovered.add(str(item.relative_to(root)).replace("\\", "/"))
            except OSError:
                # Skip global fixtures inspection if directory traversal error occurs.
                pass

    return sorted(discovered)


def compute_fixtures_hash(
    test_rel: str,
    root: Path,
    file_hashes: dict[str, str],
) -> str:
    """Compute deterministic SHA256 of all non-Python fixtures tied to a test."""
    fixtures = find_associated_fixtures(test_rel, root)
    if not fixtures:
        return ""

    entries: list[str] = []
    for f in fixtures:
        if f not in file_hashes:
            file_hashes[f] = _file_sha256(root / f)
        entries.append(f"{f}:{file_hashes[f]}")

    return hashlib.sha256(";".join(entries).encode("utf-8")).hexdigest()


def inspect_test_cache_smells(test_path: Path) -> tuple[bool, list[str]]:
    """Inspect AST of a test file to flag environment pollution, writes, or unmocked smells."""
    if not test_path.is_file():
        return (False, [])

    try:
        content = test_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(content, filename=str(test_path))
    except (SyntaxError, OSError) as exc:
        return (True, [f"PARSE_ERROR: {exc}"])

    smells: list[str] = []

    for node in ast.walk(tree):
        # 1. Environment and process mutation (ENV_POLLUTION)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Attribute)
                    and target.value.attr == "environ"
                ):
                    smells.append(f"ENV_POLLUTION: os.environ assignment at line {node.lineno}")
        elif isinstance(node, ast.Delete):
            for target in node.targets:
                if (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Attribute)
                    and target.value.attr == "environ"
                ):
                    smells.append(f"ENV_POLLUTION: os.environ deletion at line {node.lineno}")
        elif isinstance(node, ast.Call):
            func = node.func
            # Method mutations on os.environ
            if isinstance(func, ast.Attribute) and func.attr in (
                "pop",
                "clear",
                "update",
                "setdefault",
            ):
                if isinstance(func.value, ast.Attribute) and func.value.attr == "environ":
                    smells.append(f"ENV_POLLUTION: os.environ.{func.attr} at line {node.lineno}")
            elif isinstance(func, ast.Attribute) and func.attr == "putenv":
                smells.append(f"ENV_POLLUTION: os.putenv at line {node.lineno}")
            elif isinstance(func, ast.Attribute) and func.attr in ("append", "insert"):
                if isinstance(func.value, ast.Attribute) and func.value.attr == "path":
                    smells.append(f"ENV_POLLUTION: sys.path modification at line {node.lineno}")

            # 2. Arbitrary sleep & unmocked clocks (CLOCK_SMELL)
            elif (isinstance(func, ast.Attribute) and func.attr == "sleep") or (
                isinstance(func, ast.Name) and func.id == "sleep"
            ):
                smells.append(f"CLOCK_SMELL: arbitrary sleep at line {node.lineno}")
            elif (
                isinstance(func, ast.Attribute)
                and func.attr in ("now", "utcnow", "time", "monotonic")
            ) or (isinstance(func, ast.Name) and func.id in ("time", "monotonic")):
                smells.append(f"CLOCK_SMELL: unmocked clock call at line {node.lineno}")

            # 3. Direct socket & HTTP network calls (NETWORK_SMELL)
            elif isinstance(func, ast.Attribute) and func.attr in (
                "socket",
                "create_connection",
                "urlopen",
            ):
                smells.append(f"NETWORK_SMELL: direct socket/network call at line {node.lineno}")

            # 4. Direct filesystem writes (FS_WRITE)
            elif isinstance(func, ast.Attribute) and func.attr in ("write_text", "write_bytes"):
                smells.append(f"FS_WRITE: direct file write at line {node.lineno}")
            elif (isinstance(func, ast.Name) and func.id == "open") or (
                isinstance(func, ast.Attribute) and func.attr == "open"
            ):
                for arg in node.args[1:]:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        if any(m in arg.value for m in ("w", "a", "x", "+")):
                            smells.append(f"FS_WRITE: writable open() mode at line {node.lineno}")
                            break

    return (len(smells) > 0, smells)


def compute_test_cache_receipt(
    test_rel: str,
    root: Path,
    file_dep_graph: Mapping[str, set[str]],
    file_hashes: dict[str, str],
    lockfile_hash: str = "",
    runtime_fingerprint: str = "",
) -> JsonObject:
    """Generate a content-addressable AST cache receipt for a test module."""
    test_path = root / test_rel
    ast_hash = _file_sha256(test_path) if test_path.is_file() else ""
    transitive_hash = compute_ast_closure_hash(test_rel, root, file_dep_graph, file_hashes)
    fixtures_hash = compute_fixtures_hash(test_rel, root, file_hashes)

    if not runtime_fingerprint:
        runtime_fingerprint = f"py{sys.version_info.major}{sys.version_info.minor}-{sys.platform}"

    if not lockfile_hash:
        for lock_name in ("poetry.lock", "Pipfile.lock", "uv.lock", "requirements.txt"):
            lp = root / lock_name
            if lp.is_file():
                lockfile_hash = _file_sha256(lp)
                break

    has_smell, smells = inspect_test_cache_smells(test_path)
    if has_smell:
        cacheable = False
        bypass_reasons = smells
        cache_key = ""
    else:
        cacheable = True
        bypass_reasons = []
        raw_key = (
            f"ast:{ast_hash};"
            f"transitive:{transitive_hash};"
            f"fixtures:{fixtures_hash};"
            f"lock:{lockfile_hash};"
            f"runtime:{runtime_fingerprint}"
        )
        cache_key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    return {
        "schema_version": "1.0",
        "node_id": test_rel,
        "ast_subtree_sha256": ast_hash,
        "transitive_deps_sha256": transitive_hash,
        "fixtures_sha256": fixtures_hash,
        "lockfile_sha256": lockfile_hash,
        "runtime_fingerprint": runtime_fingerprint,
        "cacheable": cacheable,
        "cache_key": cache_key,
        "bypass_reasons": bypass_reasons,
    }


def shard_test_suite(
    root: Path,
    *,
    nodes: int = 4,
    index: int | None = None,
    test_files: Sequence[str] | None = None,
    use_cache: bool = False,
    cache_path: str | Path | None = None,
) -> JsonObject:
    """Partition tests across N workers using Longest Processing Time (LPT) balancing."""
    resolved_root = root.resolve()
    total_nodes = max(1, min(nodes, 128))
    target_idx = max(0, min(index, total_nodes - 1)) if index is not None else 0

    # 1. Discover or validate target test files
    tests_found: list[str] = []
    if test_files:
        tests_found = [str(f).replace("\\", "/") for f in test_files if str(f).strip()]
    else:
        tests_dir = resolved_root / "tests"
        if tests_dir.is_dir():
            for p in sorted(tests_dir.rglob("test_*.py")):
                if p.is_file():
                    tests_found.append(str(p.relative_to(resolved_root)).replace("\\", "/"))
        if not tests_found:
            for p in sorted(resolved_root.rglob("test_*.py")):
                if p.is_file() and not any(part in _SKIPPED_DIRS for part in p.parts):
                    tests_found.append(str(p.relative_to(resolved_root)).replace("\\", "/"))

    # 2. Subtree AST Caching & Smell Audit (if requested)
    cached_tests: list[str] = []
    active_tests: list[str] = []
    smell_bypassed_tests: list[str] = []
    current_cache_hashes: dict[str, str] = {}
    current_cache_receipts: dict[str, JsonObject] = {}
    saved_cache_hashes: dict[str, str] = {}
    avoided_duration_sec: float = 0.0

    cache_file = resolved_root / (cache_path if cache_path else DEFAULT_TEST_CACHE_PATH)
    if use_cache and cache_file.is_file():
        try:
            saved_data = json.loads(cache_file.read_text(encoding="utf-8"))
            if saved_data.get("schema_version") == CACHE_SCHEMA_VERSION:
                saved_cache_hashes = saved_data.get("hashes", {})
                if not saved_cache_hashes and "receipts" in saved_data:
                    for k, rec in saved_data.get("receipts", {}).items():
                        if isinstance(rec, dict) and "cache_key" in rec:
                            saved_cache_hashes[k] = rec["cache_key"]
        except (json.JSONDecodeError, OSError):
            saved_cache_hashes = {}

    import_graph = build_import_graph(resolved_root)
    file_hashes: dict[str, str] = {}

    for t in tests_found:
        receipt = compute_test_cache_receipt(
            t, resolved_root, import_graph.forward_graph, file_hashes
        )
        current_cache_receipts[t] = receipt
        cache_k = str(receipt.get("cache_key") or "")
        current_cache_hashes[t] = cache_k

        if use_cache:
            if not receipt.get("cacheable"):
                smell_bypassed_tests.append(t)
                active_tests.append(t)
            elif cache_k and t in saved_cache_hashes and saved_cache_hashes[t] == cache_k:
                cached_tests.append(t)
                p = resolved_root / t
                dur = _estimate_test_duration(p)
                avoided_duration_sec = round(avoided_duration_sec + dur, 3)
            else:
                active_tests.append(t)
        else:
            active_tests.append(t)

    # Distribute active tests or all tests if cache was not requested
    distribute_list = active_tests if (use_cache and active_tests) else tests_found
    if use_cache and not active_tests and tests_found:
        distribute_list = []

    # 3. Compute duration for each test and sort descending (LPT)
    test_durations: list[tuple[str, float]] = []
    for t in distribute_list:
        p = resolved_root / t
        dur = _estimate_test_duration(p)
        test_durations.append((t, dur))

    test_durations.sort(key=lambda x: x[1], reverse=True)

    # 4. Greedy Partitioning across N shards
    shard_allocations: list[list[str]] = [[] for _ in range(total_nodes)]
    shard_durations: list[float] = [0.0] * total_nodes

    for t, dur in test_durations:
        min_shard_idx = shard_durations.index(min(shard_durations))
        shard_allocations[min_shard_idx].append(t)
        shard_durations[min_shard_idx] = round(shard_durations[min_shard_idx] + dur, 3)

    total_est_duration = round(sum(shard_durations), 3)
    target_shard_duration = round(total_est_duration / total_nodes, 3) if total_nodes > 0 else 0.0
    max_shard_dur = max(shard_durations) if shard_durations else 0.0
    min_shard_dur = min(shard_durations) if shard_durations else 0.0
    balance_efficiency = (
        round((target_shard_duration / max_shard_dur) * 100.0, 1) if max_shard_dur > 0.0 else 100.0
    )

    shards_data: list[JsonObject] = []
    for i in range(total_nodes):
        files_for_shard = shard_allocations[i]
        shards_data.append(
            {
                "index": i,
                "file_count": len(files_for_shard),
                "estimated_duration": shard_durations[i],
                "files": files_for_shard,
                "pytest_args": " ".join(files_for_shard),
            }
        )

    selected = shards_data[target_idx] if target_idx < len(shards_data) else shards_data[0]

    return {
        "schema_version": SHARD_SCHEMA_VERSION,
        "nodes": total_nodes,
        "selected_index": target_idx,
        "balance_efficiency_pct": balance_efficiency,
        "total_tests_discovered": len(tests_found),
        "cached_tests_skipped": len(cached_tests),
        "cached_test_files": cached_tests,
        "smell_bypassed_tests_count": len(smell_bypassed_tests),
        "smell_bypassed_tests": smell_bypassed_tests,
        "avoided_duration_sec": avoided_duration_sec,
        "active_tests_distributed": len(distribute_list),
        "total_estimated_duration_sec": total_est_duration,
        "target_duration_per_shard_sec": target_shard_duration,
        "max_shard_duration_sec": max_shard_dur,
        "min_shard_duration_sec": min_shard_dur,
        "cache_used": use_cache,
        "shards": shards_data,
        "selected_shard": selected,
        "current_closure_hashes": current_cache_hashes,
        "cache_receipts": current_cache_receipts,
    }


def render_shard_markdown(report: JsonObject) -> str:
    nodes = report.get("nodes", 1)
    sel_idx = report.get("selected_index", 0)
    eff = report.get("balance_efficiency_pct", 100.0)
    total_tests = report.get("total_tests_discovered", 0)
    cached = report.get("cached_tests_skipped", 0)
    active = report.get("active_tests_distributed", 0)
    total_dur = report.get("total_estimated_duration_sec", 0.0)
    target_dur = report.get("target_duration_per_shard_sec", 0.0)
    max_dur = report.get("max_shard_duration_sec", 0.0)
    shards = report.get("shards") or []
    selected = report.get("selected_shard") or {}

    lines = [
        f"### [SHARD: {eff}% EFFICIENCY] SDETKit Duration-Weighted Test Sharding",
        "",
        f"- **Cluster Parallelism**: `{nodes} Nodes` (Target Duration: `{target_dur}s` / node)",
        f"- **Balance Efficiency**: `{eff}%` (Max node duration: `{max_dur}s`)",
        f"- **Test Distribution**: `{active} Active` ({cached} cached & skipped out of {total_tests} total)",
        f"- **Total Workload**: `{total_dur}s` total test time compressed into `{max_dur}s` wall-clock time",
        "",
        "#### Shard Partition Matrix",
        "| Shard Node | Tests Assigned | Estimated Runtime | Delta vs Target |",
        "| :--- | :--- | :--- | :--- |",
    ]

    for s in shards:
        idx = s.get("index", 0)
        cnt = s.get("file_count", 0)
        dur = s.get("estimated_duration", 0.0)
        delta = round(dur - target_dur, 2)
        marker = " [TARGET SHARD]" if idx == sel_idx else ""
        lines.append(f"| **Node {idx}**{marker} | `{cnt} files` | `{dur}s` | `{delta:+}s` |")

    lines.append("")
    lines.append(
        f"> **Selected Worker (Node {sel_idx})**: `{selected.get('file_count', 0)}` tests assigned (`{selected.get('estimated_duration', 0.0)}s`)"
    )
    lines.append("")
    pytest_args = selected.get("pytest_args", "")
    if pytest_args:
        lines.append("```bash")
        lines.append(f"pytest {pytest_args}")
        lines.append("```\n")

    return "\n".join(lines).strip() + "\n"


def shard_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit shard",
        description="Duration-weighted predictive test sharding and AST subtree caching.",
    )
    parser.add_argument(
        "--repo-root",
        "--root",
        "-r",
        dest="repo_root",
        default=".",
        help="Root directory of the repository (default: current dir)",
    )
    parser.add_argument(
        "--nodes", type=int, default=2, help="Number of parallel worker nodes (default: 2)"
    )
    parser.add_argument(
        "--index",
        type=int,
        default=0,
        help="Target worker index to output for execution (default: 0)",
    )
    parser.add_argument(
        "--cache",
        action="store_true",
        help="Enable AST subtree caching to skip unimpacted tests",
    )
    parser.add_argument(
        "--cache-manifest",
        default=None,
        help="Path to test cache manifest (default: .sdetkit/test_cache.json)",
    )
    parser.add_argument(
        "--save-cache",
        action="store_true",
        help="Save current AST subtree closure hashes to cache manifest",
    )
    parser.add_argument(
        "--format",
        choices=["md", "markdown", "json", "text", "args"],
        default="md",
        help="Output format (default: md)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Write JSON payload to a file",
    )
    parser.add_argument(
        "test_files",
        nargs="*",
        help="Explicit list of test files to partition (default: auto-discover)",
    )

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    root = Path(args.repo_root).resolve()

    report = shard_test_suite(
        root=root,
        nodes=args.nodes,
        index=args.index,
        test_files=args.test_files if args.test_files else None,
        use_cache=args.cache,
        cache_path=args.cache_manifest,
    )

    if args.save_cache:
        c_path = root / (args.cache_manifest if args.cache_manifest else DEFAULT_TEST_CACHE_PATH)
        c_path.parent.mkdir(parents=True, exist_ok=True)
        cache_data = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "updated_at": str(time.time()),
            "hashes": report.get("current_closure_hashes", {}),
            "receipts": report.get("cache_receipts", {}),
            "avoided_duration_sec": report.get("avoided_duration_sec", 0.0),
        }
        c_path.write_text(json.dumps(cache_data, indent=2), encoding="utf-8")

        ledger_path = root / ".sdetkit" / "finops_ledger.jsonl"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_entry = {
            "timestamp": time.time(),
            "iso_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "avoided_compute_seconds": float(report.get("avoided_duration_sec", 0.0)),
            "cached_tests_count": int(report.get("cached_tests_skipped", 0)),
            "active_tests_count": int(report.get("active_tests_distributed", 0)),
            "source": "shard_cache",
        }
        with ledger_path.open("a", encoding="utf-8") as lf:
            lf.write(json.dumps(ledger_entry, separators=(",", ":")) + "\n")

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.format == "json":
        print(json.dumps(report, indent=2))
    elif args.format == "args":
        print(report.get("selected_shard", {}).get("pytest_args", ""))
    elif args.format == "text":
        eff = report.get("balance_efficiency_pct", 100.0)
        sel = report.get("selected_shard", {})
        print(
            f"shards={report.get('nodes')} efficiency={eff}% node_{args.index}_files={sel.get('file_count')}"
        )
    else:
        print(render_shard_markdown(report))

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(argv) if argv is not None else list(sys.argv[1:])
    is_shard = (
        ("shard" in sys.argv)
        or (os.environ.get("SDETKIT_SUBCOMMAND") == "shard")
        or (bool(args_list) and args_list[0] == "shard")
    )
    if is_shard:
        if args_list and args_list[0] == "shard":
            args_list = args_list[1:]
        return shard_main(args_list)
    is_blast_radius = (
        ("blast-radius" in sys.argv)
        or ("blast_radius" in sys.argv)
        or (os.environ.get("SDETKIT_SUBCOMMAND") in {"blast-radius", "blast_radius"})
        or (bool(args_list) and args_list[0] in {"blast-radius", "blast_radius"})
    )
    if is_blast_radius:
        if args_list and args_list[0] in {"blast-radius", "blast_radius"}:
            args_list = args_list[1:]
        return blast_radius_main(args_list)
    parser = argparse.ArgumentParser(
        prog="sdetkit verify impact",
        description="Predict and select impacted tests via AST dependency graph traversal.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Root directory of the repository (default: current directory)",
    )
    parser.add_argument(
        "--files",
        nargs="*",
        help="Specific files to analyze instead of querying git status",
    )
    parser.add_argument(
        "--base",
        help="Git base reference to diff against (e.g. main, origin/main, HEAD~1)",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Execute the selected impacted tests immediately with pytest",
    )
    parser.add_argument(
        "--fail-fast",
        "-x",
        action="store_true",
        help="Stop test execution on first failure",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Maximum timeout in seconds for test execution (default: 180)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--out",
        help="Path to write JSON impact report artifact",
    )

    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()

    files_arg: list[str] | None = None
    if args.files:
        files_arg = []
        for item in args.files:
            for piece in item.split(","):
                clean = piece.strip()
                if clean:
                    files_arg.append(clean)

    report = analyze_impact(root, files=files_arg, base=args.base)

    exec_res: JsonObject | None = None
    if args.run and report.get("all_impacted_tests"):
        exec_res = run_impacted_tests(
            report,
            root=root,
            timeout=args.timeout,
            fail_fast=args.fail_fast,
        )

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        combined = {**report, "execution": exec_res} if exec_res else report
        out_path.write_text(json.dumps(combined, indent=2), encoding="utf-8")

    if args.format == "json":
        combined = {**report, "execution": exec_res} if exec_res else report
        print(json.dumps(combined, indent=2))
    elif args.format == "markdown":
        print(render_markdown(report, exec_res))
    else:
        print(render_markdown(report, exec_res))

    if exec_res and not exec_res.get("ok"):
        return int(exec_res.get("returncode") or 1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
