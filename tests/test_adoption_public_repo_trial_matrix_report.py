from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit.adoption_public_repo_trial_matrix_report import (
    ACCEPTED_MATRIX_SCHEMA,
    SCHEMA_VERSION,
    build_public_repo_trial_matrix_report,
    write_public_repo_trial_matrix_report_artifacts,
)

MATRIX_PATH = Path("tests/fixtures/adoption_public_trials/public_repo_trial_matrix.json")


def test_public_repo_trial_matrix_report_summarizes_recorded_evidence() -> None:
    payload = build_public_repo_trial_matrix_report(MATRIX_PATH, current_head_sha="head-a")
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["report_status"] == "ready_for_human_review"
    assert payload["source_matrix"]["schema_version"] == ACCEPTED_MATRIX_SCHEMA
    assert payload["summary"] == {
        "trial_count": 3,
        "eligible_trial_count": 3,
        "prior_single_repo_trial_count": 1,
        "new_read_only_trial_candidate_count": 2,
        "all_trials_eligible": True,
    }
    assert [trial["repo_full_name"] for trial in payload["trials"]] == [
        "pallets/click",
        "pallets/itsdangerous",
        "pallets/markupsafe",
    ]
    provenance = payload["input_provenance"]
    assert provenance["input_digest_algorithm"] == "sha256"
    assert len(provenance["input_digest"]) == 64
    assert len(provenance["matrix_sha256"]) == 64
    assert provenance["current_head_sha"] == "head-a"
    assert provenance["current_head_bound"] is True
    assert payload["rules"] == {
        "source_matrix_only": True,
        "target_repos_read": False,
        "install_dependencies": False,
        "target_tests_executed": False,
        "target_repo_mutation": False,
        "target_pr_or_issue_opened": False,
        "endorsement_claim": False,
        "review_first": True,
    }
    assert payload["reporting_only"] is True
    assert payload["repo_mutation"] is False
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False
    assert payload["authority_boundary"] == {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def test_public_repo_trial_matrix_report_writes_json_and_markdown(tmp_path: Path) -> None:
    out = tmp_path / "reports" / "public-trial-matrix-report.json"
    payload = write_public_repo_trial_matrix_report_artifacts(
        matrix_json=MATRIX_PATH,
        out=out,
        root=Path("."),
        current_head_sha="head-a",
    )
    markdown = out.with_suffix(".md")
    assert out.is_file()
    assert markdown.is_file()
    assert json.loads(out.read_text(encoding="utf-8")) == payload
    rendered = markdown.read_text(encoding="utf-8")
    assert "# SDETKit public repository trial matrix report" in rendered
    assert "trial_count: 3" in rendered
    assert "new_read_only_trial_candidate_count: 2" in rendered
    assert "`pallets/click`" in rendered
    assert "target_repos_read: false" in rendered
    assert "merge_authorized: false" in rendered


def test_public_repo_trial_matrix_report_cli_dispatch(tmp_path: Path, capsys) -> None:
    from sdetkit.cli import main as cli_main

    out = tmp_path / "report.json"
    markdown = tmp_path / "report.md"
    rc = cli_main(
        [
            "adoption-public-trial-matrix-report",
            "--matrix-json",
            str(MATRIX_PATH),
            "--out",
            str(out),
            "--markdown-out",
            str(markdown),
            "--format",
            "text",
        ]
    )
    assert rc == 0
    stdout = capsys.readouterr().out
    assert "# SDETKit public repository trial matrix report" in stdout
    assert "report_status: ready_for_human_review" in stdout
    assert out.is_file()
    assert markdown.is_file()


def test_public_repo_trial_matrix_report_rejects_wrong_schema(tmp_path: Path) -> None:
    matrix = tmp_path / "matrix.json"
    matrix.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.public_repo_trial_matrix.v0",
                "trials": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unsupported public repo trial matrix schema"):
        build_public_repo_trial_matrix_report(matrix)
