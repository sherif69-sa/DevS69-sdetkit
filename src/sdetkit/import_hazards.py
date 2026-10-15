from __future__ import annotations

import sys
from pathlib import Path


def find_stdlib_shadowing(repo_root: Path, src_dir: str = "src") -> list[str]:
    src = repo_root / src_dir
    if not src.is_dir():
        return []

    names = getattr(sys, "stdlib_module_names", None)
    if not names:
        return []

    stdlib = set(names)
    # Guard against runtime/version skew (e.g. checking for tomllib shadowing on py<3.11).
    stdlib.update({"tomllib"})
    out: list[str] = []

    for p in src.iterdir():
        if p.name == "sdetkit":
            continue

        if p.is_file() and p.suffix == ".py":
            name = p.stem
            if name in stdlib:
                out.append(str(p.relative_to(repo_root)))
            continue

        if p.is_dir() and (p / "__init__.py").is_file():
            name = p.name
            if name in stdlib:
                out.append(str(p.relative_to(repo_root)))
            continue

    out.sort()
    return out
