from __future__ import annotations

import ast
from datetime import timezone
from pathlib import Path

from sdetkit._datetime import UTC

ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOTS = ("src", "scripts", "tools", "tests")
ALLOWED_PYTHON_FILES = {
    Path("src/sitecustomize.py"),
    Path("src/sdetkit/_datetime.py"),
}


def _project_python_files() -> list[Path]:
    files: list[Path] = []
    for root_name in PYTHON_ROOTS:
        root = ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            rel = path.relative_to(ROOT)
            if "__pycache__" in rel.parts:
                continue
            if rel in ALLOWED_PYTHON_FILES:
                continue
            files.append(path)
    return sorted(files)


def test_utc_compat_helper_is_timezone_utc() -> None:
    assert UTC.utcoffset(None) == timezone.utc.utcoffset(None)


def test_python_modules_do_not_depend_on_datetime_utc_symbol() -> None:
    violations: list[str] = []

    for path in _project_python_files():
        rel = path.relative_to(ROOT)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(rel))

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "datetime":
                for alias in node.names:
                    if alias.name == "UTC":
                        violations.append(f"{rel}:{node.lineno}: imports datetime.UTC directly")

            if isinstance(node, ast.Attribute) and node.attr == "UTC":
                value = node.value
                if isinstance(value, ast.Name) and value.id in {"datetime", "dt", "_dt"}:
                    violations.append(f"{rel}:{node.lineno}: reads {value.id}.UTC directly")

    assert not violations, "\n".join(violations)


def test_shell_embedded_python_does_not_import_datetime_utc_directly() -> None:
    violations: list[str] = []

    for root_name in ("scripts", "tools"):
        root = ROOT / root_name
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.sh")):
            rel = path.relative_to(ROOT)
            text = path.read_text(encoding="utf-8")
            if "from datetime import UTC" in text or "from datetime import datetime, UTC" in text:
                violations.append(f"{rel}: imports datetime.UTC directly")

    assert not violations, "\n".join(violations)
