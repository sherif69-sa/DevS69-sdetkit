from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "sdetkit.investigation.safe_fix_policy.v1"
MECHANICAL_CANDIDATE_CLASSES = {
    "PRE_COMMIT_FORMAT_DRIFT": {
        "route": "safe_mechanical_candidate_later",
        "risk_level": "low",
        "reason": "Formatting drift can become a narrow mechanical candidate after repeated proof.",
    },
    "RUFF_FIXABLE_LINT": {
        "route": "safe_mechanical_candidate_later",
        "risk_level": "low",
        "reason": "Ruff fixable lint can become a narrow mechanical candidate after proof and policy.",
    },
}
REVIEW_FIRST_CLASSES = {
    "GIT_BRANCH_DIVERGED": ("command_guidance", "Git workflow drift needs explicit user sync."),
    "REMOTE_BRANCH_DRIFT": ("sync_guidance", "Remote branch drift needs explicit user sync."),
    "MISSING_TEST_DEPENDENCY": (
        "environment_guidance",
        "Dependency issues are environment guidance, not code mutation.",
    ),
    "PYTHON_RUNTIME_COMPATIBILITY": (
        "compatibility_pr",
        "Runtime compatibility changes need review.",
    ),
    "LOCAL_ENVIRONMENT_FRICTION": (
        "environment_guidance",
        "Local environment friction is guidance-only.",
    ),
    "BROKEN_TEST_DOUBLE": (
        "review_first_test_fix",
        "Broken test doubles need review before changing tests.",
    ),
    "MISSING_PUBLIC_API_PARITY": (
        "review_first_product_fix",
        "Public API gaps are product changes.",
    ),
    "PRODUCT_LOGIC_FAILURE": (
        "review_first_product_fix",
        "Product logic failures need human review.",
    ),
    "UNKNOWN_REVIEW_REQUIRED": (
        "review_first_unknown",
        "Unknown classifications remain review-required.",
    ),
}


def route_investigation_safe_fix_policy(classification: str) -> dict[str, Any]:
    clean = classification.strip()
    if not clean:
        raise OSError("classification is required")
    if clean in MECHANICAL_CANDIDATE_CLASSES:
        meta = MECHANICAL_CANDIDATE_CLASSES[clean]
        return {
            "schema_version": SCHEMA_VERSION,
            "diagnostic_only": True,
            "automation_allowed": False,
            "classification": clean,
            "auto_fix_allowed_now": False,
            "safe_to_auto_fix": False,
            "candidate_later": True,
            "requires_human_review": True,
            "risk_level": meta["risk_level"],
            "route": meta["route"],
            "blocking_reason": "Policy, proof history, dry run, and PR-only guardrails are still required.",
            "reason": meta["reason"],
        }
    route, reason = REVIEW_FIRST_CLASSES.get(
        clean,
        ("review_first_unknown", "Unrecognized classification remains review-required."),
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "diagnostic_only": True,
        "automation_allowed": False,
        "classification": clean,
        "auto_fix_allowed_now": False,
        "safe_to_auto_fix": False,
        "candidate_later": False,
        "requires_human_review": True,
        "risk_level": "review_required",
        "route": route,
        "blocking_reason": "This classification is not eligible for automatic changes at this stage.",
        "reason": reason,
    }
