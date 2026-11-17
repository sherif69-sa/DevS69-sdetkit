"""`sdetkit verify impact`: predictive test selection and AST dependency impact engine."""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
import time
from collections import defaultdict, deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sdetkit.gates.project_env import resolve_project_python

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

# Directories to skip when indexing repository Python files
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
            _normalize_rel(Path(f), resolved_root)
            if Path(f).is_absolute()
            else str(f).replace("\\", "/")
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


def main(argv: list[str] | None = None) -> int:
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
