from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.maintenance.policy_decisions.v1"

BLOCK_RELEASE = "BLOCK_RELEASE"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
TRACK_ONLY = "TRACK_ONLY"
NO_ACTION = "NO_ACTION"

_DECISION_ORDER = {
    BLOCK_RELEASE: 0,
    REVIEW_REQUIRED: 1,
    TRACK_ONLY: 2,
    NO_ACTION: 3,
}


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


def _source_location(source_key: str) -> str:
    parts = [part for part in source_key.split(":") if part]
    return parts[-1] if parts else "unknown"


def _policy_basis(item: dict[str, Any]) -> list[str]:
    basis = [
        f"source={_text(item.get('source')) or 'unknown'}",
        f"priority={_as_int(item.get('priority'))}",
        f"severity={_text(item.get('severity')) or 'unknown'}",
    ]
    source_key = _text(item.get("key"))
    if source_key:
        basis.append(f"key={source_key}")
    title = _text(item.get("title"))
    if title:
        basis.append(f"title={title}")
    action = _text(item.get("action"))
    if action:
        basis.append(f"action={action}")
    return basis


def _risk_profile(
    *,
    decision: str,
    source: str,
    priority: int,
    severity: str,
) -> dict[str, str]:
    if decision == BLOCK_RELEASE:
        return {
            "confidence": "high",
            "automation_risk": "high",
            "review_risk": "high",
            "release_risk": "high",
        }

    if source == "safe_fix_rollup":
        return {
            "confidence": "high",
            "automation_risk": "high",
            "review_risk": "medium",
            "release_risk": "medium" if priority <= 2 else "low",
        }

    if source == "annotation_hygiene":
        return {
            "confidence": "medium",
            "automation_risk": "high",
            "review_risk": "low",
            "release_risk": "low" if severity in {"warning", "notice", "info"} else "medium",
        }

    if decision == REVIEW_REQUIRED:
        return {
            "confidence": "medium",
            "automation_risk": "medium",
            "review_risk": "medium",
            "release_risk": "medium" if priority <= 2 else "low",
        }

    return {
        "confidence": "medium",
        "automation_risk": "low",
        "review_risk": "low",
        "release_risk": "low",
    }


def _decision_for_item(item: dict[str, Any]) -> dict[str, str]:
    priority = _as_int(item.get("priority"))
    source = _text(item.get("source"))
    severity = _text(item.get("severity")).lower()
    title = _text(item.get("title"))
    action = _text(item.get("action"))
    reason = _text(item.get("reason"))
    source_key = _text(item.get("key"))
    location = _source_location(source_key)

    if priority <= 1 and source == "maintenance":
        return {
            "decision": BLOCK_RELEASE,
            "reason": reason or "Priority-1 maintenance failure was reported.",
            "adaptive_context": (
                f"`{title or source}` is a priority-1 maintenance signal. "
                "Treat it as release-blocking until the failing check is reviewed or fixed."
            ),
        }

    if source == "safe_fix_rollup" and priority <= 2:
        return {
            "decision": REVIEW_REQUIRED,
            "reason": reason or "Safe-fix learning shows a failed or incomplete remediation path.",
            "adaptive_context": (
                f"`{title or source}` came from safe-fix outcome history. "
                "Keep this review-first and do not widen automation policy until the recorded "
                "remediation pattern is consistently successful."
            ),
        }

    if source == "annotation_hygiene" and severity == "warning":
        return {
            "decision": TRACK_ONLY,
            "reason": reason or "Workflow annotation hygiene warning was reported.",
            "adaptive_context": (
                f"`{title or source}` appeared for `{location}`. Track it as CI/workflow hygiene "
                "and preserve product-code behavior; this signal does not justify expanding auto-fix policy."
            ),
        }

    if source == "maintenance_action":
        return {
            "decision": REVIEW_REQUIRED,
            "reason": reason or "Maintenance suggested an explicit follow-up action.",
            "adaptive_context": (
                f"The maintenance queue suggested `{action or title}`. "
                "Route it to maintainer review before making automation or release-policy changes."
            ),
        }

    if priority <= 2:
        return {
            "decision": REVIEW_REQUIRED,
            "reason": reason or f"Priority-{priority} maintenance signal was reported.",
            "adaptive_context": (
                f"`{title or source or 'maintenance signal'}` is high-priority. "
                "Require maintainer review before policy or automation changes."
            ),
        }

    if severity in {"notice", "info"} or priority >= 3:
        return {
            "decision": TRACK_ONLY,
            "reason": reason or "Lower-priority or informational maintenance signal was reported.",
            "adaptive_context": (
                f"`{title or source or 'maintenance signal'}` is lower-priority. "
                "Track it for trend/history and avoid turning it into a release block."
            ),
        }

    return {
        "decision": REVIEW_REQUIRED,
        "reason": reason or f"Maintenance signal `{title or source or 'unknown'}` needs review.",
        "adaptive_context": (
            f"`{title or source or 'unknown'}` did not match a narrower policy lane. "
            "Default to human review instead of fixed automation."
        ),
    }


