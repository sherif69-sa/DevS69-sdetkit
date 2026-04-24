#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must be a JSON object")
    return payload


def build_delta(*, baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    base_modules = baseline.get("modules", [])
    curr_modules = current.get("modules", [])
    by_path: dict[str, dict[str, Any]] = {}
    if isinstance(base_modules, list):
        for row in base_modules:
            if isinstance(row, dict):
                by_path[str(row.get("path", ""))] = row

    rows: list[dict[str, Any]] = []
    if isinstance(curr_modules, list):
        for row in curr_modules:
            if not isinstance(row, dict):
                continue
            path = str(row.get("path", ""))
            prev = by_path.get(path, {})
            rows.append(
                {
                    "path": path,
                    "lines_of_code_delta": int(row.get("lines_of_code", 0))
                    - int(prev.get("lines_of_code", 0)),
                    "function_count_delta": int(row.get("function_count", 0))
                    - int(prev.get("function_count", 0)),
                    "class_count_delta": int(row.get("class_count", 0))
                    - int(prev.get("class_count", 0)),
                }
            )
    rows.sort(key=lambda item: item["path"])
    return {
        "schema_version": "sdetkit.phase2-hotspot-delta.v1",
        "baseline": str(baseline.get("generated_at_utc", "")),
        "current": str(current.get("generated_at_utc", "")),
        "modules": rows,
        "summary": {
            "module_count": len(rows),
            "total_lines_of_code_delta": sum(int(r["lines_of_code_delta"]) for r in rows),
            "total_function_count_delta": sum(int(r["function_count_delta"]) for r in rows),
            "total_class_count_delta": sum(int(r["class_count_delta"]) for r in rows),
        },
    }


def _to_markdown(delta: dict[str, Any]) -> str:
    lines = [
        "# Phase 2 Hotspot Delta",
        "",
        f"- Baseline generated_at_utc: `{delta.get('baseline', '')}`",
        f"- Current generated_at_utc: `{delta.get('current', '')}`",
        "",
        "| Module | LOC Δ | Functions Δ | Classes Δ |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in delta.get("modules", []):
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| `{row.get('path', '')}` | {int(row.get('lines_of_code_delta', 0))} | {int(row.get('function_count_delta', 0))} | {int(row.get('class_count_delta', 0))} |"
        )
    summary = delta.get("summary", {})
    if isinstance(summary, dict):
        lines.extend(
            [
                "",
                "## Summary",
                f"- total LOC delta: `{int(summary.get('total_lines_of_code_delta', 0))}`",
                f"- total function delta: `{int(summary.get('total_function_count_delta', 0))}`",
                f"- total class delta: `{int(summary.get('total_class_count_delta', 0))}`",
            ]
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build phase-2 hotspot delta from baseline/current metrics."
    )
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-md", type=Path, required=True)
    args = parser.parse_args(argv)

    baseline = _load(args.baseline)
    current = _load(args.current)
    delta = build_delta(baseline=baseline, current=current)

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(delta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.out_md.write_text(_to_markdown(delta), encoding="utf-8")

    print(
        json.dumps(
            {"ok": True, "out_json": args.out_json.as_posix(), "out_md": args.out_md.as_posix()}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
