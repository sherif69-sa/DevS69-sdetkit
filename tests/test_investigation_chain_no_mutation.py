from __future__ import annotations

import subprocess
from typing import Any

from sdetkit.auto_fix_dry_run_plan import build_auto_fix_dry_run_plan
from sdetkit.auto_fix_probation_report import build_auto_fix_probation_report
from sdetkit.maintenance_policy_proposals import build_maintenance_policy_proposals
from sdetkit.pr_investigation_summary import build_pr_investigation_summary
from sdetkit.safe_fix_candidate_registry import build_safe_fix_candidate_registry


def _assert_no_mutation_flags(payload: dict[str, Any]) -> None:
    if "diagnostic_only" in payload:
        assert payload["diagnostic_only"] is True
    if "automation_allowed" in payload:
        assert payload["automation_allowed"] is False
    if "auto_fix_allowed_now" in payload:
        assert payload["auto_fix_allowed_now"] is False
    if "requires_human_review" in payload:
        assert payload["requires_human_review"] is True

    for value in payload.values():
        if isinstance(value, dict):
            _assert_no_mutation_flags(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _assert_no_mutation_flags(item)


def test_investigation_recommendation_plan_chain_stays_non_mutating(monkeypatch) -> None:
    def forbidden_subprocess(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise AssertionError(f"unexpected subprocess call: args={args!r} kwargs={kwargs!r}")

    monkeypatch.setattr(subprocess, "run", forbidden_subprocess)

    summary = build_pr_investigation_summary(
        log_text="ruff reported F401 unused import [*] fixable in src/sdetkit/example.py",
        surface="lint",
        memory_seen_count=3,
        memory_fixed_count=3,
    )

    registry = build_safe_fix_candidate_registry(
        {
            "records": [
                {
                    "classification": "RUFF_FIXABLE_LINT",
                    "safe_fix_outcome": "manual_success",
                },
                {
                    "classification": "RUFF_FIXABLE_LINT",
                    "safe_fix_outcome": "manual_success",
                },
                {
                    "classification": "RUFF_FIXABLE_LINT",
                    "safe_fix_outcome": "manual_success",
                },
            ]
        },
        candidate_classes=("RUFF_FIXABLE_LINT",),
    )
    probation = build_auto_fix_probation_report(registry)
    proposals = build_maintenance_policy_proposals(probation)
    dry_run = build_auto_fix_dry_run_plan(proposals)

    for payload in (summary, registry, probation, proposals, dry_run):
        _assert_no_mutation_flags(payload)

    assert registry["candidates"][0]["current_status"] == "READY_FOR_POLICY_PR"
    assert probation["probation_rows"][0]["probation_status"] == "READY_FOR_PROBATION_REVIEW"
    assert proposals["proposals"][0]["proposal_status"] == "PROPOSE_POLICY_REVIEW"
    assert dry_run["plans"][0]["dry_run_status"] == "READY_FOR_DRY_RUN_PLAN_REVIEW"
    assert dry_run["plans"][0]["dry_run_commands"]
    assert dry_run["plans"][0]["expected_artifacts"]
