#!/usr/bin/env python3
"""Summarize Phase 1 progress by control-loop stage."""

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


def build_control_loop_report(
    plan: dict[str, Any],
    baseline_summary: dict[str, Any],
    dashboard: dict[str, Any],
    weekly_pack: dict[str, Any],
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    plan_ok = bool(plan.get("current_phase", {}).get("id") == 1)
    checks.append(
        {
            "stage": "plan",
            "ok": plan_ok,
            "evidence": "current_phase.id == 1",
            "action_if_missing": "Run make phase-current-json and verify phase lock",
        }
    )

    build_ok = bool(baseline_summary)
    checks.append(
        {
            "stage": "build",
            "ok": build_ok,
            "evidence": "phase1-baseline-summary exists",
            "action_if_missing": "Run make phase1-baseline",
        }
    )

    validate_ok = bool(dashboard)
    checks.append(
        {
            "stage": "validate",
            "ok": validate_ok,
            "evidence": "phase1-completion-dashboard exists",
            "action_if_missing": "Run make phase1-dashboard",
        }
    )

    operationalize_ok = bool(weekly_pack)
    checks.append(
        {
            "stage": "operationalize",
            "ok": operationalize_ok,
            "evidence": "phase1-weekly-pack exists",
            "action_if_missing": "Run make phase1-weekly-pack",
        }
    )

    expand_ok = bool(dashboard.get("next_step"))
    checks.append(
        {
            "stage": "expand",
            "ok": expand_ok,
            "evidence": "next_step computed",
            "action_if_missing": "Run make phase1-next",
        }
    )

    passed = sum(1 for row in checks if row["ok"])
    next_actions = [row["action_if_missing"] for row in checks if not row["ok"]]

    return {
        "schema_version": "sdetkit.phase1_control_loop_report.v1",
        "generated_at": _utc_now(),
        "phase": "phase1",
        "stages": checks,
        "passed_stages": passed,
        "total_stages": len(checks),
        "completion_percent": round((passed / len(checks)) * 100, 1) if checks else 0,
        "ready_for_closeout": bool(dashboard.get("ready_to_close", False)),
        "next_actions": next_actions,
    }


def _to_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Phase 1 control loop report",
        "",
        f"- Generated at: {payload.get('generated_at', '')}",
        f"- Completion: {payload.get('completion_percent', 0)}%",
        f"- Ready for closeout: {payload.get('ready_for_closeout', False)}",
        "",
        "## Stage checks",
    ]
    stages = payload.get("stages", [])
    if isinstance(stages, list):
        for row in stages:
            if isinstance(row, dict):
                lines.append(f"- {row.get('stage')}: ok={row.get('ok')} ({row.get('evidence')})")

    lines.extend(["", "## Next actions"])
    actions = payload.get("next_actions", [])
    if isinstance(actions, list) and actions:
        lines.extend(f"- {item}" for item in actions)
    else:
        lines.append("- none")

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Phase 1 control loop report.")
    parser.add_argument("--plan", default="plans/strategic-execution-model-2026.json")
    parser.add_argument(
        "--baseline-summary", default="build/phase1-baseline/phase1-baseline-summary.json"
    )
    parser.add_argument(
        "--dashboard", default="build/phase1-baseline/phase1-completion-dashboard.json"
    )
    parser.add_argument(
        "--weekly-pack", default="build/phase1-baseline/weekly-pack/phase1-weekly-pack.json"
    )
    parser.add_argument(
        "--out-json", default="build/phase1-baseline/phase1-control-loop-report.json"
    )
    parser.add_argument("--out-md", default="build/phase1-baseline/phase1-control-loop-report.md")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    payload = build_control_loop_report(
        plan=_load_json(Path(args.plan)),
        baseline_summary=_load_json(Path(args.baseline_summary)),
        dashboard=_load_json(Path(args.dashboard)),
        weekly_pack=_load_json(Path(args.weekly_pack)),
    )

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out_md.write_text(_to_markdown(payload), encoding="utf-8")

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("phase1-control-loop-report: OK")
        print(f"- completion_percent: {payload.get('completion_percent', 0)}")
        print(f"- json: {out_json}")
        print(f"- markdown: {out_md}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
