from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit.diagnostic_job import (
    SCHEMA_VERSION,
    WORKER_RESULT_SCHEMA_VERSION,
    build_diagnostic_job,
    main,
    render_markdown,
    run_diagnostic_worker,
    validate_job,
)


def _job() -> dict:
    return build_diagnostic_job(
        repo="sherif69-sa/DevS69-sdetkit",
        base_sha="base123",
        head_sha="head123",
        event_name="pull_request",
        pr_number=1441,
        input_artifacts={"check_intelligence": "build/check-intelligence.json"},
        generated_at="2026-05-27T00:00:00Z",
    )


def _formatting_intelligence() -> dict:
    return {
        "failed_checks": [
            {
                "name": "PR Quality local quality gate",
                "surface": "formatting",
                "command": "python -m pre_commit run -a",
                "scope": "pr_owned_only",
                "diagnosis": {"title": "Pre-commit formatting drift", "surface": "formatting"},
                "first_failure": {
                    "line": "ruff format..............................Failed",
                    "line_number": 30,
                    "tool": "ruff",
                    "kind": "format_drift",
                },
                "safe_to_auto_fix": True,
                "safe_remediation": {
                    "safe_to_auto_fix": True,
                    "strategy": "run_pre_commit",
                    "affected_files": ["src/sdetkit/example.py"],
                },
                "affected_files": ["src/sdetkit/example.py"],
            }
        ]
    }


def test_diagnostic_job_is_deterministic_and_read_only() -> None:
    first = _job()
    second = _job()

    assert first == second
    assert first["schema_version"] == SCHEMA_VERSION
    assert first["job_type"] == "diagnostic_vector"
    assert first["execution_mode"] == "local_read_only"
    assert first["worker_contract"]["writes_artifacts_only"] is True
    assert first["worker_contract"]["runs_proof_commands"] is False
    assert first["worker_contract"]["applies_patch"] is False
    assert first["worker_contract"]["publishes_decision"] is False
    assert first["decision_boundary"]["current_pr_decision_input"] is False
    assert first["decision_boundary"]["automation_allowed"] is False
    assert first["decision_boundary"]["merge_authorized"] is False


def test_diagnostic_worker_executes_existing_vector_engine_without_authority(
    tmp_path: Path,
) -> None:
    job = _job()
    result = run_diagnostic_worker(
        job,
        check_intelligence=_formatting_intelligence(),
        out_dir=tmp_path,
    )

    assert result["schema_version"] == WORKER_RESULT_SCHEMA_VERSION
    assert result["status"] == "completed"
    assert result["summary"]["diagnosis_count"] == 1
    assert result["summary"]["safe_fix_candidate_count"] == 1
    assert result["primary_diagnosis"]["failure_surface"] == "formatting"
    assert result["primary_diagnosis"]["safe_fix_candidate"] is True
    assert result["decision_boundary"]["current_pr_decision_input"] is False
    assert result["decision_boundary"]["proof_commands_executed"] is False
    assert result["decision_boundary"]["patch_application_allowed"] is False
    assert result["decision_boundary"]["automation_allowed"] is False
    assert result["execution"]["patch_attempted"] is False
    assert (tmp_path / "vector" / "failure-vector.json").exists()

    markdown = render_markdown(job, result)
    assert "Local diagnostic job evidence" in markdown
    assert "Current PR decision input: `false`" in markdown
    assert "Safe-fix candidates observed: `1`" in markdown
    assert "Patch application allowed: `false`" in markdown


def test_diagnostic_job_rejects_worker_authority_expansion() -> None:
    job = _job()
    job["worker_contract"]["applies_patch"] = True

    with pytest.raises(ValueError, match="expands authority"):
        validate_job(job)

    job = _job()
    job["decision_boundary"]["semantic_equivalence_proven"] = True

    with pytest.raises(ValueError, match="expands authority"):
        validate_job(job)