def _overall_decision(decisions: list[dict[str, Any]]) -> str:
    if not decisions:
        return NO_ACTION
    return min(
        (_text(item.get("decision")) or TRACK_ONLY for item in decisions),
        key=lambda decision: _DECISION_ORDER.get(decision, 99),
    )


def build_policy_decisions(priority_rollup: dict[str, Any]) -> dict[str, Any]:
    decisions: list[dict[str, Any]] = []

    for item in _as_list(priority_rollup.get("priority_queue")):
        row = _as_dict(item)
        if not row:
            continue

        policy = _decision_for_item(row)
        decision = _text(policy.get("decision")) or REVIEW_REQUIRED
        priority = _as_int(row.get("priority"))
        source = _text(row.get("source")) or "unknown"
        severity = _text(row.get("severity")) or "unknown"
        risks = _risk_profile(
            decision=decision,
            source=source,
            priority=priority,
            severity=severity.lower(),
        )
        source_key = _text(row.get("key"))

        decisions.append(
            {
                "rank": _as_int(row.get("rank")) or len(decisions) + 1,
                "decision": decision,
                "priority": priority,
                "source": source,
                "severity": severity,
                "title": _text(row.get("title")) or "Untitled maintenance signal",
                "action": _text(row.get("action")),
                "reason": _text(policy.get("reason")),
                "adaptive_context": _text(policy.get("adaptive_context")),
                "policy_basis": _policy_basis(row),
                "source_key": source_key,
                "memory_lookup_key": source_key or f"{source}:{_text(row.get('title'))}",
                "observed_priority": priority,
                "observed_source": source,
                "observed_severity": severity,
                "observed_title": _text(row.get("title")),
                "observed_action": _text(row.get("action")),
                "observed_reason": _text(row.get("reason")),
                "automation_allowed": False,
                **risks,
            }
        )

    counts_by_decision: dict[str, int] = {}
    counts_by_source: dict[str, int] = {}
    for item in decisions:
        decision = _text(item.get("decision")) or TRACK_ONLY
        source = _text(item.get("source")) or "unknown"
        counts_by_decision[decision] = counts_by_decision.get(decision, 0) + 1
        counts_by_source[source] = counts_by_source.get(source, 0) + 1

    overall = _overall_decision(decisions)
    top = decisions[0] if decisions else {}

    return {
        "schema_version": SCHEMA_VERSION,
        "ok": overall != BLOCK_RELEASE,
        "decision": overall,
        "release_blocking": overall == BLOCK_RELEASE,
        "automation_allowed": False,
        "adaptive_ready": True,
        "decision_count": len(decisions),
        "counts_by_decision": dict(sorted(counts_by_decision.items())),
        "counts_by_source": dict(sorted(counts_by_source.items())),
        "top_action": _text(top.get("action")) if top else "",
        "top_reason": _text(top.get("reason")) if top else "",
        "top_adaptive_context": _text(top.get("adaptive_context")) if top else "",
        "decisions": decisions,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Maintenance policy decisions",
        "",
        f"- overall decision: **{payload.get('decision', NO_ACTION)}**",
        f"- release blocking: **{payload.get('release_blocking', False)}**",
        f"- automation allowed: **{payload.get('automation_allowed', False)}**",
        f"- adaptive ready: **{payload.get('adaptive_ready', False)}**",
        f"- decision items: **{payload.get('decision_count', 0)}**",
        f"- top action: {payload.get('top_action') or 'No action required.'}",
    ]

    top_context = _text(payload.get("top_adaptive_context"))
    if top_context:
        lines.append(f"- top context: {top_context}")

    decisions = _as_list(payload.get("decisions"))
    if not decisions:
        lines.extend(["", "No maintenance policy action is required."])
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            "",
            "| Rank | Decision | P | Source | Confidence | Risk | Title | Action |",
            "|---:|---|---:|---|---|---|---|---|",
        ]
    )
    for item in decisions:
        row = _as_dict(item)
        risk = (
            f"auto={_text(row.get('automation_risk'))}; "
            f"review={_text(row.get('review_risk'))}; "
            f"release={_text(row.get('release_risk'))}"
        )
        lines.append(
            f"| {row.get('rank', '')} | {_cell(row.get('decision'))} | "
            f"{row.get('priority', '')} | {_cell(row.get('source'))} | "
            f"{_cell(row.get('confidence'))} | {_cell(risk)} | "
            f"{_cell(row.get('title'))} | {_cell(row.get('action') or 'Review item.')} |"
        )

    lines.extend(["", "## Adaptive context", ""])
    for item in decisions[:5]:
        row = _as_dict(item)
        lines.append(
            f"- **{_cell(row.get('decision'))}** `{_cell(row.get('source_key'))}`: {_cell(row.get('adaptive_context'))}"
        )

    return "\n".join(lines).rstrip() + "\n"


def policy_decisions_from_priority_rollup(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return build_policy_decisions(payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.maintenance_policy_decisions")
    parser.add_argument("--priority-rollup-json", required=True)
    parser.add_argument("--out-json")
    parser.add_argument("--out-md")
    parser.add_argument("--format", choices=["json", "md"], default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = policy_decisions_from_priority_rollup(Path(args.priority_rollup_json))
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
