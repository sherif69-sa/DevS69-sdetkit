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
