from __future__ import annotations

from collections import Counter
from typing import Any

from sdetkit.investigation_safe_fix_policy import route_investigation_safe_fix_policy

SCHEMA_VERSION = "sdetkit.safe_fix.candidates.v1"
DEFAULT_CANDIDATE_CLASSES = ("PRE_COMMIT_FORMAT_DRIFT", "RUFF_FIXABLE_LINT")
DEFAULT_ALLOWED_COMMANDS = {
    "PRE_COMMIT_FORMAT_DRIFT": ["python -m pre_commit run -a", "./scripts/pr_preflight.sh"],
    "RUFF_FIXABLE_LINT": ["python -m ruff check .", "python -m pre_commit run -a"],
}
DEFAULT_FORBIDDEN_PATHS = [".github/workflows", "pyproject.toml", "src/sdetkit/security"]
REQUIRED_HISTORY_COUNT = 3
REQUIRED_SUCCESS_COUNT = 3


def _candidate_key(classification: str) -> str:
    return f"diagnosis:{classification}"


def _status_for(history_count: int, success_count: int) -> str:
    if history_count < REQUIRED_HISTORY_COUNT:
        return "OBSERVE_MORE"
    if success_count < REQUIRED_SUCCESS_COUNT:
        return "NOT_READY"
    return "READY_FOR_POLICY_PR"


def _counts_by_class(records: list[dict[str, Any]]) -> tuple[Counter[str], Counter[str]]:
    seen: Counter[str] = Counter()
    successes: Counter[str] = Counter()
    for record in records:
        classification = str(record.get("classification", "")).strip()
        if not classification:
            continue
        seen[classification] += 1
        if bool(record.get("merged")) and str(record.get("manual_fix_outcome", "")) == "merged":
            successes[classification] += 1
        elif str(record.get("safe_fix_outcome", "")) == "manual_success":
            successes[classification] += 1
    return seen, successes


def _candidate_for_class(
    classification: str,
    history_count: int,
    success_count: int,
) -> dict[str, Any]:
    policy = route_investigation_safe_fix_policy(classification)
    return {
        "candidate_key": _candidate_key(classification),
        "classification": classification,
        "category": "formatting" if classification == "PRE_COMMIT_FORMAT_DRIFT" else "lint",
        "risk_level": policy["risk_level"],
        "required_history_count": REQUIRED_HISTORY_COUNT,
        "required_success_count": REQUIRED_SUCCESS_COUNT,
        "observed_history_count": history_count,
        "observed_success_count": success_count,
        "allowed_commands": DEFAULT_ALLOWED_COMMANDS[classification],
        "forbidden_paths": DEFAULT_FORBIDDEN_PATHS,
        "rollback_required": True,
        "automation_allowed": False,
        "auto_fix_allowed_now": False,
        "current_status": _status_for(history_count, success_count),
        "blocking_reason": policy["blocking_reason"],
    }


def build_safe_fix_candidate_registry(
    outcome_memory: dict[str, Any] | None = None,
    candidate_classes: tuple[str, ...] = DEFAULT_CANDIDATE_CLASSES,
) -> dict[str, Any]:
    records = outcome_memory.get("records", []) if isinstance(outcome_memory, dict) else []
    records = records if isinstance(records, list) else []
    seen, successes = _counts_by_class(records)
    candidates = [
        _candidate_for_class(
            classification,
            seen.get(classification, 0),
            successes.get(classification, 0),
        )
        for classification in sorted(candidate_classes)
    ]
    counts = Counter(str(candidate["current_status"]) for candidate in candidates)
    return {
        "schema_version": SCHEMA_VERSION,
        "diagnostic_only": True,
        "automation_allowed": False,
        "candidate_count": len(candidates),
        "counts_by_status": dict(sorted(counts.items())),
        "candidates": candidates,
    }


def render_safe_fix_candidate_registry_markdown(payload: dict[str, Any]) -> str:
    candidates = (
        payload.get("candidates", []) if isinstance(payload.get("candidates"), list) else []
    )
    lines = [
        "# Safe-fix candidate registry",
        "",
        f"- diagnostic only: **{payload.get('diagnostic_only', True)}**",
        f"- automation allowed: **{payload.get('automation_allowed', False)}**",
        f"- candidates: **{payload.get('candidate_count', 0)}**",
        "",
        "## Candidates",
        "",
        "| Candidate | Status | History | Successes | Allowed now |",
        "|---|---|---:|---:|---|",
    ]
    for candidate in candidates:
        lines.append(
            "| `{key}` | {status} | {history} | {successes} | {allowed} |".format(
                key=candidate.get("candidate_key", ""),
                status=candidate.get("current_status", ""),
                history=candidate.get("observed_history_count", 0),
                successes=candidate.get("observed_success_count", 0),
                allowed=candidate.get("auto_fix_allowed_now", False),
            )
        )
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "This registry is diagnostic-only. Candidates still require policy, proof, dry-run, rollback, and PR-only guardrails before any future automation.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
