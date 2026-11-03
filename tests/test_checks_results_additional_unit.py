from __future__ import annotations

from sdetkit.checks.results import CheckRecord, build_final_verdict


def test_final_verdict_markdown_includes_profile_notes_cache_and_lists() -> None:
    verdict = build_final_verdict(
        profile="standard",
        profile_notes="planner narrowed scope",
        checks=[
            CheckRecord(
                id="tests_smoke",
                title="Smoke Tests",
                status="failed",
                reason="flake in test suite",
                metadata={"target_mode": "targeted", "cache": {"status": "miss"}},
            ),
            CheckRecord(
                id="lint",
                title="Lint",
                status="skipped",
                reason="not needed for this lane",
            ),
        ],
        metadata={"execution": {"mode": "parallel", "workers": 4}},
    )

    assert verdict.recommendation == "do-not-merge"
    md = verdict.to_markdown()
    assert "- profile notes: planner narrowed scope" in md
    assert "cache=miss" in md
    assert "`lint` - not needed for this lane" in md
    assert "- tests_smoke: Smoke Tests" in md


def test_final_verdict_adaptive_ok_uses_run_standard_validation() -> None:
    verdict = build_final_verdict(
        profile="adaptive",
        checks=[CheckRecord(id="lint", title="Lint", status="passed")],
    )

    assert verdict.ok is True
    assert verdict.recommendation == "run-standard-validation"


def test_final_verdict_markdown_advisory_none_when_absent() -> None:
    verdict = build_final_verdict(
        profile="strict",
        checks=[CheckRecord(id="tests_full", title="Full Tests", status="passed")],
    )

    assert verdict.recommendation == "ready-for-merge-review"
    md = verdict.to_markdown()
    assert "### Advisory findings" in md
    assert "- none" in md


def test_strict_verdict_blocks_on_a_check_skipped_for_a_missing_tool() -> None:
    checks = [
        CheckRecord(id="lint", title="Lint", status="passed"),
        CheckRecord(
            id="tests_full",
            title="Full tests",
            status="skipped",
            reason="missing required tool(s): pytest",
        ),
        CheckRecord(
            id="typing", title="Typing", status="skipped", reason="missing required path(s): src"
        ),
    ]

    strict = build_final_verdict(profile="strict", checks=checks)
    assert strict.ok is False
    assert strict.recommendation == "do-not-merge"
    assert strict.blocking_failures == (
        "tests_full: Full tests (not run: missing required tool(s): pytest)",
    )

    standard = build_final_verdict(profile="standard", checks=checks)
    assert standard.ok is True
