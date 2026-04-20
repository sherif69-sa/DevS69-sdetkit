#!/usr/bin/env python3
"""Append Phase 1 run telemetry and compute drift metrics."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _duration_total_ms(run_payload: dict[str, Any]) -> int:
    total = 0
    for row in run_payload.get("steps", []):
        if isinstance(row, dict):
            total += int(row.get("duration_ms", 0) or 0)
    return total


def build_history_entry(run_payload: dict[str, Any]) -> dict[str, Any]:
    steps = run_payload.get("steps", []) if isinstance(run_payload, dict) else []
    if not isinstance(steps, list):
        steps = []
    failed = [row for row in steps if isinstance(row, dict) and not bool(row.get("ok", False))]
    blocker_categories = []
    for row in failed:
        cmd = str(row.get("command", ""))
        if "baseline" in cmd:
            blocker_categories.append("build")
        elif "dashboard" in cmd or "control-loop" in cmd:
            blocker_categories.append("validate")
        else:
            blocker_categories.append("other")

    return {
        "recorded_at": _utc_now(),
        "ok": bool(run_payload.get("ok", False)),
        "duration_ms": _duration_total_ms(run_payload),
        "steps_total": len(steps),
        "steps_failed": len(failed),
        "blocker_categories": sorted(set(blocker_categories)),
    }


def summarize(history: list[dict[str, Any]]) -> dict[str, Any]:
    if not history:
        return {
            "runs": 0,
            "pass_rate": 0,
            "avg_duration_ms": 0,
            "last_duration_ms": 0,
            "duration_drift_ms": 0,
            "blocker_category_counts": {},
        }

    runs = len(history)
    pass_count = sum(1 for row in history if bool(row.get("ok", False)))
    avg_duration = int(sum(int(row.get("duration_ms", 0)) for row in history) / runs)
    last_duration = int(history[-1].get("duration_ms", 0))
    previous = int(history[-2].get("duration_ms", 0)) if runs > 1 else last_duration
    drift = last_duration - previous

    counts: dict[str, int] = {}
    for row in history:
        for cat in row.get("blocker_categories", []):
            counts[cat] = counts.get(cat, 0) + 1

    return {
        "runs": runs,
        "pass_rate": round((pass_count / runs) * 100, 1),
        "avg_duration_ms": avg_duration,
        "last_duration_ms": last_duration,
        "duration_drift_ms": drift,
        "blocker_category_counts": counts,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Update Phase 1 telemetry history.")
    parser.add_argument("--run-json", default="build/phase1-baseline/phase1-run-all.json")
    parser.add_argument(
        "--history-json", default="build/phase1-baseline/phase1-telemetry-history.json"
    )
    parser.add_argument(
        "--summary-json", default="build/phase1-baseline/phase1-telemetry-summary.json"
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    run_payload = _load_json(Path(args.run_json), {})
    if not run_payload:
        result = {
            "ok": False,
            "schema_version": "sdetkit.phase1_telemetry_history.v1",
            "reason": f"missing run payload: {args.run_json}",
        }
        if args.format == "json":
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(f"phase1-telemetry-history: FAIL ({result['reason']})")
        return 1

    history_path = Path(args.history_json)
    history = _load_json(history_path, [])
    if not isinstance(history, list):
        history = []

    history.append(build_history_entry(run_payload))
    summary = summarize(history)

    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(json.dumps(history, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary_payload = {
        "schema_version": "sdetkit.phase1_telemetry_summary.v1",
        "generated_at": _utc_now(),
        **summary,
    }
    summary_path = Path(args.summary_json)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    if args.format == "json":
        print(json.dumps(summary_payload, indent=2, sort_keys=True))
    else:
        print("phase1-telemetry-history: OK")
        print(f"- runs: {summary_payload['runs']}")
        print(f"- pass_rate: {summary_payload['pass_rate']}%")
        print(f"- avg_duration_ms: {summary_payload['avg_duration_ms']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
