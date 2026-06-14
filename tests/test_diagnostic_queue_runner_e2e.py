from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from sdetkit.diagnostic_job import build_diagnostic_job
from sdetkit.job_queue import (
    COMPLETED,
    FAILED,
    PENDING,
    enqueue_job,
    load_queue,
)


def _formatting_intelligence() -> dict[str, Any]:
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
) -> dict[str, Any]:
    return build_diagnostic_job(
        repo="sherif69-sa/DevS69-sdetkit",
        base_sha="base123",
        head_sha=head_sha,
        event_name="pull_request",
        pr_number=1776,
        input_artifacts=input_artifacts,
        generated_at=created_at,
    )


def _run_cli(
    *,
    queue_path: Path,
    out_root: Path,
    input_root: Path,
    max_jobs: int,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "sdetkit.diagnostic_queue_runner_cli",
            "--queue-path",
            str(queue_path),
            "--out-root",
            str(out_root),
            "--input-root",
            str(input_root),
            "--max-jobs",
            str(max_jobs),
            "--claimed-at",
            "2026-06-15T01:00:00Z",
            "--finished-at",
            "2026-06-15T02:00:00Z",
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def _json_stdout(
    completed: subprocess.CompletedProcess[str],
) -> dict[str, Any]:
    payload = json.loads(completed.stdout)

    assert completed.stdout == (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    return payload


def test_module_cli_processes_real_queue_worker_and_trajectory(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "queue.json"
    input_root = tmp_path / "inputs"
    out_root = tmp_path / "worker"

    input_root.mkdir()

    input_path = input_root / "check-intelligence.json"
    input_path.write_text(
        json.dumps(
            _formatting_intelligence(),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    job = _job(
        head_sha="e2e-success",
        created_at="2026-06-15T00:00:00Z",
        input_artifacts={
            "check_intelligence": input_path.name,
        },
    )

    enqueue_job(
        queue_path,
        job,
    )

    completed = _run_cli(
        queue_path=queue_path,
        out_root=out_root,
        input_root=input_root,
        max_jobs=2,
    )

    assert completed.returncode == 0
    assert completed.stderr == ""

    payload = _json_stdout(completed)

    assert payload["status"] == "completed"
    assert payload["stop_reason"] == "no_pending_jobs"
    assert payload["max_jobs"] == 2
    assert payload["jobs_attempted"] == 1
    assert payload["jobs_completed"] == 1
    assert payload["jobs_failed"] == 0

    assert payload["execution"]["automatic_retry"] is False
    assert payload["decision_boundary"]["merge_authorized"] is False

    successful = payload["successful_results"]

    assert len(successful) == 1
    assert successful[0]["job_id"] == job["job_id"]
    assert successful[0]["status"] == "completed"

    trajectory = successful[0]["trajectory"]["summary"]

    assert trajectory["status"] == "recorded"
    assert trajectory["reporting_only"] is True
    assert trajectory["current_pr_decision_input"] is False
    assert trajectory["automation_allowed"] is False
    assert trajectory["merge_authorized"] is False

    queue = load_queue(queue_path)

    assert len(queue["jobs"]) == 1

    record = queue["jobs"][0]

    assert record["job_id"] == job["job_id"]
    assert record["state"] == COMPLETED
    assert record["claimed_at"] == "2026-06-15T01:00:00Z"
    assert record["completed_at"] == "2026-06-15T02:00:00Z"

    required_artifacts = {
        "worker_result",
        "diagnostic_worker_trajectory_jsonl",
        "diagnostic_worker_trajectory_summary_json",
        "diagnostic_worker_trajectory_markdown",
    }

    assert required_artifacts <= set(record["result_artifacts"])

    for artifact_name in required_artifacts:
        artifact_path = Path(record["result_artifacts"][artifact_name])
        assert artifact_path.exists()
        assert artifact_path.is_file()

    trajectory_summary_path = Path(
        record["result_artifacts"]["diagnostic_worker_trajectory_summary_json"]
    )
    trajectory_summary = json.loads(trajectory_summary_path.read_text(encoding="utf-8"))

    assert trajectory_summary["reporting_only"] is True
    assert trajectory_summary["current_pr_decision_input"] is False
    assert trajectory_summary["automation_allowed"] is False
    assert trajectory_summary["merge_authorized"] is False

    trajectory_jsonl_path = Path(record["result_artifacts"]["diagnostic_worker_trajectory_jsonl"])
    trajectory_lines = trajectory_jsonl_path.read_text(encoding="utf-8").splitlines()

    assert len(trajectory_lines) == 1

    trajectory_record = json.loads(trajectory_lines[0])

    assert trajectory_record["decision"]["review_first"] is True
    assert trajectory_record["decision"]["auto_fix_allowed"] is False
    assert trajectory_record["proof"]["commands"] == []
    assert trajectory_record["worker_evidence"]["reporting_only"] is True


def test_module_cli_stops_after_real_failed_job_without_retry(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "queue.json"
    input_root = tmp_path / "inputs"
    out_root = tmp_path / "worker"

    input_root.mkdir()

    valid_path = input_root / "valid.json"
    valid_path.write_text(
        json.dumps(
            _formatting_intelligence(),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    failing = _job(
        head_sha="e2e-failing",
        created_at="2026-06-15T00:00:00Z",
        input_artifacts={
            "check_intelligence": "missing.json",
        },
    )
    later = _job(
        head_sha="e2e-later",
        created_at="2026-06-15T00:01:00Z",
        input_artifacts={
            "check_intelligence": valid_path.name,
        },
    )

    enqueue_job(
        queue_path,
        later,
    )
    enqueue_job(
        queue_path,
        failing,
    )

    completed = _run_cli(
        queue_path=queue_path,
        out_root=out_root,
        input_root=input_root,
        max_jobs=3,
    )

    assert completed.returncode == 1
    assert completed.stderr == ""

    payload = _json_stdout(completed)

    assert payload["status"] == "failed"
    assert payload["stop_reason"] == "job_failed"
    assert payload["max_jobs"] == 3
    assert payload["jobs_attempted"] == 1
    assert payload["jobs_completed"] == 0
    assert payload["jobs_failed"] == 1
    assert payload["successful_results"] == []

    assert payload["failure"]["job_id"] == failing["job_id"]
    assert payload["failure"]["exception_type"] == "ValueError"
    assert "evidence input is missing" in payload["failure"]["message"]

    assert payload["execution"]["automatic_retry"] is False
    assert payload["execution"]["proof_commands_executed"] is False
    assert payload["execution"]["patch_attempted"] is False
    assert payload["execution"]["merge_authorized"] is False

    states = {record["job_id"]: record["state"] for record in load_queue(queue_path)["jobs"]}

    assert states[failing["job_id"]] == FAILED
    assert states[later["job_id"]] == PENDING

    assert not (out_root / later["job_id"]).exists()
