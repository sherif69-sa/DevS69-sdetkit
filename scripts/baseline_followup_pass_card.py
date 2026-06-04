#!/usr/bin/env python3
"""Generate a concise follow-up pass card for baseline remediation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_followup_pass_card(
    readiness_signal: dict[str, Any], next_actions: dict[str, Any], control_loop: dict[str, Any]
) -> dict[str, Any]:
    status = readiness_signal.get("status", "unknown")
    blockers = readiness_signal.get("blocking_required_checks", [])
    if not isinstance(blockers, list):
        blockers = []

    missing_stages = [
        row.get("stage")
        for row in control_loop.get("stages", [])
        if isinstance(row, dict) and not bool(row.get("ok", False))
    ]

    actions = next_actions.get("next_actions", []) if isinstance(next_actions, dict) else []
    if not isinstance(actions, list):
        actions = []

    if not actions:
        actions = [readiness_signal.get("next_step", "make baseline-next")]

    return {
        "schema_version": "sdetkit.baseline_followup_pass_card.v1",
        "status": status,
        "ready_to_close": bool(readiness_signal.get("ready_to_close", False)),
        "completion_percent": float(readiness_signal.get("completion_percent", 0) or 0),
        "blocking_required_checks": blockers,
        "missing_control_loop_stages": missing_stages,
        "next_actions": actions,
    }


def _to_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# baseline follow-up pass card",
        "",
        f"- Status: {payload.get('status', 'unknown')}",
        f"- Completion: {payload.get('completion_percent', 0)}%",
        f"- Ready to close: {payload.get('ready_to_close', False)}",
        "",
        "## Blocking required checks",
    ]

    blockers = payload.get("blocking_required_checks", [])
    if isinstance(blockers, list) and blockers:
        lines.extend(f"- {item}" for item in blockers)
    else:
        lines.append("- none")

    lines.extend(["", "## Missing control-loop stages"])
    stages = payload.get("missing_control_loop_stages", [])
    if isinstance(stages, list) and stages:
        lines.extend(f"- {item}" for item in stages)
    else:
        lines.append("- none")

    lines.extend(["", "## Next actions"])
    actions = payload.get("next_actions", [])
    if isinstance(actions, list) and actions:
        lines.extend(f"- {item}" for item in actions)
    else:
        lines.append("- none")

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build baseline follow-up pass remediation card.")
    parser.add_argument(
        "--readiness-signal", default="build/baseline/baseline-readiness-signal.json"
    )
    parser.add_argument("--next-actions", default="build/baseline/baseline-next-actions.json")
    parser.add_argument(
        "--control-loop", default="build/baseline/baseline-control-loop-report.json"
    )
    parser.add_argument("--out-json", default="build/baseline/baseline-followup-pass-card.json")
    parser.add_argument("--out-md", default="build/baseline/baseline-followup-pass-card.md")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    readiness_signal = _load_json(Path(args.readiness_signal))
    control_loop = _load_json(Path(args.control_loop))
    next_actions = _load_json(Path(args.next_actions))

    if not readiness_signal or not control_loop:
        payload = {
            "ok": False,
            "schema_version": "sdetkit.baseline_followup_pass_card.v1",
            "reason": "missing readiness signal or control-loop artifact",
        }
        if args.format == "json":
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"baseline-followup-pass-card: FAIL ({payload['reason']})")
        return 1

    card = build_followup_pass_card(readiness_signal, next_actions, control_loop)
    card["ok"] = True

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out_md.write_text(_to_markdown(card), encoding="utf-8")

    if args.format == "json":
        print(json.dumps(card, indent=2, sort_keys=True))
    else:
        print(f"baseline-followup-pass-card: {card.get('status', 'unknown')}")
        print(f"- json: {out_json}")
        print(f"- markdown: {out_md}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
