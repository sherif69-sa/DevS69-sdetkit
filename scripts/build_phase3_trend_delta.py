#!/usr/bin/env python3
"""Build Phase 3 trend delta artifacts from baseline summaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.phase3_quality_engine import build_trend_delta, load_json


def _resolve_previous_summary(explicit: str | None, current: Path) -> Path | None:
    if explicit:
        return Path(explicit)
    history_dir = current.parent / "history"
    if not history_dir.is_dir():
        return None
    candidates = sorted(
        path for path in history_dir.glob("*.json") if path.is_file() and path.resolve() != current.resolve()
    )
    return candidates[-1] if candidates else None


def _to_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Phase 3 trend delta",
        "",
        f"- status: `{payload.get('status', 'unknown')}`",
        f"- current: `{payload.get('compared_artifacts', {}).get('current', '')}`",
        f"- previous: `{payload.get('compared_artifacts', {}).get('previous', '')}`",
        "",
        "## regressions",
    ]
    regressions = payload.get("regressions", [])
    lines.extend([f"- {item}" for item in regressions] or ["- none"])
    lines.extend(["", "## improvements"])
    improvements = payload.get("improvements", [])
    lines.extend([f"- {item}" for item in improvements] or ["- none"])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current", default="build/phase1-baseline/phase1-baseline-summary.json")
    parser.add_argument("--previous", default=None)
    parser.add_argument(
        "--out-json", default="build/phase3-quality/phase3-trend-delta.json", help="Trend delta JSON output path."
    )
    parser.add_argument(
        "--out-md", default="build/phase3-quality/phase3-trend-delta.md", help="Optional markdown companion output."
    )
    parser.add_argument("--skip-md", action="store_true")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    current_path = Path(args.current)
    current = load_json(current_path)
    if not current:
        payload = {"ok": False, "reason": f"missing current summary: {current_path}"}
        if args.format == "json":
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"phase3-trend-delta: FAIL ({payload['reason']})")
        return 1

    current["_source"] = str(current_path)
    previous_payload = None
    previous_path = _resolve_previous_summary(args.previous, current_path)
    if previous_path:
        previous_payload = load_json(previous_path)
        if previous_payload:
            previous_payload["_source"] = str(previous_path)

    trend = build_trend_delta(current, previous_payload)

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(trend, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not args.skip_md:
        out_md = Path(args.out_md)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(_to_markdown(trend), encoding="utf-8")

    if args.format == "json":
        print(json.dumps(trend, indent=2, sort_keys=True))
    else:
        print(f"phase3-trend-delta: {trend['status']}")
        print(f"- json: {out_json}")
        if not args.skip_md:
            print(f"- markdown: {args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
