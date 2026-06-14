from __future__ import annotations

import json
from pathlib import Path

import pytest

import sdetkit.queued_diagnostic_worker as queued_worker
from sdetkit.diagnostic_job import build_diagnostic_job
from sdetkit.job_queue import (
    COMPLETED,
    FAILED,
    PENDING,
    enqueue_job,
    load_queue,
)
from sdetkit.queued_diagnostic_worker import (
    SCHEMA_VERSION,
    run_queued_diagnostic_job,
)


def _formatting_intelligence() -> dict:
    return {
        "failed_checks": [
            {
                "name": "PR Quality local quality gate",
                "surface": "formatting",
                "command": "python -m pre_commit run -a",
                "scope": "pr_owned_only",
                "diagnosis": {
                    "title": "Pre-commit formatting drift",
                    "surface": "formatting",
                },
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
                    "affected_files": [
                        "src/sdetkit/example.py",
                    ],
                },
                "affected_files": [
                    "src/sdetkit/example.py",
                ],
            }
        ]
    }


def _job(
    *,
    head_sha: str,
    created_at: str,
    input_artifacts: dict[str, str],
) -> dict:
    return build_diagnostic_job(
        repo="sherif69-sa/DevS69-sdetkit",
        base_sha="base123",
        head_sha=head_sha,
        event_name="pull_request",
        pr_number=1772,
        input_artifacts=input_artifacts,
        generated_at=created_at,
    )


