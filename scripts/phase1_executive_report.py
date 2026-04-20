#!/usr/bin/env python3
"""Build a concise executive report for current Phase 1 status."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_report(
    finish: dict[str, Any],
    gate: dict[str, Any],
    blockers: dict[str, Any],
    telemetry: dict[str, Any],
) -> dict[str, Any]:
    rows = blockers.get("rows", []) if isinstance(blockers, dict) else []
    if not isinstance(rows, list):
        rows = []

    top_blockers = rows[:3]
    return {
        "schema_version": "sdetkit.phase1_executive_report.v1",
        "generated_at": _utc_now(),
        "status": finish.get("status", "unknown"),
        "ready_for_phase2": bool(gate.get("ready_for_phase2", False)),
        "completion_percent": float(finish.get("completion_percent", 0) or 0),
        "gate_next_step": gate.get("next_step", "make phase1-next"),
        "blocker_count": int(blockers.get("count", len(rows) if rows else 0) or 0),
        "top_blockers": top_blockers,
        "telemetry": {
            "runs": telemetry.get("runs", 0),
            "pass_rate": telemetry.get("pass_rate", 0),
            "avg_duration_ms": telemetry.get("avg_duration_ms", 0),
            "duration_drift_ms": telemetry.get("duration_drift_ms", 0),
        },
    }


def _to_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Phase 1 executive report",
        "",
        f"- Generated at: {payload.get('generated_at', '')}",
        f"- Status: {payload.get('status', 'unknown')}",
        f"- Completion: {payload.get('completion_percent', 0)}%",
        f"- Ready for Phase 2: {payload.get('ready_for_phase2', False)}",
        f"- Next step: {payload.get('gate_next_step', '')}",
        "",
        "## Telemetry",
    ]

    tele = payload.get("telemetry", {})
    lines.append(f"- runs: {tele.get('runs', 0)}")
    lines.append(f"- pass_rate: {tele.get('pass_rate', 0)}%")
    lines.append(f"- avg_duration_ms: {tele.get('avg_duration_ms', 0)}")
    lines.append(f"- duration_drift_ms: {tele.get('duration_drift_ms', 0)}")

    lines.extend(["", "## Top blockers"])
    blockers = payload.get("top_blockers", [])
    if isinstance(blockers, list) and blockers:
        for row in blockers:
            if isinstance(row, dict):
                lines.append(
                    f"- {row.get('blocker')}: priority={row.get('priority')} action={row.get('recommended_action')}"
                )
    else:
        lines.append("- none")

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Phase 1 executive report.")
    parser.add_argument("--finish", default="build/phase1-baseline/phase1-finish-signal.json")
    parser.add_argument("--gate", default="build/phase1-baseline/phase1-gate-phase2.json")
    parser.add_argument("--blockers", default="build/phase1-baseline/phase1-blocker-register.json")
    parser.add_argument(
        "--telemetry", default="build/phase1-baseline/phase1-telemetry-summary.json"
    )
    parser.add_argument("--out-json", default="build/phase1-baseline/phase1-executive-report.json")
    parser.add_argument("--out-md", default="build/phase1-baseline/phase1-executive-report.md")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    finish = _load_json(Path(args.finish))
    gate = _load_json(Path(args.gate))
    blockers = _load_json(Path(args.blockers))
    telemetry = _load_json(Path(args.telemetry))

    if not finish or not gate:
        payload = {
            "ok": False,
            "schema_version": "sdetkit.phase1_executive_report.v1",
            "reason": "missing finish or gate payload",
        }
        if args.format == "json":
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"phase1-executive-report: FAIL ({payload['reason']})")
        return 1

    report = build_report(finish, gate, blockers, telemetry)
    report["ok"] = True

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out_md.write_text(_to_markdown(report), encoding="utf-8")

    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"phase1-executive-report: {report.get('status', 'unknown')}")
        print(f"- ready_for_phase2: {report.get('ready_for_phase2', False)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