def test_diagnostic_job_cli_writes_job_result_vector_and_comment_artifacts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    check_path = tmp_path / "check-intelligence.json"
    check_path.write_text(json.dumps(_formatting_intelligence()), encoding="utf-8")
    out_dir = tmp_path / "job"

    rc = main(
        [
            "--check-intelligence",
            str(check_path),
            "--repo",
            "sherif69-sa/DevS69-sdetkit",
            "--base-sha",
            "base123",
            "--head-sha",
            "head123",
            "--event-name",
            "pull_request",
            "--pr-number",
            "1441",
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    stdout = json.loads(capsys.readouterr().out)
    job = json.loads((out_dir / "diagnostic-job.json").read_text(encoding="utf-8"))
    result = json.loads((out_dir / "diagnostic-worker-result.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "diagnostic-job.md").read_text(encoding="utf-8")

    assert stdout["decision_boundary"]["automation_allowed"] is False
    assert job["event"]["head_sha"] == "head123"
    assert result["summary"]["diagnosis_count"] == 1
    assert (out_dir / "vector" / "diagnostic-vector.json").exists()
    assert (out_dir / "vector" / "failure-vector.json").exists()
    assert "does not execute proof, apply a patch, or authorize a merge" in markdown


def test_diagnostic_job_cli_rejects_declared_missing_evidence_input(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing = tmp_path / "missing-check-intelligence.json"
    out_dir = tmp_path / "job"

    rc = main(
        [
            "--check-intelligence",
            str(missing),
            "--head-sha",
            "head123",
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 2
    assert "declared diagnostic job evidence input is missing" in capsys.readouterr().out
    assert not (out_dir / "diagnostic-worker-result.json").exists()
    assert not (out_dir / "diagnostic-job.md").exists()


def test_diagnostic_worker_surfaces_runtime_guard_violation_as_read_only_review_first_evidence(
    tmp_path: Path,
) -> None:
    result = run_diagnostic_worker(
        _job(),
        runtime_proof_artifacts={
            "isolated_proof": {
                "collection_status": "collected",
                "runtime_guard_checked": True,
                "runtime_guard_passed": False,
                "runtime_guard_violation_count": 1,
            }
        },
        out_dir=tmp_path,
    )

    assert result["summary"]["diagnosis_count"] == 1
    assert result["summary"]["primary_surface"] == "runtime"
    assert result["summary"]["primary_action"] == "review_first_runtime_debug"
    assert result["primary_diagnosis"]["actual_failure"] == (
        "runtime_guard_passed=false; runtime_guard_violation_count=1"
    )
    assert result["primary_diagnosis"]["review_first"] is True
    assert result["primary_diagnosis"]["safe_fix_candidate"] is False
    assert result["decision_boundary"]["current_pr_decision_input"] is False
    assert result["decision_boundary"]["automation_allowed"] is False
    assert result["decision_boundary"]["merge_authorized"] is False

    markdown = render_markdown(_job(), result)
    assert "Primary surface: `runtime`" in markdown
    assert "Primary action: `review_first_runtime_debug`" in markdown
    assert "Runtime guard violation observed" in markdown


def test_diagnostic_worker_does_not_promote_stale_security_evidence_over_current_runtime_guard(
    tmp_path: Path,
) -> None:
    result = run_diagnostic_worker(
        _job(),
        security_review={
            "diagnoses": [
                {
                    "tool": "sdetkit-security-gate",
                    "rule_id": "SEC_HIGH_ENTROPY_STRING",
                    "path": "src/sdetkit/flaky_test_registry_evidence.py",
                    "line": 218,
                    "freshness": "stale",
                    "classification": "stale_or_outdated_alert",
                    "diagnosis": "The alert does not point at the current PR head.",
                    "recommended_action": "wait_for_code_scanning_refresh",
                    "safe_to_auto_fix": False,
                    "automation_allowed": False,
                }
            ]
        },
        runtime_proof_artifacts={
            "isolated_proof": {
                "runtime_guard_checked": True,
                "runtime_guard_passed": False,
                "runtime_guard_violation_count": 1,
            }
        },
        out_dir=tmp_path,
    )

    assert result["summary"]["diagnosis_count"] == 1
    assert result["summary"]["primary_surface"] == "runtime"
    assert result["summary"]["primary_action"] == "review_first_runtime_debug"
    assert result["decision_boundary"]["automation_allowed"] is False
    assert result["decision_boundary"]["merge_authorized"] is False


def test_diagnostic_worker_promotes_current_security_evidence_as_non_authorizing_primary(
    tmp_path: Path,
) -> None:
    result = run_diagnostic_worker(
        _job(),
        security_review={
            "diagnoses": [
                {
                    "tool": "CodeQL",
                    "rule_id": "py/credential-exposure",
                    "path": "src/sdetkit/current_security.py",
                    "line": 7,
                    "freshness": "current",
                    "classification": "codeql_security_review_required",
                    "diagnosis": "A current CodeQL finding requires rule-specific human security review.",
                    "recommended_action": "review_codeql_finding",
                    "safe_to_auto_fix": False,
                    "automation_allowed": False,
                }
            ]
        },
        runtime_proof_artifacts={
            "isolated_proof": {
                "runtime_guard_checked": True,
                "runtime_guard_passed": False,
                "runtime_guard_violation_count": 1,
            }
        },
        out_dir=tmp_path,
    )

    assert result["summary"]["diagnosis_count"] == 2
    assert result["summary"]["primary_surface"] == "security"
    assert result["summary"]["primary_action"] == "review_first_security_review"
    vector = json.loads(
        (tmp_path / "vector" / "diagnostic-vector.json").read_text(encoding="utf-8")
    )
    assert vector["diagnoses"][0]["failure_vector"]["failure_class"] == "security"
    assert result["primary_diagnosis"]["safe_fix_candidate"] is False
    assert result["decision_boundary"]["current_pr_decision_input"] is False
    assert result["decision_boundary"]["automation_allowed"] is False
    assert result["decision_boundary"]["merge_authorized"] is False
