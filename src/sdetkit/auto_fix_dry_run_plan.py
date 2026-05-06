from __future__ import annotations

from collections import Counter
from typing import Any

SCHEMA_VERSION = "sdetkit.auto_fix.dry_run_plan.v1"
DRY_RUN_REQUIREMENTS = [
    "human_reviewed_policy_pr",
    "clean_worktree_required",
    "branch_only_changes",
    "no_direct_main_push",
    "rollback_plan_required",
    "post_run_evidence_required",
]
DEFAULT_COMMANDS = {
    "PRE_COMMIT_FORMAT_DRIFT": [
        "python -m pre_commit run -a",
        "git diff --check",
        "./scripts/pr_preflight.sh",
    ],
    "RUFF_FIXABLE_LINT": [
        "python -m ruff check . --fix --diff",
        "python -m ruff format --check .",
        "python -m pre_commit run -a",
    ],
}


def _as_proposals(payload: dict[str, Any]) -> list[dict[str, Any]]:
    proposals = payload.get("proposals", []) if isinstance(payload, dict) else []
    return proposals if isinstance(proposals, list) else []


def _plan_status(proposal: dict[str, Any]) -> str:
    if bool(proposal.get("auto_fix_allowed_now")):
        return "BLOCK_POLICY_VIOLATION"
    if str(proposal.get("proposal_status", "")) == "PROPOSE_POLICY_REVIEW":
        return "READY_FOR_DRY_RUN_PLAN_REVIEW"
    return "NOT_READY_FOR_DRY_RUN"


def _commands_for(classification: str) -> list[str]:
    return DEFAULT_COMMANDS.get(
        classification,
        ["python -m sdetkit investigate failure --log <log> --format markdown"],
    )


def _blockers_for(status: str, proposal: dict[str, Any]) -> list[str]:
    if status == "READY_FOR_DRY_RUN_PLAN_REVIEW":
        return ["Dry-run plan still requires human approval before execution."]
    if status == "BLOCK_POLICY_VIOLATION":
        return ["Auto-fix appears enabled before dry-run policy approval."]
    reasons = proposal.get("blocking_reasons", []) if isinstance(proposal.get("blocking_reasons"), list) else []
    return [str(reason) for reason in reasons] or ["Policy proposal is not ready for dry-run planning."]


def _plan_for_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    classification = str(proposal.get("classification", ""))
    status = _plan_status(proposal)
    return {
        "candidate_key": str(proposal.get("candidate_key", "")),
        "classification": classification,
        "dry_run_status": status,
        "automation_allowed": False,
        "auto_fix_allowed_now": False,
        "requires_human_review": True,
        "dry_run_commands": _commands_for(classification),
        "required_guardrails": DRY_RUN_REQUIREMENTS,
        "expected_artifacts": [
            "dry-run-command-log.txt",
            "dry-run-diff.patch",
            "dry-run-preflight-summary.md",
            "dry-run-outcome.json",
        ],
        "rollback_plan": "Discard the dry-run branch or revert the dry-run diff before any PR is opened.",
        "blockers": _blockers_for(status, proposal),
    }


def build_auto_fix_dry_run_plan(policy_proposals: dict[str, Any]) -> dict[str, Any]:
    plans = [_plan_for_proposal(proposal) for proposal in _as_proposals(policy_proposals)]
    counts = Counter(plan["dry_run_status"] for plan in plans)
    return {
        "schema_version": SCHEMA_VERSION,
        "diagnostic_only": True,
        "automation_allowed": False,
        "auto_fix_allowed_now": False,
        "plan_count": len(plans),
        "counts_by_dry_run_status": dict(sorted(counts.items())),
        "plans": sorted(plans, key=lambda item: item["candidate_key"]),
    }


def render_auto_fix_dry_run_plan_markdown(payload: dict[str, Any]) -> str:
    plans = payload.get("plans", []) if isinstance(payload.get("plans"), list) else []
    lines = [
        "# Auto-fix dry-run plan",
        "",
        f"- diagnostic only: **{payload.get('diagnostic_only', True)}**",
        f"- automation allowed: **{payload.get('automation_allowed', False)}**",
        f"- auto-fix allowed now: **{payload.get('auto_fix_allowed_now', False)}**",
        f"- plans: **{payload.get('plan_count', 0)}**",
        "",
        "## Plans",
        "",
        "| Candidate | Dry-run status | Commands | Artifacts |",
        "|---|---|---:|---:|",
    ]
    for plan in plans:
        commands = plan.get("dry_run_commands", []) if isinstance(plan.get("dry_run_commands"), list) else []
        artifacts = plan.get("expected_artifacts", []) if isinstance(plan.get("expected_artifacts"), list) else []
        lines.append(
            "| `{key}` | {status} | {commands} | {artifacts} |".format(
                key=plan.get("candidate_key", ""),
                status=plan.get("dry_run_status", ""),
                commands=len(commands),
                artifacts=len(artifacts),
            )
        )
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "This is a plan only. It does not run commands, modify files, create branches, or open PRs.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
