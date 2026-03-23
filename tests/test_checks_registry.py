from __future__ import annotations

from sdetkit.checks import build_final_verdict, default_registry
from sdetkit.checks.results import CheckRecord


def test_registry_exposes_profiles_and_core_truth_checks() -> None:
    registry = default_registry()

    assert registry.profile_names() == ("quick", "standard", "strict", "adaptive")
    assert "tests_smoke" in registry.profile_check_ids("quick")
    assert "tests_full" in registry.profile_check_ids("strict")
    assert "security_scan" in registry.profile_check_ids("adaptive")

    planner = registry.planner_seed()
    assert planner["profile"] == "adaptive"
    assert planner["planner_selected"] is True
    assert "tests_smoke" in planner["check_ids"]


def test_final_verdict_contract_separates_run_skipped_and_failures() -> None:
    verdict = build_final_verdict(
        profile="quick",
        profile_notes="Smoke only.",
        checks=[
            CheckRecord(id="format_check", title="Ruff format check", status="passed"),
            CheckRecord(id="tests_smoke", title="Fast/smoke tests", status="failed"),
            CheckRecord(
                id="tests_full",
                title="Full pytest suite",
                status="skipped",
                reason="quick profile uses smoke gate only; run verify for merge truth",
            ),
        ],
    )

    payload = verdict.as_dict()

    assert payload["verdict_contract"] == "sdetkit.final-verdict.v1"
    assert payload["profile"] == "quick"
    assert payload["confidence_level"] == "low (smoke-only)"
    assert payload["blocking_failures"] == ["tests_smoke: Fast/smoke tests"]
    assert payload["checks_skipped"][0]["reason"] == (
        "quick profile uses smoke gate only; run verify for merge truth"
    )
    assert payload["recommendation"] == "do-not-merge"