def test_queued_worker_claims_runs_and_completes_job(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "queue.json"
    input_path = tmp_path / "check-intelligence.json"

    input_path.write_text(
        json.dumps(_formatting_intelligence()),
        encoding="utf-8",
    )

    job = _job(
        head_sha="head123",
        created_at="2026-06-14T00:00:00Z",
        input_artifacts={
            "check_intelligence": str(input_path),
        },
    )

    enqueue_job(queue_path, job)

    result = run_queued_diagnostic_job(
        queue_path,
        claimed_at="2026-06-14T01:00:00Z",
        finished_at="2026-06-14T02:00:00Z",
        out_root=tmp_path / "worker",
    )

    assert result["schema_version"] == SCHEMA_VERSION
    assert result["status"] == "completed"
    assert result["job_id"] == job["job_id"]
    assert result["worker_result"]["summary"]["diagnosis_count"] == 1
    assert result["worker_result"]["primary_diagnosis"]["failure_surface"] == "formatting"

    assert result["decision_boundary"]["automation_allowed"] is False
    assert result["decision_boundary"]["patch_application_allowed"] is False
    assert result["decision_boundary"]["merge_authorized"] is False
    assert result["execution"]["automatic_retry"] is False
    assert result["execution"]["proof_commands_executed"] is False
    assert result["execution"]["patch_attempted"] is False

    queue = load_queue(queue_path)
    record = queue["jobs"][0]

    assert record["state"] == COMPLETED
    assert record["result_artifacts"]["worker_result"].endswith("diagnostic-worker-result.json")

    result_path = tmp_path / "worker" / job["job_id"] / "diagnostic-worker-result.json"
    vector_path = tmp_path / "worker" / job["job_id"] / "vector" / "diagnostic-vector.json"

    assert result_path.exists()
    assert vector_path.exists()


def test_queued_worker_uses_queue_order_when_job_id_is_omitted(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "queue.json"
    input_path = tmp_path / "check-intelligence.json"

    input_path.write_text(
        json.dumps(_formatting_intelligence()),
        encoding="utf-8",
    )

    later = _job(
        head_sha="later",
        created_at="2026-06-14T02:00:00Z",
        input_artifacts={
            "check_intelligence": str(input_path),
        },
    )
    earlier = _job(
        head_sha="earlier",
        created_at="2026-06-14T01:00:00Z",
        input_artifacts={
            "check_intelligence": str(input_path),
        },
    )

    enqueue_job(queue_path, later)
    enqueue_job(queue_path, earlier)

    result = run_queued_diagnostic_job(
        queue_path,
        claimed_at="2026-06-14T03:00:00Z",
        finished_at="2026-06-14T04:00:00Z",
        out_root=tmp_path / "worker",
    )

    assert result["job_id"] == earlier["job_id"]

    states = {record["job_id"]: record["state"] for record in load_queue(queue_path)["jobs"]}

    assert states[earlier["job_id"]] == COMPLETED
    assert states[later["job_id"]] == PENDING


def test_queued_worker_can_process_a_specific_pending_job(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "queue.json"
    input_path = tmp_path / "check-intelligence.json"

    input_path.write_text(
        json.dumps(_formatting_intelligence()),
        encoding="utf-8",
    )

    first = _job(
        head_sha="first",
        created_at="2026-06-14T01:00:00Z",
        input_artifacts={
            "check_intelligence": str(input_path),
        },
    )
    second = _job(
        head_sha="second",
        created_at="2026-06-14T02:00:00Z",
        input_artifacts={
            "check_intelligence": str(input_path),
        },
    )

    enqueue_job(queue_path, first)
    enqueue_job(queue_path, second)

    result = run_queued_diagnostic_job(
        queue_path,
        claimed_at="2026-06-14T03:00:00Z",
        finished_at="2026-06-14T04:00:00Z",
        out_root=tmp_path / "worker",
        job_id=second["job_id"],
    )

    assert result["job_id"] == second["job_id"]

    states = {record["job_id"]: record["state"] for record in load_queue(queue_path)["jobs"]}

    assert states[first["job_id"]] == PENDING
    assert states[second["job_id"]] == COMPLETED


def test_missing_declared_input_marks_claimed_job_failed(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "queue.json"

    job = _job(
        head_sha="missing",
        created_at="2026-06-14T00:00:00Z",
        input_artifacts={
            "check_intelligence": "missing.json",
        },
    )

    enqueue_job(queue_path, job)

    with pytest.raises(
        ValueError,
        match="evidence input is missing",
    ):
        run_queued_diagnostic_job(
            queue_path,
            claimed_at="2026-06-14T01:00:00Z",
            finished_at="2026-06-14T02:00:00Z",
            out_root=tmp_path / "worker",
            input_root=tmp_path,
        )

    record = load_queue(queue_path)["jobs"][0]

    assert record["state"] == FAILED
    assert "ValueError" in record["failure_reason"]
    assert "evidence input is missing" in record["failure_reason"]


def test_unsupported_input_marks_job_failed_without_retry(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "queue.json"
    unknown_path = tmp_path / "unknown.json"

    unknown_path.write_text(
        "{}",
        encoding="utf-8",
    )

    job = _job(
        head_sha="unsupported",
        created_at="2026-06-14T00:00:00Z",
        input_artifacts={
            "unsupported_input": str(unknown_path),
        },
    )

    enqueue_job(queue_path, job)

    with pytest.raises(
        ValueError,
        match="unsupported evidence inputs",
    ):
        run_queued_diagnostic_job(
            queue_path,
            claimed_at="2026-06-14T01:00:00Z",
            finished_at="2026-06-14T02:00:00Z",
            out_root=tmp_path / "worker",
        )

    record = load_queue(queue_path)["jobs"][0]

    assert record["state"] == FAILED

    with pytest.raises(
        ValueError,
        match="only be claimed from pending state",
    ):
        run_queued_diagnostic_job(
            queue_path,
            claimed_at="2026-06-14T03:00:00Z",
            finished_at="2026-06-14T04:00:00Z",
            out_root=tmp_path / "worker",
            job_id=job["job_id"],
        )


def test_worker_exception_marks_job_failed_and_is_reraised(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue_path = tmp_path / "queue.json"
    input_path = tmp_path / "check-intelligence.json"

    input_path.write_text(
        json.dumps(_formatting_intelligence()),
        encoding="utf-8",
    )

    job = _job(
        head_sha="worker-error",
        created_at="2026-06-14T00:00:00Z",
        input_artifacts={
            "check_intelligence": str(input_path),
        },
    )

    enqueue_job(queue_path, job)

    def fail_worker(
        *args: object,
        **kwargs: object,
    ) -> dict:
        raise RuntimeError("bounded worker failure")

    monkeypatch.setattr(
        queued_worker,
        "run_diagnostic_worker",
        fail_worker,
    )

    with pytest.raises(
        RuntimeError,
        match="bounded worker failure",
    ):
        run_queued_diagnostic_job(
            queue_path,
            claimed_at="2026-06-14T01:00:00Z",
            finished_at="2026-06-14T02:00:00Z",
            out_root=tmp_path / "worker",
        )

    record = load_queue(queue_path)["jobs"][0]

    assert record["state"] == FAILED
    assert record["failure_reason"] == "RuntimeError: bounded worker failure"
