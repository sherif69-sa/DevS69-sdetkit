from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit.diagnostic_job import build_diagnostic_job, run_diagnostic_worker, write_artifacts
from sdetkit.diagnostic_worker_trajectory import (
    SCHEMA_VERSION,
    build_worker_trajectory_records,
    main,
    render_markdown,
)
from sdetkit.diagnostic_worker_trajectory import (
    write_artifacts as write_trajectory_artifacts,
)


def _job() -> dict:
    return build_diagnostic_job(
        repo="sherif69-sa/DevS69-sdetkit",
        base_sha="base123",
        head_sha="head123",
        event_name="pull_request",
        pr_number=1443,
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


def _worker_payloads(tmp_path: Path) -> tuple[dict, dict, dict]:
    job = _job()
    result = run_diagnostic_worker(
        job,
        check_intelligence=_formatting_intelligence(),
        out_dir=tmp_path / "worker",
    )
    vector = json.loads(
        (tmp_path / "worker" / "vector" / "diagnostic-vector.json").read_text(encoding="utf-8")
    )
    return job, result, vector


def test_worker_trajectory_records_observed_candidates_as_advisory_only(tmp_path: Path) -> None:
    job, result, vector = _worker_payloads(tmp_path)
    records = build_worker_trajectory_records(
        job=job,
        worker_result=result,
        diagnostic_vector=vector,
        repo="sherif69-sa/DevS69-sdetkit",
        branch="feature/diagnostic-worker-advisory-trajectory",
        commit_sha="head123",
        pr_number=1443,
    )

    assert len(records) == 1
    record = records[0]
    assert record["environment"]["source"] == "diagnostic_worker_result"
    assert record["action"] == "record_diagnostic_worker_observation"
    assert record["decision"]["review_first"] is True
    assert record["decision"]["auto_fix_allowed"] is False
    assert record["fix"]["patch_files"] == []
    assert record["proof"]["commands"] == []
    assert record["final_result"] == "advisory_observation_recorded"
    assert record["worker_evidence"]["observed_safe_fix_candidate"] is True
    assert record["worker_evidence"]["reporting_only"] is True
    assert record["worker_evidence"]["current_pr_decision_input"] is False
    assert record["worker_evidence"]["automation_allowed"] is False
    assert record["worker_evidence"]["merge_authorized"] is False


def test_worker_trajectory_rejects_result_authority_or_mismatched_vector(tmp_path: Path) -> None:
    job, result, vector = _worker_payloads(tmp_path)

    result["decision_boundary"]["automation_allowed"] = True
    with pytest.raises(ValueError, match="worker result expands authority"):
        build_worker_trajectory_records(
            job=job,
            worker_result=result,
            diagnostic_vector=vector,
        )

    job, result, vector = _worker_payloads(tmp_path / "second")
    vector["summary"]["diagnosis_count"] = 99
    with pytest.raises(ValueError, match="summary does not match diagnostic vector"):
        build_worker_trajectory_records(
            job=job,
            worker_result=result,
            diagnostic_vector=vector,
        )


def test_worker_trajectory_artifacts_render_reporting_only_boundary(tmp_path: Path) -> None:
    job, result, vector = _worker_payloads(tmp_path)
    records = build_worker_trajectory_records(
        job=job,
        worker_result=result,
        diagnostic_vector=vector,
    )
    payload = write_trajectory_artifacts(
        records,
        worker_result=result,
        out_dir=tmp_path / "trajectory",
    )
    summary = payload["summary"]

    assert summary["schema_version"] == SCHEMA_VERSION
    assert summary["record_count"] == 1
    assert summary["observed_safe_fix_candidate_count"] == 1
    assert summary["reporting_only"] is True
    assert summary["current_pr_decision_input"] is False
    assert summary["patch_application_allowed"] is False
    assert summary["automation_allowed"] is False
    assert summary["merge_authorized"] is False

    markdown = render_markdown(summary)
    assert "Local diagnostic worker trajectory handoff" in markdown
    assert "Reporting only: `true`" in markdown
    assert "Current PR decision input: `false`" in markdown
    assert "not consumed by current-run candidate decisions or RepoMemory" in markdown


def test_worker_trajectory_cli_writes_separate_jsonl_without_decision_authority(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    job, result, vector = _worker_payloads(tmp_path)
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    write_artifacts(job, result, out_dir=input_dir)
    vector_path = tmp_path / "worker" / "vector" / "diagnostic-vector.json"
    out_dir = tmp_path / "trajectory-out"

    rc = main(
        [
            "--diagnostic-job",
            str(input_dir / "diagnostic-job.json"),
            "--diagnostic-worker-result",
            str(input_dir / "diagnostic-worker-result.json"),
            "--diagnostic-vector",
            str(vector_path),
            "--repo",
            "sherif69-sa/DevS69-sdetkit",
            "--branch",
            "feature/diagnostic-worker-advisory-trajectory",
            "--commit-sha",
            "head123",
            "--pr-number",
            "1443",
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["summary"]["reporting_only"] is True
    assert printed["summary"]["automation_allowed"] is False
    record = json.loads(
        (out_dir / "diagnostic-worker-trajectory.jsonl").read_text(encoding="utf-8")
    )
    assert record["decision"]["auto_fix_allowed"] is False
    assert (out_dir / "diagnostic-worker-trajectory-summary.json").exists()
    assert (out_dir / "diagnostic-worker-trajectory.md").exists()
