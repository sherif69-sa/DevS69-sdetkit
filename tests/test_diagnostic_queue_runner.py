from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit.diagnostic_job import build_diagnostic_job
from sdetkit.diagnostic_queue_runner import (
    SCHEMA_VERSION,
    run_bounded_diagnostic_queue,
)
from sdetkit.job_queue import (
    COMPLETED,
    FAILED,
    PENDING,
    enqueue_job,
    load_queue,
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
                    "line": ("ruff format..............................Failed"),
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
        pr_number=1773,
        input_artifacts=input_artifacts,
        generated_at=created_at,
    )


def _states(queue_path: Path) -> dict[str, str]:
    return {record["job_id"]: record["state"] for record in load_queue(queue_path)["jobs"]}


@pytest.mark.parametrize(
    "max_jobs",
    [
        0,
        -1,
        True,
    ],
)
def test_runner_rejects_invalid_max_jobs(
    tmp_path: Path,
    max_jobs: int,
) -> None:
    with pytest.raises(
        ValueError,
        match="positive integer max_jobs",
    ):
        run_bounded_diagnostic_queue(
            tmp_path / "queue.json",
            max_jobs=max_jobs,
            claimed_at="2026-06-14T01:00:00Z",
            finished_at="2026-06-14T02:00:00Z",
            out_root=tmp_path / "worker",
        )


def test_runner_rejects_missing_timestamps(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match="requires claimed_at",
    ):
        run_bounded_diagnostic_queue(
            tmp_path / "queue.json",
            max_jobs=1,
            claimed_at="",
            finished_at="2026-06-14T02:00:00Z",
            out_root=tmp_path / "worker",
        )

    with pytest.raises(
        ValueError,
        match="requires finished_at",
    ):
        run_bounded_diagnostic_queue(
            tmp_path / "queue.json",
            max_jobs=1,
            claimed_at="2026-06-14T01:00:00Z",
            finished_at="",
            out_root=tmp_path / "worker",
        )


def test_empty_queue_stops_cleanly(
    tmp_path: Path,
) -> None:
    result = run_bounded_diagnostic_queue(
        tmp_path / "queue.json",
        max_jobs=3,
        claimed_at="2026-06-14T01:00:00Z",
        finished_at="2026-06-14T02:00:00Z",
        out_root=tmp_path / "worker",
    )

    assert result["schema_version"] == SCHEMA_VERSION
    assert result["status"] == "completed"
    assert result["stop_reason"] == "no_pending_jobs"
    assert result["jobs_attempted"] == 0
    assert result["jobs_completed"] == 0
    assert result["jobs_failed"] == 0
    assert result["successful_results"] == []
    assert result["failure"] == {}

    assert result["queue_state_counts"] == {
        "pending": 0,
        "claimed": 0,
        "completed": 0,
        "failed": 0,
    }

    assert result["decision_boundary"]["automation_allowed"] is False
    assert result["decision_boundary"]["patch_application_allowed"] is False
    assert result["decision_boundary"]["merge_authorized"] is False
    assert result["execution"]["automatic_retry"] is False


def test_runner_processes_no_more_than_max_jobs(
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
    third = _job(
        head_sha="third",
        created_at="2026-06-14T03:00:00Z",
        input_artifacts={
            "check_intelligence": str(input_path),
        },
    )

    enqueue_job(queue_path, third)
    enqueue_job(queue_path, second)
    enqueue_job(queue_path, first)

    result = run_bounded_diagnostic_queue(
        queue_path,
        max_jobs=2,
        claimed_at="2026-06-14T04:00:00Z",
        finished_at="2026-06-14T05:00:00Z",
        out_root=tmp_path / "worker",
    )

    assert result["status"] == "completed"
    assert result["stop_reason"] == "max_jobs_reached"
    assert result["jobs_attempted"] == 2
    assert result["jobs_completed"] == 2
    assert result["jobs_failed"] == 0

    assert [item["job_id"] for item in result["successful_results"]] == [
        first["job_id"],
        second["job_id"],
    ]

    states = _states(queue_path)

    assert states[first["job_id"]] == COMPLETED
    assert states[second["job_id"]] == COMPLETED
    assert states[third["job_id"]] == PENDING

    assert result["queue_state_counts"] == {
        "pending": 1,
        "claimed": 0,
        "completed": 2,
        "failed": 0,
    }


def test_runner_stops_cleanly_after_draining_queue(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "queue.json"
    input_path = tmp_path / "check-intelligence.json"

    input_path.write_text(
        json.dumps(_formatting_intelligence()),
        encoding="utf-8",
    )

    job = _job(
        head_sha="single",
        created_at="2026-06-14T01:00:00Z",
        input_artifacts={
            "check_intelligence": str(input_path),
        },
    )

    enqueue_job(queue_path, job)

    result = run_bounded_diagnostic_queue(
        queue_path,
        max_jobs=3,
        claimed_at="2026-06-14T02:00:00Z",
        finished_at="2026-06-14T03:00:00Z",
        out_root=tmp_path / "worker",
    )

    assert result["status"] == "completed"
    assert result["stop_reason"] == "no_pending_jobs"
    assert result["jobs_attempted"] == 1
    assert result["jobs_completed"] == 1
    assert result["jobs_failed"] == 0

    assert _states(queue_path)[job["job_id"]] == COMPLETED


def test_runner_stops_after_first_failed_job_without_retry(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "queue.json"
    valid_input = tmp_path / "valid.json"

    valid_input.write_text(
        json.dumps(_formatting_intelligence()),
        encoding="utf-8",
    )

    failing = _job(
        head_sha="failing",
        created_at="2026-06-14T01:00:00Z",
        input_artifacts={
            "check_intelligence": "missing.json",
        },
    )
    later = _job(
        head_sha="later",
        created_at="2026-06-14T02:00:00Z",
        input_artifacts={
            "check_intelligence": str(valid_input),
        },
    )

    enqueue_job(queue_path, later)
    enqueue_job(queue_path, failing)

    result = run_bounded_diagnostic_queue(
        queue_path,
        max_jobs=5,
        claimed_at="2026-06-14T03:00:00Z",
        finished_at="2026-06-14T04:00:00Z",
        out_root=tmp_path / "worker",
        input_root=tmp_path,
    )

    assert result["status"] == "failed"
    assert result["stop_reason"] == "job_failed"
    assert result["jobs_attempted"] == 1
    assert result["jobs_completed"] == 0
    assert result["jobs_failed"] == 1
    assert result["successful_results"] == []

    assert result["failure"]["job_id"] == failing["job_id"]
    assert result["failure"]["exception_type"] == "ValueError"
    assert "evidence input is missing" in result["failure"]["message"]

    states = _states(queue_path)

    assert states[failing["job_id"]] == FAILED
    assert states[later["job_id"]] == PENDING

    assert result["queue_state_counts"] == {
        "pending": 1,
        "claimed": 0,
        "completed": 0,
        "failed": 1,
    }

    assert result["execution"]["automatic_retry"] is False
    assert result["execution"]["proof_commands_executed"] is False
    assert result["execution"]["patch_attempted"] is False
    assert result["execution"]["merge_authorized"] is False
