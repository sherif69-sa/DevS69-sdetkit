from __future__ import annotations

import json
from pathlib import Path

from sdetkit.pr_quality_candidate_validation import (
    SCHEMA_VERSION,
    build_validation_report,
    main,
    render_markdown,
)

FIXTURES = Path("tests/fixtures/pr_quality_candidate_visibility")
SCENARIOS = [
    FIXTURES / "formatting_candidate_verified.json",
    FIXTURES / "broader_diff_review_first.json",
]


def test_controlled_validation_exercises_verified_and_review_first_states_without_authority() -> (
    None
):
    report = build_validation_report(SCENARIOS)

    assert report["schema_version"] == SCHEMA_VERSION
    assert report["status"] == "passed"
    assert report["scenario_count"] == 2
    assert report["passed_count"] == 2

    rows = {row["scenario_id"]: row for row in report["scenarios"]}
    assert rows["formatting_candidate_structurally_verified"]["observed_status"] == (
        "candidate_structurally_verified"
    )
    assert rows["formatting_candidate_structurally_verified"]["observed_verifier_status"] == (
        "structurally_verified_candidate"
    )
    assert rows["broader_diff_remains_review_first"]["observed_status"] == (
        "candidate_review_first_after_verification"
    )
    assert rows["broader_diff_remains_review_first"]["observed_verifier_status"] == (
        "blocked_review_first"
    )
    assert all(row["candidate_renderer_exercised"] is True for row in rows.values())
    assert all(row["automation_allowed"] is False for row in rows.values())
    assert all(row["merge_authorized"] is False for row in rows.values())

    family = report["family_evaluation"]
    assert family["schema_version"] == "sdetkit.formatting_candidate_family_evaluation.v1"
    assert family["family"] == "formatting_only"
    assert family["evaluation_mode"] == "read_only_without_writes"
    assert family["structurally_verified_count"] == 1
    assert family["review_first_blocked_count"] == 1
    assert family["patch_application_allowed"] is False
    assert family["automation_allowed"] is False
    assert family["merge_authorized"] is False
    assert family["semantic_equivalence_proven"] is False
    assert family["current_pr_decision_input"] is False
    assert family["step_error_primary_categories"] == ["none"]

    dimensions = family["patch_score_dimension_statuses"]
    assert dimensions["diagnostic_precision"]["supported"] == 2
    assert dimensions["patch_scope_safety"]["contained"] == 2
    assert dimensions["proof_strength"]["supported"] == 2
    assert dimensions["reviewability"]["reviewable"] == 2
    assert dimensions["anti_cheat_integrity"]["preserved"] == 2
    assert dimensions["regression_risk"]["low"] == 2

    boundary = report["boundary"]
    assert boundary["controlled_fixture_inputs_only"] is True
    assert boundary["contributes_to_current_pr_decision"] is False
    assert boundary["automation_allowed"] is False
    assert boundary["merge_authorized"] is False
    assert boundary["semantic_equivalence_proven"] is False


def test_controlled_validation_markdown_marks_evidence_as_non_decision_input() -> None:
    markdown = render_markdown(build_validation_report(SCENARIOS))

    assert "Controlled read-only candidate evidence validation" in markdown
    assert "Current PR decision input: `false`" in markdown
    assert "Validation status: `passed`" in markdown
    assert "Scenarios passed: `2/2`" in markdown
    assert "Automation allowed: `false`" in markdown
    assert "Merge authorized: `false`" in markdown
    assert "Formatting-only family evaluation" in markdown
    assert "Family: `formatting_only`" in markdown
    assert "Evaluation mode: `read_only_without_writes`" in markdown
    assert "Structurally verified candidates: `1`" in markdown
    assert "Review-first blocked candidates: `1`" in markdown
    assert "Patch application allowed: `false`" in markdown
    assert "PatchScorer dimension reporting" in markdown
    assert "`diagnostic_precision`: supported=2" in markdown
    assert "`anti_cheat_integrity`: preserved=2" in markdown
    assert "Step error primary categories: `none`" in markdown
    assert "does not identify a remediation candidate in the current PR" in markdown


def test_controlled_validation_cli_writes_report_artifacts(tmp_path: Path, capsys) -> None:
    out_dir = tmp_path / "validation"
    rc = main(
        [
            "--scenario",
            str(SCENARIOS[0]),
            "--scenario",
            str(SCENARIOS[1]),
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    report = json.loads((out_dir / "candidate-validation.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "candidate-validation.md").read_text(encoding="utf-8")

    assert printed["status"] == "passed"
    assert printed["scenario_count"] == 2
    assert printed["passed_count"] == 2
    assert printed["family_evaluation"]["family"] == "formatting_only"
    assert printed["family_evaluation"]["patch_application_allowed"] is False
    assert printed["family_evaluation"]["step_error_primary_categories"] == ["none"]
    assert (
        printed["family_evaluation"]["patch_score_dimension_statuses"]["proof_strength"][
            "supported"
        ]
        == 2
    )
    assert printed["boundary"]["contributes_to_current_pr_decision"] is False
    assert report["family_evaluation"]["evaluation_mode"] == "read_only_without_writes"
    assert report["status"] == "passed"
    assert "Current PR decision input: `false`" in markdown
