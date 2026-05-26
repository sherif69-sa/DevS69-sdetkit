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
    assert printed["boundary"]["contributes_to_current_pr_decision"] is False
    assert report["status"] == "passed"
    assert "Current PR decision input: `false`" in markdown
