from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.maintenance.recommendation_eligibility.v1"

BLOCKED = "BLOCKED"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
DEFERRED = "DEFERRED"
ELIGIBLE_PENDING_POLICY = "ELIGIBLE_PENDING_POLICY"

BLOCK_RELEASE = "BLOCK_RELEASE"
BLOCK_RELEASE_REVIEW = "BLOCK_RELEASE_REVIEW"
NOT_ELIGIBLE = "NOT_ELIGIBLE"
REVIEW_FIRST = "REVIEW_FIRST"
OBSERVE_ONLY = "OBSERVE_ONLY"
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


def _eligibility_for_item(item: dict[str, Any], release_blocking: bool) -> dict[str, Any]:
    recommendation = _text(item.get("recommendation"))
    decision = _text(item.get("decision"))
    readiness = _text(item.get("automation_readiness"))
    row_allowed = bool(item.get("automation_allowed", False))
    row_eligible = bool(item.get("automation_eligible", False))

    if release_blocking or decision == BLOCK_RELEASE or recommendation == BLOCK_RELEASE_REVIEW:
        eligibility = BLOCKED
        reason = "Release-blocking or release-review recommendations cannot enter automation."
        gate = "Resolve or explicitly review the release-blocking signal first."
    elif readiness == NOT_ELIGIBLE:
        eligibility = BLOCKED
        reason = "The recommendation is explicitly marked not eligible for automation."
        gate = "Keep this item out of automation policy."
    elif decision == REVIEW_REQUIRED or readiness == REVIEW_FIRST:
        eligibility = REVIEW_REQUIRED
        reason = "The recommendation requires maintainer review before any policy change."
        gate = "Attach review proof before considering automation policy changes."
    elif readiness in {OBSERVE_ONLY, CANDIDATE_LATER}:
        eligibility = DEFERRED
        reason = "The recommendation needs more history before automation can be considered."
        gate = "Continue observing repeated successful evidence."
    elif row_allowed and row_eligible and readiness == AUTOMATION_READY:
        eligibility = ELIGIBLE_PENDING_POLICY
        reason = "The recommendation reports automation-ready signals, but this report is diagnostic only."
        gate = "Require an explicit policy PR before enabling automation."
    else:
        eligibility = REVIEW_REQUIRED
        reason = "The recommendation does not carry enough evidence for automation."
        gate = "Review the policy basis and attach proof."

    return {
        "rank": item.get("rank", ""),
        "recommendation": recommendation,
        "decision": decision,
        "source": _text(item.get("source")),
        "title": _text(item.get("title")),
        "memory_lookup_key": _text(item.get("memory_lookup_key")),
        "automation_readiness": readiness,
        "automation_allowed": row_allowed,
        "automation_eligible": row_eligible,
        "eligibility": eligibility,
        "reason": reason,
        "required_gate": gate,
        "proof_needed": _text(item.get("proof_needed")),
    }


def build_eligibility_report(recommendations_payload: dict[str, Any]) -> dict[str, Any]:
    release_blocking = bool(recommendations_payload.get("release_blocking", False))
    items = [
        _eligibility_for_item(_as_dict(item), release_blocking)
        for item in _as_list(recommendations_payload.get("recommendations"))
        if _as_dict(item)
    ]

    counts: dict[str, int] = {}
    for item in items:
        eligibility = _text(item.get("eligibility")) or REVIEW_REQUIRED
        counts[eligibility] = counts.get(eligibility, 0) + 1

    if counts.get(BLOCKED, 0):
        next_gate = "BLOCKED_REVIEW"
    elif counts.get(REVIEW_REQUIRED, 0):
        next_gate = "MAINTAINER_REVIEW"
    elif counts.get(ELIGIBLE_PENDING_POLICY, 0):
        next_gate = "POLICY_PR_REQUIRED"
    else:
        next_gate = "OBSERVE"

    return {
        "schema_version": SCHEMA_VERSION,
        "ok": bool(recommendations_payload.get("ok", True)),
        "source_schema_version": _text(recommendations_payload.get("schema_version")),
        "source_decision": _text(recommendations_payload.get("decision")),
        "release_blocking": release_blocking,
        "automation_allowed": False,
        "diagnostic_only": True,
        "recommendation_count": len(items),
        "counts_by_eligibility": dict(sorted(counts.items())),
        "next_gate": next_gate,
        "items": items,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Maintenance recommendation eligibility",
        "",
        f"- diagnostic only: **{payload.get('diagnostic_only', True)}**",
        f"- automation allowed: **{payload.get('automation_allowed', False)}**",
        f"- source decision: **{payload.get('source_decision') or 'UNKNOWN'}**",
        f"- release blocking: **{payload.get('release_blocking', False)}**",
        f"- recommendations checked: **{payload.get('recommendation_count', 0)}**",
        f"- next gate: **{payload.get('next_gate') or 'OBSERVE'}**",
    ]

    counts = _as_dict(payload.get("counts_by_eligibility"))
    if counts:
        lines.extend(["", "## Counts", ""])
        for name, count in sorted(counts.items()):
            lines.append(f"- **{_cell(name)}**: {count}")

    items = _as_list(payload.get("items"))
    if not items:
        lines.extend(["", "No recommendation eligibility items were produced."])
        return "\n".join(lines).rstrip() + "\n"

    lines.extend(
        [
            "",
            "## Eligibility details",
            "",
            "| Rank | Eligibility | Recommendation | Readiness | Source | Required gate |",
            "|---:|---|---|---|---|---|",
        ]
    )

    for item in items:
        row = _as_dict(item)
        lines.append(
            f"| {row.get('rank', '')} | {_cell(row.get('eligibility'))} | "
            f"{_cell(row.get('recommendation'))} | "
            f"{_cell(row.get('automation_readiness'))} | "
            f"{_cell(row.get('source'))} | {_cell(row.get('required_gate'))} |"
        )

    lines.extend(["", "## Why blocked, deferred, or review-first", ""])
    for item in items[:8]:
        row = _as_dict(item)
        lines.append(
            f"- **{_cell(row.get('eligibility'))}** `{_cell(row.get('memory_lookup_key'))}`: "
            f"{_cell(row.get('reason'))} Proof: {_cell(row.get('proof_needed')) or 'None.'}"
        )

    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sdetkit.maintenance_recommendation_eligibility"
    )
    parser.add_argument("--recommendations-json", required=True)
    parser.add_argument("--out-json")
    parser.add_argument("--out-md")
    parser.add_argument("--format", choices=["json", "md"], default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = build_eligibility_report(_read_json(args.recommendations_json) or {})
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
