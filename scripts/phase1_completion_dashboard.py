#!/usr/bin/env python3
"""Build a single readiness dashboard for Phase 1 completion."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_CHECKS = ["doctor", "enterprise_contracts", "primary_docs_map"]
ALLOW_FAIL = {"ruff", "pytest", "gate_fast", "gate_release"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _sequential_summary(plan_path: Path, status_path: Path) -> dict[str, Any]:
    plan = _load_json(plan_path)
    status = _load_json(status_path)
    current = plan.get("current_phase", {}) if isinstance(plan, dict) else {}
    progress = {
        "available": bool(status),
        "status_file": str(status_path),
        "phase1_ok": bool(status.get("ok", False)) if isinstance(status, dict) else False,
        "accomplished_count": len(status.get("accomplished", []))
        if isinstance(status.get("accomplished", []), list)
        else 0,
        "remaining_count": len(status.get("not_yet", []))
        if isinstance(status.get("not_yet", []), list)
        else 0,
        "hard_blockers": status.get("hard_blockers", []) if isinstance(status, dict) else [],
    }
    total = progress["accomplished_count"] + progress["remaining_count"]
    progress["progress_percent"] = round((progress["accomplished_count"] / total) * 100, 1) if total else 0
    return {
        "ok": bool(plan),
        "schema_version": "sdetkit.phase_sequential_executor.v1",
        "plan_id": plan.get("plan_id"),
        "current_phase": current,
        "control_loop": plan.get("control_loop", []),
        "phase_handoff_rule": plan.get("phase_handoff_rule", ""),
        "next_commands": current.get("now_actions", []) if isinstance(current, dict) else [],
        "progress": progress,
    }


def _completion_gate(summary: dict[str, Any]) -> dict[str, Any]:
    rows = summary.get("checks", []) if isinstance(summary, dict) else []
    if not isinstance(rows, list):
        rows = []

    by_id: dict[str, bool] = {}
    for row in rows:
        if isinstance(row, dict):
            cid = str(row.get("id", "")).strip()
            if cid:
                by_id[cid] = bool(row.get("ok", False))

    failing_required = [cid for cid in REQUIRED_CHECKS if not by_id.get(cid, False)]
    missing_required = [cid for cid in REQUIRED_CHECKS if cid not in by_id]
    blocked_nonrequired = [
        cid
        for cid, ok in by_id.items()
        if not ok and cid not in REQUIRED_CHECKS and cid not in ALLOW_FAIL
    ]

    ok = not failing_required and not missing_required and not blocked_nonrequired
    return {
        "ok": ok,
        "required_checks": REQUIRED_CHECKS,
        "allow_fail": sorted(ALLOW_FAIL),
        "failing_required_checks": failing_required,
        "missing_required_checks": missing_required,
        "blocked_nonrequired_checks": sorted(blocked_nonrequired),
    }


def build_dashboard(
    plan_path: Path,
    status_path: Path,
    summary_path: Path,
    snapshot_path: Path,
) -> dict[str, Any]:
    sequential = _sequential_summary(plan_path=plan_path, status_path=status_path)
    status = _load_json(status_path)
    summary = _load_json(summary_path)
    snapshot = _load_json(snapshot_path)
    gate = _completion_gate(summary)

    hard_blockers = status.get("hard_blockers", []) if isinstance(status, dict) else []
    if not isinstance(hard_blockers, list):
        hard_blockers = []

    remaining = status.get("not_yet", []) if isinstance(status, dict) else []
    if not isinstance(remaining, list):
        remaining = []

    ready = bool(gate.get("ok", False)) and len(hard_blockers) == 0

    return {
        "schema_version": "sdetkit.phase1_completion_dashboard.v1",
        "generated_at": _utc_now(),
        "phase": "phase1",
        "ready_to_close": ready,
        "sequential": sequential,
        "status": {
            "ok": bool(status.get("ok", False)),
            "accomplished": status.get("accomplished", []),
            "not_yet": remaining,
            "hard_blockers": hard_blockers,
        },
        "completion_gate": gate,
        "ops_snapshot": {
            "progress_percent": snapshot.get("progress_percent", 0),
            "top_risk_item": snapshot.get("top_risk_item"),
            "recommended_next_actions": snapshot.get("recommended_next_actions", []),
        },
        "next_step": "make phase1-closeout" if ready else "make phase1-next && make phase1-ops-snapshot",
    }


def _to_markdown(payload: dict[str, Any]) -> str:
    status = payload.get("status", {})
    gate = payload.get("completion_gate", {})
    ops = payload.get("ops_snapshot", {})

    lines = [
        "# Phase 1 completion dashboard",
        "",
        f"- Generated at: {payload.get('generated_at', '')}",
        f"- Ready to close: {payload.get('ready_to_close', False)}",
        f"- Progress: {ops.get('progress_percent', 0)}%",
        f"- Next step: {payload.get('next_step', '')}",
        "",
        "## Hard blockers",
    ]

    blockers = status.get("hard_blockers", [])
    if isinstance(blockers, list) and blockers:
        lines.extend(f"- {item}" for item in blockers)
    else:
        lines.append("- none")

    lines.extend(["", "## Completion gate"])
    lines.append(f"- gate_ok: {gate.get('ok', False)}")
    for key in ("failing_required_checks", "missing_required_checks", "blocked_nonrequired_checks"):
        vals = gate.get(key, [])
        if isinstance(vals, list) and vals:
            lines.append(f"- {key}: {', '.join(vals)}")
        else:
            lines.append(f"- {key}: none")

    lines.extend(["", "## Top risk item"])
    top_risk = ops.get("top_risk_item")
    if isinstance(top_risk, dict) and top_risk:
        lines.append(
            f"- {top_risk.get('check_id')}: risk={top_risk.get('risk_score')} impact={top_risk.get('impact')}"
        )
    else:
        lines.append("- none")

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Phase 1 completion dashboard.")
    parser.add_argument("--plan", default="plans/strategic-execution-model-2026.json")
    parser.add_argument("--status", default="build/phase1-baseline/phase1-status.json")
    parser.add_argument("--summary", default="build/phase1-baseline/phase1-baseline-summary.json")
    parser.add_argument("--snapshot", default="build/phase1-baseline/phase1-ops-snapshot.json")
    parser.add_argument("--out-json", default="build/phase1-baseline/phase1-completion-dashboard.json")
    parser.add_argument("--out-md", default="build/phase1-baseline/phase1-completion-dashboard.md")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    payload = build_dashboard(
        plan_path=Path(args.plan),
        status_path=Path(args.status),
        summary_path=Path(args.summary),
        snapshot_path=Path(args.snapshot),
    )

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out_md.write_text(_to_markdown(payload), encoding="utf-8")

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("phase1-completion-dashboard: OK")
        print(f"- ready_to_close: {payload.get('ready_to_close', False)}")
        print(f"- json: {out_json}")
        print(f"- markdown: {out_md}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
