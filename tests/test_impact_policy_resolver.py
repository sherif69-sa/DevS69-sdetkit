from __future__ import annotations

from scripts.impact_policy_resolver import resolve_policy_for_branch


def test_resolve_policy_applies_main_override() -> None:
    policy = {
        "min_overall_program_score": 85,
        "min_step_scores": {"step_1": 85},
        "branch_overrides": {
            "main": {"min_overall_program_score": 90, "min_step_scores": {"step_1": 90}}
        },
    }
    resolved = resolve_policy_for_branch(policy, "main")
    assert resolved["min_overall_program_score"] == 90
    assert resolved["min_step_scores"]["step_1"] == 90


def test_resolve_policy_applies_feature_glob() -> None:
    policy = {
        "min_overall_program_score": 85,
        "branch_overrides": {"feature/*": {"min_overall_program_score": 80}},
    }
    resolved = resolve_policy_for_branch(policy, "feature/demo")
    assert resolved["min_overall_program_score"] == 80
