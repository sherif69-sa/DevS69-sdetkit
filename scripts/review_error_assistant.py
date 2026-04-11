from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sdetkit.review_engine import triage_error_log


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Analyze recurring CI/local errors and recommend real-world fixes.",
    )
    p.add_argument("--in", dest="in_path", default=None, help="Path to error log text. Defaults to stdin.")
    p.add_argument("--format", choices=("json", "text"), default="text")
    return p


def main(argv: list[str] | None = None) -> int:
    ns = _build_parser().parse_args(argv)
    if ns.in_path:
        text = Path(ns.in_path).read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()

    payload = triage_error_log(text)
    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return 0 if payload["summary"]["ok"] else 2

    if payload["summary"]["ok"]:
        sys.stdout.write("No known error patterns matched.\n")
        return 0

    sys.stdout.write("Detected error patterns and recommended fixes:\n")
    for row in payload["matched_rules"]:
        sys.stdout.write(f"- [{row['category']}] {row['id']}: {row['recommendation']}\n")
    return 2


if __name__ in {"__main__", "main_"}:
    raise SystemExit(main())
