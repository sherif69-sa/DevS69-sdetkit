from __future__ import annotations

from collections import Counter
from typing import Any

SCHEMA_VERSION = "sdetkit.pr_guardrail_decisions.v1"
REQUIRED_APPROVALS = [
    "human_reviewed_policy_pr",
    "dry_run_plan_approved",
    "rollback_plan_approved",
    "pr_only_guardrails",
    "clean_worktree_confirmed",
]
READY_STATUSES = {"READY_FOR_DRY_RUN_PLAN_REVIEW"}


def _as_plans(payload: dict[str, Any]) -> list[dict[str, Any]]:
    plans = payload.get("plans", []) if isinstance(payload, dict) else []
    return plans if isinstance(plans, list) else []


def _approved_set(approvals: list[str] | tuple[str, ...] | None) -> set[str]:
    if not approvals:
        return set()
    return {str(value).strip() for value in approvals if str(value).strip()}


def _missing_approvals(approved: set[str]) -> list[str]:
    return [item for item in REQUIRED_APPROVALS if item not in approved]


def _decision_status(plan: dict[str, Any], approved: set[str]) -> str:
    if bool(plan.get("direct_to_main_allowed")):
        return "BLOCK_DIRECT_TO_MAIN"
    if str(plan.get("dry_run_status", "")) not in READY_STATUSES:
        return "BLOCK_NOT_READY"
    if _missing_approvals(approved):
        return "BLOCK_MISSING_APPROVALS"
    return "READY_FOR_PR_BRANCH_REVIEW"


def _branch_name(candidate_key: str) -> str:
    clean = candidate_key.replace("diagnosis:", "").lower().replace("_", "-")
    return f"maintenance/{clean or 'candidate'}"


def _decision_for_plan(plan: dict[str, Any], approved: set[str]) -> dict[str, Any]:
    status = _decision_status(plan, approved)
    candidate_key = str(plan.get("candidate_key", ""))
    blockers = []
    if status == "BLOCK_DIRECT_TO_MAIN":
        blockers.append("Direct-to-main changes are blocked by policy.")
    elif status == "BLOCK_NOT_READY":
        blockers.append("Plan is not ready for a guarded PR branch.")
    elif status == "BLOCK_MISSING_APPROVALS":
        blockers.append("Required approvals are missing before a PR branch can be prepared.")
    return {
        "candidate_key": candidate_key,
        "classification": str(plan.get("classification", "")),
        "decision_status": status,
        "change_allowed_now": False,
        "direct_to_main_allowed": False,
        "pr_only": True,
        "requires_human_review": True,
        "target_branch": _branch_name(candidate_key),
        "required_approvals": REQUIRED_APPROVALS,
        "missing_approvals": _missing_approvals(approved),
        "review_commands": plan.get("dry_run_commands", [])
        if isinstance(plan.get("dry_run_commands"), list)
        else [],
        "expected_artifacts": plan.get("expected_artifacts", [])
        if isinstance(plan.get("expected_artifacts"), list)
        else [],
        "blockers": blockers,
    }


def build_pr_guardrail_decisions(
    dry_run_plan: dict[str, Any],
    approvals: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    approved = _approved_set(approvals)
    decisions = [_decision_for_plan(plan, approved) for plan in _as_plans(dry_run_plan)]
    counts = Counter(decision["decision_status"] for decision in decisions)
    return {
        "schema_version": SCHEMA_VERSION,
        "automation_allowed": False,
        "change_allowed_now": False,
        "direct_to_main_allowed": False,
        "decision_count": len(decisions),
        "counts_by_decision_status": dict(sorted(counts.items())),
        "decisions": sorted(decisions, key=lambda item: item["candidate_key"]),
    }


def render_pr_guardrail_decisions_markdown(payload: dict[str, Any]) -> str:
    decisions = payload.get("decisions", []) if isinstance(payload.get("decisions"), list) else []
    lines = [
        "# PR guardrail decisions",
        "",
        f"- automation allowed: **{payload.get('automation_allowed', False)}**",
        f"- change allowed now: **{payload.get('change_allowed_now', False)}**",
        f"- direct-to-main allowed: **{payload.get('direct_to_main_allowed', False)}**",
        f"- decisions: **{payload.get('decision_count', 0)}**",
        "",
        "## Decisions",
        "",
        "| Candidate | Decision | Target branch | Missing approvals |",
        "|---|---|---|---:|",
    ]
    for decision in decisions:
        missing = decision.get("missing_approvals", [])
        missing_count = len(missing) if isinstance(missing, list) else 0
        lines.append(
            "| `{key}` | {status} | `{branch}` | {missing} |".format(
                key=decision.get("candidate_key", ""),
                status=decision.get("decision_status", ""),
                branch=decision.get("target_branch", ""),
                missing=missing_count,
            )
        )
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "This layer only decides whether a candidate may proceed toward a PR branch for human review.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
