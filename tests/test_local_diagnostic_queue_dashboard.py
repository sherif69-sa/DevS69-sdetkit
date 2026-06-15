from __future__ import annotations

import json
from pathlib import Path

from sdetkit.diagnostic_job import build_diagnostic_job
from sdetkit.job_queue import (
    CLAIMED,
    COMPLETED,
    FAILED,
    PENDING,
    claim_job,
    complete_job,
    enqueue_job,
    fail_job,
)
from sdetkit.local_diagnostic_queue_dashboard import (
    SCHEMA_VERSION,
    build_dashboard,
    main,
    render_html,
)


def _job(*, head_sha: str, created_at: str, pr_number: int) -> dict[str, object]:
    return build_diagnostic_job(
        repo="sherif69-sa/DevS69-sdetkit",
        base_sha="base123",
        head_sha=head_sha,
        event_name="pull_request",
        pr_number=pr_number,
        input_artifacts={"check_intelligence": "check-intelligence.json"},
        generated_at=created_at,
    )


def test_dashboard_summarizes_validated_queue_and_artifact_links(tmp_path: Path) -> None:
    queue_path = tmp_path / "queue.json"
    out_path = tmp_path / "dashboard.html"

    pending = _job(
        head_sha="pending-head",
        created_at="2026-06-15T00:00:00Z",
        pr_number=1779,
    )
    completed = _job(
        head_sha="completed-head",
        created_at="2026-06-15T00:01:00Z",
        pr_number=1780,
    )
    failed = _job(
        head_sha="failed-head",
        created_at="2026-06-15T00:02:00Z",
        pr_number=1781,
    )

    enqueue_job(queue_path, pending, enqueued_at="2026-06-15T00:00:00Z")
    enqueue_job(queue_path, completed, enqueued_at="2026-06-15T00:01:00Z")
    enqueue_job(queue_path, failed, enqueued_at="2026-06-15T00:02:00Z")

    claim_job(
        queue_path,
        job_id=str(completed["job_id"]),
        claimed_at="2026-06-15T01:00:00Z",
    )
    worker_result = tmp_path / "worker" / "result.json"
    worker_result.parent.mkdir()
    worker_result.write_text("{}\n", encoding="utf-8")
    complete_job(
        queue_path,
        str(completed["job_id"]),
        result_artifacts={"worker_result": worker_result.as_posix()},
        completed_at="2026-06-15T02:00:00Z",
    )

    claim_job(
        queue_path,
        job_id=str(failed["job_id"]),
        claimed_at="2026-06-15T01:01:00Z",
    )
    fail_job(
        queue_path,
        str(failed["job_id"]),
        reason="<script>alert('unsafe')</script>",
        failed_at="2026-06-15T02:01:00Z",
    )

    payload = build_dashboard(queue_path, out_path=out_path)

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["status"] == "ready"
    assert payload["queue_exists"] is True
    assert payload["local_only"] is True
    assert payload["read_only"] is True
    assert payload["job_count"] == 3
    assert payload["state_counts"] == {
        PENDING: 1,
        CLAIMED: 0,
        COMPLETED: 1,
        FAILED: 1,
    }
    assert payload["artifact_count"] == 1
    assert payload["present_artifact_count"] == 1
    assert payload["missing_artifact_count"] == 0

    jobs = payload["jobs"]
    assert [row["job_id"] for row in jobs] == [
        pending["job_id"],
        completed["job_id"],
        failed["job_id"],
    ]
    assert jobs[1]["state"] == COMPLETED
    assert jobs[1]["artifact_count"] == 1
    assert jobs[1]["artifacts"][0]["present"] is True
    assert jobs[1]["artifacts"][0]["name"] == "worker_result"

    assert payload["decision_boundary"] == {
        "current_pr_decision_input": False,
        "automation_allowed": False,
        "automatic_retry": False,
        "proof_commands_executed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }

    rendered = render_html(payload)
    assert "Local diagnostic queue dashboard" in rendered
    assert "local only: true" in rendered
    assert "read only: true" in rendered
    assert "&lt;script&gt;" in rendered
    assert "<script>alert" not in rendered


def test_dashboard_marks_missing_result_artifacts(tmp_path: Path) -> None:
    queue_path = tmp_path / "queue.json"
    out_path = tmp_path / "dashboard.html"
    job = _job(
        head_sha="missing-artifact",
        created_at="2026-06-15T00:00:00Z",
        pr_number=1779,
    )
    enqueue_job(queue_path, job, enqueued_at="2026-06-15T00:00:00Z")
    claim_job(
        queue_path,
        job_id=str(job["job_id"]),
        claimed_at="2026-06-15T01:00:00Z",
    )
    complete_job(
        queue_path,
        str(job["job_id"]),
        result_artifacts={"worker_result": (tmp_path / "missing-worker-result.json").as_posix()},
        completed_at="2026-06-15T02:00:00Z",
    )

    payload = build_dashboard(queue_path, out_path=out_path)
    assert payload["artifact_count"] == 1
    assert payload["present_artifact_count"] == 0
    assert payload["missing_artifact_count"] == 1
    assert payload["jobs"][0]["artifacts"][0]["present"] is False


def test_json_cli_is_deterministic_and_does_not_mutate_queue(tmp_path: Path) -> None:
    queue_path = tmp_path / "queue.json"
    out_path = tmp_path / "dashboard.json"
    job = _job(
        head_sha="json-cli",
        created_at="2026-06-15T00:00:00Z",
        pr_number=1779,
    )
    enqueue_job(queue_path, job, enqueued_at="2026-06-15T00:00:00Z")
    before = queue_path.read_text(encoding="utf-8")

    rc = main(
        [
            "--queue-path",
            str(queue_path),
            "--format",
            "json",
            "--out",
            str(out_path),
        ]
    )

    assert rc == 0
    assert queue_path.read_text(encoding="utf-8") == before
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert out_path.read_text(encoding="utf-8") == (
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    assert payload["job_count"] == 1
    assert payload["state_counts"][PENDING] == 1


def test_missing_queue_renders_valid_empty_dashboard(tmp_path: Path) -> None:
    queue_path = tmp_path / "missing-queue.json"
    out_path = tmp_path / "dashboard.html"

    rc = main(
        [
            "--queue-path",
            str(queue_path),
            "--format",
            "html",
            "--out",
            str(out_path),
        ]
    )

    assert rc == 0
    assert queue_path.exists() is False
    text = out_path.read_text(encoding="utf-8")
    assert "No queued jobs" in text
    assert "status: empty" in text
    assert "read only: true" in text
