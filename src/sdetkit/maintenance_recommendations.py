from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.maintenance.recommendations.v1"

BLOCK_RELEASE = "BLOCK_RELEASE"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
TRACK_ONLY = "TRACK_ONLY"
NO_ACTION = "NO_ACTION"

NOT_ELIGIBLE = "NOT_ELIGIBLE"
REVIEW_FIRST = "REVIEW_FIRST"
OBSERVE_ONLY = "OBSERVE_ONLY"
CANDIDATE_LATER = "CANDIDATE_LATER"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


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


def _history_seen(decision: dict[str, Any]) -> int:
    return _as_int(_as_dict(decision.get("history_context")).get("seen_count"))


def _safe_fix_attempts(decision: dict[str, Any]) -> tuple[int, int]:
    context = _as_dict(decision.get("safe_fix_context"))
    return (
        _as_int(context.get("remediation_attempts")),
        _as_int(context.get("remediation_successes")),
    )


def _source_key(decision: dict[str, Any]) -> str:
    return (
        _text(decision.get("memory_lookup_key"))
        or _text(decision.get("source_key"))
        or f"{_text(decision.get('source'))}:{_text(decision.get('title'))}"
    )


def _context_hint(decision: dict[str, Any]) -> str:
    hints = []
    for name in ("history_context", "safe_fix_context", "annotation_context"):
        context = _as_dict(decision.get(name))
        hint = _text(context.get("policy_hint"))
        if hint:
            hints.append(hint)
    return " ".join(hints)


def _recommend_for_decision(decision: dict[str, Any]) -> dict[str, Any]:
    policy_decision = _text(decision.get("decision")) or REVIEW_REQUIRED
    source = _text(decision.get("source")) or "unknown"
    title = _text(decision.get("title")) or "Untitled maintenance signal"
    key = _source_key(decision)
    seen = _history_seen(decision)
    attempts, successes = _safe_fix_attempts(decision)
    context_hint = _context_hint(decision)
    release_risk = _text(decision.get("release_risk")).lower()
    automation_risk = _text(decision.get("automation_risk")).lower()

    base = {
        "rank": _as_int(decision.get("rank")),
        "decision": policy_decision,
        "source": source,
        "severity": _text(decision.get("severity")) or "unknown",
        "title": title,
        "memory_lookup_key": key,
        "automation_allowed": False,
        "automation_eligible": False,
        "observed_seen_count": seen,
        "observed_safe_fix_attempts": attempts,
        "observed_safe_fix_successes": successes,
        "policy_hint": context_hint,
    }

    if policy_decision == BLOCK_RELEASE or release_risk == "high":
        return {
            **base,
            "recommendation": "BLOCK_RELEASE_REVIEW",
            "recommended_next_action": (
                "Keep this release-blocking until the failing maintenance signal is reviewed or fixed."
            ),
            "why_now": (
                f"`{title}` is in the release-blocking lane. Do not treat this as routine hygiene."
            ),
            "proof_needed": "Run the failing maintenance check and attach the passing proof before release.",
            "automation_readiness": NOT_ELIGIBLE,
            "review_owner_hint": "release-maintainer",
            "escalation_reason": "Release risk is high.",
        }

    if source == "safe_fix_rollup":
        if attempts and successes < attempts:
            return {
                **base,
                "recommendation": "REVIEW_SAFE_FIX_OUTCOMES",
                "recommended_next_action": (
                    "Review the failed or incomplete safe-fix outcomes before widening automation."
                ),
                "why_now": (
                    f"Safe-fix memory shows {successes}/{attempts} successful remediation outcomes."
                ),
                "proof_needed": (
                    "Collect repeated successful remediation, verification, and commit outcomes "
                    "before changing auto-fix policy."
                ),
                "automation_readiness": REVIEW_FIRST,
                "review_owner_hint": "automation-maintainer",
                "escalation_reason": "Safe-fix history is not consistently successful.",
            }
        return {
            **base,
            "recommendation": "OBSERVE_SAFE_FIX_STABILITY",
            "recommended_next_action": (
                "Keep observing this safe-fix class and require more successful history before automation."
            ),
            "why_now": (
                f"Safe-fix memory has {successes}/{attempts} successful remediation outcomes."
            ),
            "proof_needed": "Require more repeated successful runs before marking automation-ready.",
            "automation_readiness": CANDIDATE_LATER,
            "review_owner_hint": "automation-maintainer",
            "escalation_reason": "",
        }

    if source == "annotation_hygiene":
        if seen >= 3:
            return {
                **base,
                "recommendation": "OPEN_WORKFLOW_HYGIENE_FOLLOWUP",
                "recommended_next_action": (
                    "Open or update a workflow-hygiene follow-up because this annotation keeps recurring."
                ),
                "why_now": (
                    f"`{title}` has appeared {seen} time(s) in policy history. "
                    "It is still hygiene, but recurrence makes it worth tracking explicitly."
                ),
                "proof_needed": (
                    "Confirm whether the warning comes from repo-owned workflow code, a pinned action, "
                    "or GitHub-managed infrastructure."
                ),
                "automation_readiness": OBSERVE_ONLY,
                "review_owner_hint": "workflow-maintainer",
                "escalation_reason": "Repeated annotation hygiene signal.",
            }
        return {
            **base,
            "recommendation": "TRACK_WORKFLOW_HYGIENE",
            "recommended_next_action": "Track this as workflow hygiene and avoid product-code changes.",
            "why_now": (
                f"`{title}` is an annotation hygiene signal, not a proven product-code failure."
            ),
            "proof_needed": "Confirm the owning workflow/action before changing code or policy.",
            "automation_readiness": OBSERVE_ONLY,
            "review_owner_hint": "workflow-maintainer",
            "escalation_reason": "",
        }

    if policy_decision == REVIEW_REQUIRED:
        return {
            **base,
            "recommendation": "MANUAL_REVIEW_REQUIRED",
            "recommended_next_action": "Route this item to maintainer review with the recorded policy basis.",
            "why_now": f"`{title}` is review-first and should not be automated from this signal alone.",
            "proof_needed": "Attach the relevant check output, policy basis, and passing proof after review.",
            "automation_readiness": REVIEW_FIRST if automation_risk != "low" else CANDIDATE_LATER,
            "review_owner_hint": "maintainer",
            "escalation_reason": "Policy lane requires human review.",
        }

    if policy_decision == TRACK_ONLY:
        return {
            **base,
            "recommendation": "CONTINUE_TRACKING",
            "recommended_next_action": "Keep tracking this signal and use future history to decide escalation.",
            "why_now": f"`{title}` is track-only based on current policy and memory context.",
            "proof_needed": "No immediate proof required; retain history for trend detection.",
            "automation_readiness": OBSERVE_ONLY,
            "review_owner_hint": "maintainer",
            "escalation_reason": "",
        }

    return {
        **base,
        "recommendation": "NO_ACTION_REQUIRED",
        "recommended_next_action": "No maintenance action is required from current policy context.",
        "why_now": "No actionable policy decision was present.",
        "proof_needed": "None.",
        "automation_readiness": OBSERVE_ONLY,
        "review_owner_hint": "none",
        "escalation_reason": "",
    }


