from __future__ import annotations

import json
from pathlib import Path

from sdetkit.adoption_learning import build_adoption_learning_payload
from sdetkit.adoption_public_repo_eligibility import (
    SCHEMA_VERSION,
    evaluate_public_repo_eligibility,
    render_public_repo_eligibility_text,
    write_public_repo_eligibility_artifact,
)


def test_public_repo_eligibility_allows_small_mit_public_repo() -> None:
    payload = evaluate_public_repo_eligibility(
        repo_url="https://github.com/example/demo",
        license_id="MIT",
        repo_size="small",
    )

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["allowed_for_read_only_trial"] is True
    assert payload["blocked_reasons"] == []
    assert "license is permissive: MIT" in payload["reasons"]
    assert payload["rules"] == {
        "read_only_trial_only": True,
        "no_dependency_install": True,
        "no_test_execution": True,
        "no_target_repo_mutation": True,
        "no_pr_or_issue_opened_on_target": True,
        "no_endorsement_claim": True,
    }
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_public_repo_eligibility_blocks_missing_license() -> None:
    payload = evaluate_public_repo_eligibility(
        repo_url="https://github.com/example/no-license",
        license_id="",
        repo_size="small",
    )

    assert payload["allowed_for_read_only_trial"] is False
    assert "license is missing" in payload["blocked_reasons"]


def test_public_repo_eligibility_blocks_restrictive_and_sensitive_repo() -> None:
    payload = evaluate_public_repo_eligibility(
        repo_url="https://github.com/example/restricted",
        license_id="Proprietary",
        repo_size="huge",
        has_no_ai_notice=True,
        has_security_sensitive_content=True,
    )

    assert payload["allowed_for_read_only_trial"] is False
    assert "license is not in permissive allowlist: Proprietary" in payload["blocked_reasons"]
    assert "repo size is not suitable for first trial: huge" in payload["blocked_reasons"]
    assert "repo contains no-AI usage notice" in payload["blocked_reasons"]
    assert "repo appears security-sensitive" in payload["blocked_reasons"]


def test_public_repo_eligibility_owned_repo_can_pass_with_operator_control() -> None:
    payload = evaluate_public_repo_eligibility(
        repo_url="https://github.com/example/owned-demo",
        license_id="",
        repo_size="small",
        owned_by_us=True,
    )

    assert payload["allowed_for_read_only_trial"] is True
    assert "repo is owned or controlled by the operator" in payload["reasons"]


def test_public_repo_eligibility_cli_dispatch_writes_artifact(
    tmp_path: Path,
    capsys,
) -> None:
    out = tmp_path / "public-repo-eligibility.json"

    from sdetkit.cli import main as cli_main

    rc = cli_main(
        [
            "public-repo-eligibility",
            "--repo-url",
            "https://github.com/example/demo",
            "--license",
            "Apache-2.0",
            "--out",
            str(out),
            "--format",
            "text",
        ]
    )

    assert rc == 0
    stdout = capsys.readouterr().out
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["allowed_for_read_only_trial"] is True
    assert "public_repo_eligibility_status=evaluated" in stdout
    assert "allowed_for_read_only_trial=true" in stdout
    assert "- no_dependency_install=true" in stdout
    assert "- patch_application_allowed=false" in stdout


def test_public_repo_eligibility_text_reports_blockers() -> None:
    payload = evaluate_public_repo_eligibility(
        repo_url="https://github.com/example/blocked",
        license_id="",
        has_no_benchmark_notice=True,
    )

    text = render_public_repo_eligibility_text(payload)

    assert "allowed_for_read_only_trial=false" in text
    assert "- license is missing" in text
    assert "- repo contains no-benchmark usage notice" in text
    assert "- patch_application_allowed=false" in text


def test_public_repo_eligibility_writer_records_json(tmp_path: Path) -> None:
    out = tmp_path / "eligibility.json"

    payload = write_public_repo_eligibility_artifact(
        repo_url="https://github.com/example/demo",
        license_id="ISC",
        out=out,
    )

    assert payload["allowed_for_read_only_trial"] is True
    assert json.loads(out.read_text(encoding="utf-8"))["schema_version"] == SCHEMA_VERSION


def test_self_learning_advances_to_public_repo_trial_after_eligibility_screen() -> None:
    payload = build_adoption_learning_payload(Path("."))

    assert payload["recommended_next_upgrade"] == "first permissive public repo read-only trial"
    assert (
        "add public repo eligibility screen before using third-party repos"
        not in payload["learning_gaps"]
    )
    assert "run first permissive public repo read-only trial" in payload["learning_gaps"]
    assert payload["authority_boundary"]["automation_allowed"] is False
    assert payload["authority_boundary"]["patch_application_allowed"] is False
