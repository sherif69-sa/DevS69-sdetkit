from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.maintenance.action_plan.v1"

BLOCKED = "BLOCKED"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
DEFERRED = "DEFERRED"
ELIGIBLE_PENDING_POLICY = "ELIGIBLE_PENDING_POLICY"

REVIEW_FIRST = "REVIEW_FIRST"
CANDIDATE_LATER = "CANDIDATE_LATER"
AUTOMATION_READY = "AUTOMATION_READY"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _cell(value: Any) -> str:
    return _text(value).replace("|", "\\|")


def _read_json(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _future_auto_fix_candidate(item: dict[str, Any]) -> bool:
    eligibility = _text(item.get("eligibility"))
    readiness = _text(item.get("automation_readiness"))
    if eligibility == ELIGIBLE_PENDING_POLICY and readiness == AUTOMATION_READY:
        return True
    return eligibility == DEFERRED and readiness == CANDIDATE_LATER


def _action_for_item(item: dict[str, Any]) -> tuple[str, str]:
    eligibility = _text(item.get("eligibility"))
    required_gate = _text(item.get("required_gate"))

    if eligibility == BLOCKED:
        return (
            "Resolve the blocking condition before any maintenance automation is considered.",
            required_gate or "Resolve the blocker and rerun maintenance.",
        )
    if eligibility == REVIEW_REQUIRED:
        return (
            "Review this signal, attach the required proof, and keep automation disabled.",
            required_gate or "Attach review proof before considering automation policy changes.",
        )
    if eligibility == DEFERRED:
        return (
            "Keep observing this signal until repeated successful evidence exists.",
            required_gate or "Continue collecting history before automation policy changes.",
        )
    if eligibility == ELIGIBLE_PENDING_POLICY:
        return (
            "Prepare an explicit policy PR before enabling any auto-fix behavior.",
            required_gate or "Require a policy PR before enabling automation.",
        )
    return (
        "Review this signal before taking action.",
        required_gate or "Review the policy basis and attach proof.",
    )


def _auto_fix_blocker(item: dict[str, Any]) -> str:
    eligibility = _text(item.get("eligibility"))
    if eligibility == BLOCKED:
        return "Blocked by release or explicit non-eligibility gate."
    if eligibility == REVIEW_REQUIRED:
        return "Maintainer review proof is required before auto-fix."
    if eligibility == DEFERRED:
        return "More repeated successful evidence is required before auto-fix."
    if eligibility == ELIGIBLE_PENDING_POLICY:
        return "An explicit policy PR is required before auto-fix."
    return "Automation is disabled until the policy basis is reviewed."


def _plan_item(item: dict[str, Any]) -> dict[str, Any]:
    recommended_action, next_gate = _action_for_item(item)
    future_candidate = _future_auto_fix_candidate(item)
    return {
        "rank": item.get("rank", ""),
        "signal": _text(item.get("title")) or _text(item.get("memory_lookup_key")),
        "source": _text(item.get("source")),
        "memory_lookup_key": _text(item.get("memory_lookup_key")),
        "eligibility": _text(item.get("eligibility")) or REVIEW_REQUIRED,
        "automation_readiness": _text(item.get("automation_readiness")),
        "recommended_action": recommended_action,
        "proof_needed": _text(item.get("proof_needed")),
        "next_gate": next_gate,
        "future_auto_fix_candidate": future_candidate,
        "auto_fix_blocker": _auto_fix_blocker(item),
    }


def build_action_plan(eligibility_payload: dict[str, Any]) -> dict[str, Any]:
    items = [
        _plan_item(_as_dict(item))
        for item in _as_list(eligibility_payload.get("items"))
        if _as_dict(item)
    ]

    counts: dict[str, int] = {}
    for item in items:
        key = _text(item.get("eligibility")) or REVIEW_REQUIRED
        counts[key] = counts.get(key, 0) + 1

    candidate_count = sum(1 for item in items if bool(item.get("future_auto_fix_candidate")))
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": bool(eligibility_payload.get("ok", True)),
        "source_schema_version": _text(eligibility_payload.get("schema_version")),
        "source_next_gate": _text(eligibility_payload.get("next_gate")),
        "diagnostic_only": True,
        "automation_allowed": False,
        "auto_fix_enabled": False,
        "action_count": len(items),
        "future_auto_fix_candidate_count": candidate_count,
        "counts_by_eligibility": dict(sorted(counts.items())),
        "actions": items,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Maintenance action plan",
        "",
        f"- diagnostic only: **{payload.get('diagnostic_only', True)}**",
        f"- automation allowed: **{payload.get('automation_allowed', False)}**",
        f"- auto-fix enabled: **{payload.get('auto_fix_enabled', False)}**",
        f"- source next gate: **{payload.get('source_next_gate') or 'UNKNOWN'}**",
        f"- actions: **{payload.get('action_count', 0)}**",
        f"- future auto-fix candidates: **{payload.get('future_auto_fix_candidate_count', 0)}**",
    ]

    counts = _as_dict(payload.get("counts_by_eligibility"))
    if counts:
        lines.extend(["", "## Eligibility mix", ""])
        for name, count in sorted(counts.items()):
            lines.append(f"- **{_cell(name)}**: {count}")

    actions = _as_list(payload.get("actions"))
    if not actions:
        lines.extend(["", "No maintenance actions were planned."])
        return "\n".join(lines).rstrip() + "\n"

    lines.extend(
        [
            "",
            "## Action plan",
            "",
            "| Rank | Eligibility | Future auto-fix | Source | Signal | Next gate |",
            "|---:|---|---|---|---|---|",
        ]
    )
    for item in actions:
        row = _as_dict(item)
        lines.append(
            f"| {row.get('rank', '')} | {_cell(row.get('eligibility'))} | "
            f"{bool(row.get('future_auto_fix_candidate'))} | {_cell(row.get('source'))} | "
            f"{_cell(row.get('signal'))} | {_cell(row.get('next_gate'))} |"
        )

    lines.extend(["", "## What to do next", ""])
    for item in actions[:8]:
        row = _as_dict(item)
        lines.append(
            f"- **{_cell(row.get('signal'))}**: {_cell(row.get('recommended_action'))} "
            f"Proof: {_cell(row.get('proof_needed')) or 'None.'} "
            f"Auto-fix blocker: {_cell(row.get('auto_fix_blocker'))}"
        )

    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.maintenance_action_plan")
    parser.add_argument("--eligibility-json", required=True)
    parser.add_argument("--out-json")
    parser.add_argument("--out-md")
    parser.add_argument("--format", choices=["json", "md"], default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = build_action_plan(_read_json(args.eligibility_json) or {})
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    json_text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    md_text = render_markdown(payload)

    if args.out_json:
        Path(args.out_json).write_text(json_text, encoding="utf-8")
    if args.out_md:
        Path(args.out_md).write_text(md_text, encoding="utf-8")

    print(json_text if args.format == "json" else md_text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