def build_recommendations(memory_context: dict[str, Any]) -> dict[str, Any]:
    recommendations = [
        _recommend_for_decision(row)
        for row in _as_list(memory_context.get("decisions"))
        if _as_dict(row)
    ]

    if not recommendations and _text(memory_context.get("decision")) == NO_ACTION:
        recommendations = [
            {
                "rank": 1,
                "decision": NO_ACTION,
                "source": "maintenance_policy",
                "severity": "info",
                "title": "No maintenance policy action required",
                "memory_lookup_key": "",
                "recommendation": "NO_ACTION_REQUIRED",
                "recommended_next_action": "No maintenance action is required.",
                "why_now": "The policy decision set is empty and non-blocking.",
                "proof_needed": "None.",
                "automation_readiness": OBSERVE_ONLY,
                "automation_allowed": False,
                "automation_eligible": False,
                "review_owner_hint": "none",
                "escalation_reason": "",
                "observed_seen_count": 0,
                "observed_safe_fix_attempts": 0,
                "observed_safe_fix_successes": 0,
                "policy_hint": "",
            }
        ]

    counts: dict[str, int] = {}
    for item in recommendations:
        name = _text(item.get("recommendation")) or "UNKNOWN"
        counts[name] = counts.get(name, 0) + 1

    top = recommendations[0] if recommendations else {}
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": memory_context.get("ok", True),
        "decision": memory_context.get("decision", NO_ACTION),
        "release_blocking": bool(memory_context.get("release_blocking", False)),
        "automation_allowed": False,
        "recommendation_count": len(recommendations),
        "counts_by_recommendation": dict(sorted(counts.items())),
        "top_recommendation": _text(top.get("recommendation")),
        "top_next_action": _text(top.get("recommended_next_action")),
        "top_proof_needed": _text(top.get("proof_needed")),
        "recommendations": recommendations,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Adaptive maintenance recommendations",
        "",
        f"- overall decision: **{payload.get('decision', NO_ACTION)}**",
        f"- release blocking: **{payload.get('release_blocking', False)}**",
        f"- automation allowed: **{payload.get('automation_allowed', False)}**",
        f"- recommendations: **{payload.get('recommendation_count', 0)}**",
        f"- top recommendation: **{payload.get('top_recommendation') or 'none'}**",
        f"- top action: {payload.get('top_next_action') or 'No action required.'}",
        f"- top proof needed: {payload.get('top_proof_needed') or 'None.'}",
    ]

    recs = _as_list(payload.get("recommendations"))
    if not recs:
        lines.extend(["", "No adaptive maintenance recommendations were produced."])
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            "",
            "| Rank | Recommendation | Decision | Source | Readiness | Owner | Action |",
            "|---:|---|---|---|---|---|---|",
        ]
    )
    for item in recs:
        row = _as_dict(item)
        lines.append(
            f"| {row.get('rank', '')} | {_cell(row.get('recommendation'))} | "
            f"{_cell(row.get('decision'))} | {_cell(row.get('source'))} | "
            f"{_cell(row.get('automation_readiness'))} | "
            f"{_cell(row.get('review_owner_hint'))} | "
            f"{_cell(row.get('recommended_next_action'))} |"
        )

    lines.extend(["", "## Why now / proof needed", ""])
    for item in recs[:8]:
        row = _as_dict(item)
        lines.append(
            f"- **{_cell(row.get('recommendation'))}** `{_cell(row.get('memory_lookup_key'))}`: "
            f"{_cell(row.get('why_now'))} Proof: {_cell(row.get('proof_needed'))}"
        )

    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.maintenance_recommendations")
    parser.add_argument("--memory-context-json", required=True)
    parser.add_argument("--out-json")
    parser.add_argument("--out-md")
    parser.add_argument("--format", choices=["json", "md"], default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = build_recommendations(_read_json(args.memory_context_json) or {})
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
    return 1 if payload.get("release_blocking", False) else 0


if __name__ == "__main__":
    raise SystemExit(main())
