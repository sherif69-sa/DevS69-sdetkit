from __future__ import annotations

from collections import Counter
from typing import Any

SCHEMA_VERSION = "sdetkit.auto_fix.probation_report.v1"


def _as_candidates(registry: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = registry.get("candidates", []) if isinstance(registry, dict) else []
    return candidates if isinstance(candidates, list) else []


def _probation_status(candidate: dict[str, Any]) -> str:
    if bool(candidate.get("auto_fix_allowed_now")):
        return "POLICY_VIOLATION"
    status = str(candidate.get("current_status", "OBSERVE_MORE"))
    if status == "READY_FOR_POLICY_PR":
        return "READY_FOR_PROBATION_REVIEW"
    if status == "NOT_READY":
        return "NEEDS_MORE_SUCCESSFUL_PROOF"
    return "NEEDS_MORE_OBSERVATION"


def _blocking_reasons(candidate: dict[str, Any], probation_status: str) -> list[str]:
    reasons = [str(candidate.get("blocking_reason", "")).strip()]
    if probation_status == "NEEDS_MORE_OBSERVATION":
        reasons.append("Candidate has not met the required observation count.")
    elif probation_status == "NEEDS_MORE_SUCCESSFUL_PROOF":
        reasons.append(
            "Candidate has enough observations but not enough successful manual outcomes."
        )
    elif probation_status == "READY_FOR_PROBATION_REVIEW":
        reasons.append("Candidate can be reviewed for a future policy PR, not executed now.")
    elif probation_status == "POLICY_VIOLATION":
        reasons.append("Candidate unexpectedly allows auto-fix now and must be blocked.")
    return [reason for reason in reasons if reason]


def _row(candidate: dict[str, Any]) -> dict[str, Any]:
    status = _probation_status(candidate)
    return {
        "candidate_key": str(candidate.get("candidate_key", "")),
        "classification": str(candidate.get("classification", "")),
        "current_status": str(candidate.get("current_status", "")),
        "probation_status": status,
        "observed_history_count": int(candidate.get("observed_history_count", 0) or 0),
        "observed_success_count": int(candidate.get("observed_success_count", 0) or 0),
        "required_history_count": int(candidate.get("required_history_count", 0) or 0),
        "required_success_count": int(candidate.get("required_success_count", 0) or 0),
        "automation_allowed": False,
        "auto_fix_allowed_now": False,
        "blocking_reasons": _blocking_reasons(candidate, status),
    }


def build_auto_fix_probation_report(registry: dict[str, Any]) -> dict[str, Any]:
    rows = [_row(candidate) for candidate in _as_candidates(registry)]
    counts = Counter(row["probation_status"] for row in rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "diagnostic_only": True,
        "automation_allowed": False,
        "auto_fix_allowed_now": False,
        "candidate_count": len(rows),
        "counts_by_probation_status": dict(sorted(counts.items())),
        "probation_rows": sorted(rows, key=lambda row: row["candidate_key"]),
    }


def render_auto_fix_probation_report_markdown(payload: dict[str, Any]) -> str:
    rows = (
        payload.get("probation_rows", []) if isinstance(payload.get("probation_rows"), list) else []
    )
    lines = [
        "# Auto-fix probation report",
        "",
        f"- diagnostic only: **{payload.get('diagnostic_only', True)}**",
        f"- automation allowed: **{payload.get('automation_allowed', False)}**",
        f"- auto-fix allowed now: **{payload.get('auto_fix_allowed_now', False)}**",
        f"- candidates: **{payload.get('candidate_count', 0)}**",
        "",
        "## Candidate probation status",
        "",
        "| Candidate | Probation status | History | Successes | Allowed now |",
        "|---|---|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            "| `{key}` | {status} | {history}/{required_history} | {successes}/{required_success} | {allowed} |".format(
                key=row.get("candidate_key", ""),
                status=row.get("probation_status", ""),
                history=row.get("observed_history_count", 0),
                required_history=row.get("required_history_count", 0),
                successes=row.get("observed_success_count", 0),
                required_success=row.get("required_success_count", 0),
                allowed=row.get("auto_fix_allowed_now", False),
            )
        )
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "This report does not enable auto-fix. READY candidates still require a separate policy PR, dry-run plan, rollback plan, and PR-only guardrails.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
