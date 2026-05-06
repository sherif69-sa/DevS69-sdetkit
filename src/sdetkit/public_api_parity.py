from __future__ import annotations

import ast
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from sdetkit.index import IGNORED_DIRS

SCHEMA_VERSION = "sdetkit.investigate.parity.v1"
PYTHON_SOURCE_DIRS = {"src", "sdetkit"}
HELPER_TOKENS = ("json", "http", "client", "request", "fetch", "call", "send", "load", "get")


def _iter_repo_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for current, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIRS)
        base = Path(current)
        if any(part in IGNORED_DIRS for part in base.relative_to(root).parts):
            continue
        for name in sorted(names):
            files.append(base / name)
    return files


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_source_file(rel: str) -> bool:
    parts = rel.split("/")
    return rel.endswith(".py") and bool(parts) and parts[0] in PYTHON_SOURCE_DIRS


def _is_test_file(rel: str) -> bool:
    parts = rel.split("/")
    name = parts[-1] if parts else rel
    return rel.endswith(".py") and ("tests" in parts or name.startswith("test_"))


def _surface_match(surface: str, rel: str, text: str) -> bool:
    normalized = surface.lower().replace("-", "_")
    return normalized in rel.lower().replace("-", "_") or normalized in text.lower().replace("-", "_")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _surface_files(root: Path, surface: str) -> tuple[list[str], list[str]]:
    production_files: list[str] = []
    test_files: list[str] = []
    for path in _iter_repo_files(root):
        rel = _rel(root, path)
        if not rel.endswith(".py"):
            continue
        text = _read(path)
        if not _surface_match(surface, rel, text):
            continue
        if _is_source_file(rel):
            production_files.append(rel)
        elif _is_test_file(rel):
            test_files.append(rel)
    return sorted(production_files), sorted(test_files)


def _parse_file(root: Path, rel: str) -> ast.Module | None:
    try:
        return ast.parse((root / rel).read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return None


def _class_methods(root: Path, files: list[str]) -> dict[str, dict[str, str]]:
    classes: dict[str, dict[str, str]] = defaultdict(dict)
    for rel in files:
        tree = _parse_file(root, rel)
        if tree is None:
            continue
        for node in tree.body:
            if not isinstance(node, ast.ClassDef) or node.name.startswith("_"):
                continue
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and not child.name.startswith(
                    "_"
                ):
                    classes[node.name][child.name] = f"{node.name}.{child.name}"
    return dict(classes)


def _module_functions(root: Path, files: list[str]) -> dict[str, str]:
    functions: dict[str, str] = {}
    for rel in files:
        tree = _parse_file(root, rel)
        if tree is None:
            continue
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                functions[node.name] = node.name
    return functions


def _public_symbols(classes: dict[str, dict[str, str]], functions: dict[str, str]) -> list[str]:
    symbols = sorted(functions)
    for class_name, methods in sorted(classes.items()):
        symbols.append(class_name)
        symbols.extend(symbol for _, symbol in sorted(methods.items()))
    return symbols


def _sync_class_for(async_class: str) -> str:
    return async_class.replace("Async", "", 1)


def _sync_async_method_findings(classes: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for async_class, async_methods in sorted(classes.items()):
        if "Async" not in async_class:
            continue
        sync_class = _sync_class_for(async_class)
        sync_methods = classes.get(sync_class, {})
        if not sync_methods:
            continue
        for method, sync_symbol in sorted(sync_methods.items()):
            if method not in async_methods:
                findings.append(
                    {
                        "kind": "SYNC_ASYNC_METHOD_GAP",
                        "severity": "warning",
                        "sync_symbol": sync_symbol,
                        "async_symbol": f"{async_class}.{method}",
                        "status": "missing",
                        "recommended_test": "focused sync/async parity test",
                    }
                )
    return findings


def _helper_needs_pair(name: str) -> bool:
    low = name.lower()
    return any(token in low for token in HELPER_TOKENS)


def _sync_async_helper_findings(functions: dict[str, str], classes: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    async_context = any("Async" in class_name for class_name in classes) or any(
        name.startswith("async_") for name in functions
    )
    if not async_context:
        return findings
    for name in sorted(functions):
        if name.startswith("async_"):
            sync_name = name.removeprefix("async_")
            if sync_name not in functions and _helper_needs_pair(sync_name):
                findings.append(
                    {
                        "kind": "SYNC_ASYNC_HELPER_GAP",
                        "severity": "warning",
                        "sync_symbol": sync_name,
                        "async_symbol": name,
                        "status": "missing_sync_helper",
                        "recommended_test": "focused sync/async helper parity test",
                    }
                )
        elif _helper_needs_pair(name) and f"async_{name}" not in functions:
            findings.append(
                {
                    "kind": "SYNC_ASYNC_HELPER_GAP",
                    "severity": "warning",
                    "sync_symbol": name,
                    "async_symbol": f"async_{name}",
                    "status": "missing_async_helper",
                    "recommended_test": "focused sync/async helper parity test",
                }
            )
    return findings


def _cli_files(files: list[str]) -> list[str]:
    return [rel for rel in files if "cli" in Path(rel).stem.lower() or rel.endswith("__main__.py")]


def _cli_backend_findings(root: Path, production_files: list[str], classes: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    cli_files = _cli_files(production_files)
    if not cli_files:
        return []
    cli_text = "\n".join(_read(root / rel) for rel in cli_files)
    findings: list[dict[str, str]] = []
    for class_name, methods in sorted(classes.items()):
        if "cli" in class_name.lower():
            continue
        for method, symbol in sorted(methods.items()):
            if method not in cli_text:
                findings.append(
                    {
                        "kind": "CLI_BACKEND_PARITY_GAP",
                        "severity": "warning",
                        "backend_symbol": symbol,
                        "cli_surface": ",".join(cli_files),
                        "status": "not_referenced_by_cli_surface",
                        "recommended_test": "focused CLI/backend parity test",
                    }
                )
    return findings


def _public_mode_findings(test_files: list[str], public_symbols: list[str]) -> list[dict[str, str]]:
    if test_files or not public_symbols:
        return []
    return [
        {
            "kind": "PUBLIC_MODE_UNTESTED",
            "severity": "warning",
            "public_symbol": public_symbols[0],
            "status": "no_matching_surface_tests",
            "recommended_test": "focused public mode coverage",
        }
    ]


def detect_public_api_parity(root: str | Path, surface: str) -> dict[str, Any]:
    root_path = Path(root).resolve()
    if not root_path.exists() or not root_path.is_dir():
        raise OSError(f"repository root does not exist: {root}")
    clean_surface = surface.strip()
    if not clean_surface:
        raise OSError("surface name is required")
    production_files, test_files = _surface_files(root_path, clean_surface)
    classes = _class_methods(root_path, production_files)
    functions = _module_functions(root_path, production_files)
    symbols = _public_symbols(classes, functions)
    findings = (
        _sync_async_method_findings(classes)
        + _sync_async_helper_findings(functions, classes)
        + _cli_backend_findings(root_path, production_files, classes)
        + _public_mode_findings(test_files, symbols)
    )
    counts = Counter(str(item.get("kind", "UNKNOWN")) for item in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "diagnostic_only": True,
        "automation_allowed": False,
        "surface": clean_surface,
        "production_files": production_files,
        "test_files": test_files,
        "public_symbols": symbols,
        "finding_count": len(findings),
        "counts_by_kind": dict(sorted(counts.items())),
        "findings": sorted(findings, key=lambda item: (str(item.get("kind")), str(item.get("status")), str(item))),
    }
