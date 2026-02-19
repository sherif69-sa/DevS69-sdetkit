from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

_DEMO_FLOW = [
    {
        "step": "Health check",
        "command": "python -m sdetkit doctor --format text",
        "expected": [
            "Doctor score:",
            "Recommendations:",
        ],
        "why": "Confirms repository hygiene and points to the highest-leverage fixes first.",
    },
    {
        "step": "Repository audit",
        "command": "python -m sdetkit repo audit --format markdown",
        "expected": [
            "# Repo audit",
            "## Findings",
        ],
        "why": "Surfaces policy, CI, and governance gaps in a report-ready format.",
    },
    {
        "step": "Security baseline",
        "command": "python -m sdetkit security --format markdown",
        "expected": [
            "# Security suite",
            "## Checks",
        ],
        "why": "Produces a security-focused snapshot that can be attached to release reviews.",
    },
]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sdetkit demo")
    p.add_argument(
        "--format",
        choices=["text", "markdown", "json"],
        default="text",
        help="Output format.",
    )
    p.add_argument(
        "--output",
        default="",
        help="Optional file path to also write the rendered demo flow.",
    )
    return p


def _as_text() -> str:
    lines = ["Day 2 demo path (target: ~60 seconds)", ""]
    for item in _DEMO_FLOW:
        lines.append(f"[{item['step']}]")
        lines.append(f"  run     : {item['command']}")
        lines.append(f"  expect  : {item['expected'][0]} | {item['expected'][1]}")
        lines.append(f"  outcome : {item['why']}")
        lines.append("")
    lines.append("Tip: copy this plan into onboarding docs or CI runbooks for first-use demos.")
    return "\n".join(lines)


def _as_markdown() -> str:
    rows = [
        "# Day 2 demo path (target: ~60 seconds)",
        "",
        "| Step | Command | Expected output snippets | Outcome |",
        "|---|---|---|---|",
    ]
    for item in _DEMO_FLOW:
        expected = "<br>".join(f"`{snippet}`" for snippet in item["expected"])
        rows.append(
            f"| {item['step']} | `{item['command']}` | {expected} | {item['why']} |"
        )
    rows.append("")
    rows.append("Related docs: [README quick start](../README.md#quick-start), [repo audit](repo-audit.md).")
    return "\n".join(rows)


def _as_json() -> str:
    return json.dumps({"name": "day2-demo-path", "steps": _DEMO_FLOW}, indent=2, sort_keys=True)


def _render(fmt: str) -> str:
    if fmt == "json":
        return _as_json()
    if fmt == "markdown":
        return _as_markdown()
    return _as_text()


def main(argv: Sequence[str] | None = None) -> int:
    ns = _build_parser().parse_args(argv)
    rendered = _render(ns.format)
    print(rendered)

    if ns.output:
        out_path = Path(ns.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        trailing = "" if rendered.endswith("\n") else "\n"
        out_path.write_text(rendered + trailing, encoding="utf-8")
    return 0

