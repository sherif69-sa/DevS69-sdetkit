from __future__ import annotations

import sys
from pathlib import Path

from sdetkit.import_hazards import find_stdlib_shadowing


def _pick_stdlib_name(candidates: tuple[str, ...]) -> str | None:
    names = getattr(sys, "stdlib_module_names", None)
    if not names:
        return None
    stdlib = set(names)
    for c in candidates:
        if c in stdlib:
            return c
    return None


def test_find_stdlib_shadowing_flags_top_level_module_file(tmp_path: Path) -> None:
    name = _pick_stdlib_name(("tomllib", "json", "email", "pathlib"))
    if not name:
        return

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / f"{name}.py").write_text("x = 1\n", encoding="utf-8")

    got = find_stdlib_shadowing(tmp_path)
    assert got == [f"src/{name}.py"]


def test_find_stdlib_shadowing_flags_top_level_package_dir(tmp_path: Path) -> None:
    name = _pick_stdlib_name(("email", "xml", "http", "asyncio"))
    if not name:
        return

    pkg = tmp_path / "src" / name
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("x = 1\n", encoding="utf-8")

    got = find_stdlib_shadowing(tmp_path)
    assert got == [f"src/{name}"]
