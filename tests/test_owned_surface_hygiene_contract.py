from __future__ import annotations

import ast
import re
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(".").resolve()

TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".rst",
    ".txt",
    ".toml",
    ".yml",
    ".yaml",
    ".json",
    ".ini",
    ".cfg",
    ".sh",
}

PATTERNS = {
    "debug_leftover": re.compile(r"\b(pdb\.set_trace|breakpoint\(\)|console\.log\()", re.I),
    "unfinished_marker": re.compile(r"\b(TODO|FIXME|HACK|XXX|WIP)\b", re.I),
    "unsafe_yaml_load": re.compile(r"\byaml\.load\s*\("),
    "shell_true": re.compile(r"shell\s*=\s*True"),
    "weak_assertion": re.compile(r"assert\s+(True|1|bool\()", re.I),
    "test_skip_or_xfail": re.compile(r"pytest\.mark\.(skip|xfail)|unittest\.skip", re.I),
}

GOVERNED_BUCKETS = {
    "live_src_and_scripts",
    "workflows",
    "current_docs",
    "templates",
    "other",
}


def _tracked_text_files() -> list[Path]:
    output = subprocess.check_output(["git", "ls-files"], text=True)
    paths = [ROOT / line for line in output.splitlines()]
    return [
        path
        for path in paths
        if path.exists()
        and path.is_file()
        and (
            path.suffix.lower() in TEXT_SUFFIXES
            or path.name
            in {
                "CHANGELOG.md",
                "Makefile",
                "README.md",
                "mkdocs.yml",
                "pyproject.toml",
            }
        )
        and path.relative_to(ROOT).parts[:2] != ("docs", "artifacts")
    ]


def _bucket_for(path: Path) -> str:
    rel = path.relative_to(ROOT)
    first = rel.parts[0] if rel.parts else ""
    if first in {"src", "scripts"}:
        return "live_src_and_scripts"
    if first == ".github":
        return "workflows"
    if first == "docs":
        return "current_docs"
    if first == "templates":
        return "templates"
    if first == "tests":
        return "tests_and_fixtures"
    return "other"


def _is_allowed_scanner_vocabulary(rel: str, line: str) -> bool:
    lowered = line.lower()
    if rel.startswith("src/sdetkit/gates/security_gate.py"):
        return True
    if rel.startswith("src/sdetkit/premium_gate_engine.py") and (
        "shell=True" in line or "yaml.load(" in line
    ):
        return True
    if rel.startswith("src/sdetkit/repo.py") and "subprocess with shell=True" in line:
        return True
    if rel.startswith("src/sdetkit/boost.py") and ("todo" in lowered or "fixme" in lowered):
        return True
    if rel.startswith("src/sdetkit/index.py") and any(
        marker in lowered for marker in ("todo", "fixme", "xxx")
    ):
        return True
    if rel.startswith("src/sdetkit/phases/phase1_hardening_29.py") and "_STALE_MARKERS" in line:
        return True
    return False


def _actionable_surface_findings() -> dict[str, list[str]]:
    findings: dict[str, list[str]] = defaultdict(list)

    for path in _tracked_text_files():
        rel = path.relative_to(ROOT).as_posix()
        bucket = _bucket_for(path)
        if bucket not in GOVERNED_BUCKETS:
            continue

        text = path.read_text(encoding="utf-8", errors="ignore")
        for line_number, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            for name, pattern in PATTERNS.items():
                if pattern.search(stripped) and not _is_allowed_scanner_vocabulary(rel, stripped):
                    findings[bucket].append(f"{rel}:{line_number}: {name}: {stripped}")

        if path.suffix == ".py" and bucket in {"live_src_and_scripts", "templates"}:
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler) and node.type is None:
                    findings[bucket].append(f"{rel}:{node.lineno}: bare_except")
                if isinstance(node, ast.Call):
                    fn = node.func
                    name = (
                        fn.id
                        if isinstance(fn, ast.Name)
                        else fn.attr
                        if isinstance(fn, ast.Attribute)
                        else ""
                    )
                    if name in {"eval", "exec", "input"}:
                        findings[bucket].append(f"{rel}:{node.lineno}: risky_call_{name}")

    return dict(findings)


def test_non_test_owned_surfaces_stay_actionable_hygiene_clean() -> None:
    findings = _actionable_surface_findings()

    assert findings == {}
