#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _module_metrics(path: Path) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = source.splitlines()
    function_lengths: list[tuple[str, int]] = []
    function_count = 0
    class_count = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_count += 1
            if hasattr(node, "end_lineno") and isinstance(node.end_lineno, int):
                length = max(1, int(node.end_lineno) - int(node.lineno) + 1)
                function_lengths.append((node.name, length))
        elif isinstance(node, ast.ClassDef):
            class_count += 1
    function_lengths.sort(key=lambda row: (-row[1], row[0]))
    return {
        "path": path.as_posix(),
        "lines_of_code": len(lines),
        "function_count": function_count,
        "class_count": class_count,
        "largest_functions": [
            {"name": name, "lines": lines_count} for name, lines_count in function_lengths[:5]
        ],
    }


def build_payload(paths: list[Path]) -> dict[str, Any]:
    modules = [_module_metrics(path) for path in paths]
    return {
        "schema_version": "sdetkit.phase2-hotspot-baseline.v1",
        "generated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "modules": modules,
        "summary": {
            "module_count": len(modules),
            "total_lines_of_code": sum(int(m.get("lines_of_code", 0)) for m in modules),
            "total_function_count": sum(int(m.get("function_count", 0)) for m in modules),
            "total_class_count": sum(int(m.get("class_count", 0)) for m in modules),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build phase-2 hotspot baseline metrics for repo.py and doctor.py."
    )
    parser.add_argument(
        "--paths",
        nargs="+",
        default=["src/sdetkit/repo.py", "src/sdetkit/doctor.py"],
        help="Module paths to include in baseline.",
    )
    parser.add_argument(
        "--out",
        default="docs/artifacts/phase2-hotspot-baseline-2026-04-24.json",
        help="Output JSON path.",
    )
    args = parser.parse_args(argv)

    paths = [Path(raw) for raw in args.paths]
    payload = build_payload(paths)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "out": out.as_posix(), "modules": len(paths)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
