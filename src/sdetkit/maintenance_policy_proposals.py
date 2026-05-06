from __future__ import annotations

from collections import Counter
from typing import Any

SCHEMA_VERSION = "sdetkit.maintenance.policy_proposals.v1"


def _as_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = report.get("probation_rows", []) if isinstance(report, dict) else []
    return rows if isinstance(rows, list) else []


def _proposal_status(row: dict[str, Any]) -> str:
    if bool(row.get("auto_fix_allowed_now")):
        return "BLOCK_POLICY_VIOLATION"
    status = str(row.get("probation_status", ""))
    if status == "READY_FOR_PROBATION_REVIEW":
        return "PROPOSE_POLICY_REVIEW"
    if status == "NEEDS_MORE_SUCCESSFUL_PROOF":
        return "WAIT_FOR_MORE_SUCCESSFUL_PROOF"
    return "WAIT_FOR_MORE_OBSERVATION"


def _recommended_next_step(status: str) -> str:
    if status == "PROPOSE_POLICY_REVIEW":
        return "Open a human-reviewed policy proposal PR before any dry-run or automation work."
    if status == "WAIT_FOR_MORE_SUCCESSFUL_PROOF":
        return "Collect additional successful manual outcomes before proposing policy."
    if status == "BLOCK_POLICY_VIOLATION":
        return "Block this candidate and investigate why auto-fix appears enabled too early."
    return "Collect more observation history before proposing policy."


def _proposal_for_row(row: dict[str, Any]) -> dict[str, Any]:
    status = _proposal_status(row)
    return {
        "candidate_key": str(row.get("candidate_key", "")),
        "classification": str(row.get("classification", "")),
        "proposal_status": status,
        "automation_allowed": False,
        "auto_fix_allowed_now": False,
        "requires_human_review": True,
        "recommended_next_step": _recommended_next_step(status),
        "observed_history_count": int(row.get("observed_history_count", 0) or 0),
        "observed_success_count": int(row.get("observed_success_count", 0) or 0),
        "blocking_reasons": row.get("blocking_reasons", [])
        if isinstance(row.get("blocking_reasons"), list)
        else [],
        "policy_requirements": [
            "human_reviewed_policy_pr",
            "dry_run_plan",
            "rollback_plan",
            "pr_only_guardrails",
            "post_merge_outcome_memory",
        ],
    }


def build_maintenance_policy_proposals(probation_report: dict[str, Any]) -> dict[str, Any]:
    proposals = [_proposal_for_row(row) for row in _as_rows(probation_report)]
    counts = Counter(proposal["proposal_status"] for proposal in proposals)
    return {
        "schema_version": SCHEMA_VERSION,
        "diagnostic_only": True,
        "automation_allowed": False,
        "auto_fix_allowed_now": False,
        "proposal_count": len(proposals),
        "counts_by_proposal_status": dict(sorted(counts.items())),
        "proposals": sorted(proposals, key=lambda item: item["candidate_key"]),
    }


def render_maintenance_policy_proposals_markdown(payload: dict[str, Any]) -> str:
    proposals = payload.get("proposals", []) if isinstance(payload.get("proposals"), list) else []
    lines = [
        "# Maintenance policy proposals",
        "",
        f"- diagnostic only: **{payload.get('diagnostic_only', True)}**",
        f"- automation allowed: **{payload.get('automation_allowed', False)}**",
        f"- auto-fix allowed now: **{payload.get('auto_fix_allowed_now', False)}**",
        f"- proposals: **{payload.get('proposal_count', 0)}**",
        "",
        "## Proposal status",
        "",
        "| Candidate | Proposal status | History | Successes | Next step |",
        "|---|---|---:|---:|---|",
    ]
    for proposal in proposals:
        lines.append(
            "| `{key}` | {status} | {history} | {successes} | {next_step} |".format(
                key=proposal.get("candidate_key", ""),
                status=proposal.get("proposal_status", ""),
                history=proposal.get("observed_history_count", 0),
                successes=proposal.get("observed_success_count", 0),
                next_step=proposal.get("recommended_next_step", ""),
            )
        )
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "These are policy proposals only. They do not enable dry-runs, create fix branches, or execute auto-fix behavior.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
