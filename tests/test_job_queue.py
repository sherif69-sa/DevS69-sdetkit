from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit.diagnostic_job import build_diagnostic_job
from sdetkit.job_queue import (
    CLAIMED,
    COMPLETED,
    FAILED,
    PENDING,
    SCHEMA_VERSION,
    claim_job,
    complete_job,
    enqueue_job,
    fail_job,
    load_queue,
)


def _job(*, head_sha: str, created_at: str) -> dict:
    return build_diagnostic_job(
        repo="sherif69-sa/DevS69-sdetkit",
        base_sha="base123",
        head_sha=head_sha,
        event_name="pull_request",
        pr_number=1771,
        input_artifacts={"check_intelligence": "build/check-intelligence.json"},
        generated_at=created_at,
    )


def test_enqueue_is_deterministic_file_backed_and_read_only(tmp_path: Path) -> None:
    first_path = tmp_path / "first" / "queue.json"
    second_path = tmp_path / "second" / "queue.json"
    job = _job(head_sha="head123", created_at="2026-06-14T00:00:00Z")

    first_record = enqueue_job(first_path, job)
    second_record = enqueue_job(second_path, job)

    assert first_record == second_record
    assert first_path.read_bytes() == second_path.read_bytes()

    queue = load_queue(first_path)
    assert queue["schema_version"] == SCHEMA_VERSION
    assert queue["execution_mode"] == "local_read_only"
    assert queue["jobs"][0]["state"] == PENDING
    assert queue["jobs"][0]["job"] == job
    assert queue["decision_boundary"] == {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "proof_commands_executed": False,
    }


def test_enqueue_rejects_duplicate_job_id(tmp_path: Path) -> None:
    path = tmp_path / "queue.json"
    job = _job(head_sha="head123", created_at="2026-06-14T00:00:00Z")

    enqueue_job(path, job)

    with pytest.raises(ValueError, match="duplicate diagnostic queue job"):
        enqueue_job(path, job)


def test_claim_order_is_created_at_then_job_id(tmp_path: Path) -> None:
    path = tmp_path / "queue.json"
    later = _job(head_sha="later", created_at="2026-06-14T02:00:00Z")
    earlier_b = _job(head_sha="earlier-b", created_at="2026-06-14T01:00:00Z")
    earlier_a = _job(head_sha="earlier-a", created_at="2026-06-14T01:00:00Z")

    enqueue_job(path, later)
    enqueue_job(path, earlier_b)
    enqueue_job(path, earlier_a)

    expected_first = min(
        (earlier_a, earlier_b),
        key=lambda job: str(job["job_id"]),
    )

    claimed = claim_job(path, claimed_at="2026-06-14T03:00:00Z")
    assert claimed["job_id"] == expected_first["job_id"]
    assert claimed["state"] == CLAIMED

    queue = load_queue(path)
    sort_projection = [(record["job"]["created_at"], record["job_id"]) for record in queue["jobs"]]
    assert sort_projection == sorted(sort_projection)


def test_unknown_and_invalid_state_transitions_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "queue.json"
    job = _job(head_sha="head123", created_at="2026-06-14T00:00:00Z")
    enqueue_job(path, job)

    with pytest.raises(ValueError, match="unknown diagnostic queue job"):
        claim_job(
            path,
            job_id="diagnostic-job-unknown",
            claimed_at="2026-06-14T01:00:00Z",
        )

    with pytest.raises(ValueError, match="only complete from claimed state"):
        complete_job(
            path,
            job["job_id"],
            result_artifacts={"worker_result": "build/result.json"},
            completed_at="2026-06-14T02:00:00Z",
        )

    with pytest.raises(ValueError, match="only fail from claimed state"):
        fail_job(
            path,
            job["job_id"],
            reason="worker failed",
            failed_at="2026-06-14T02:00:00Z",
        )


def test_completed_job_records_artifacts_and_cannot_be_reclaimed(tmp_path: Path) -> None:
    path = tmp_path / "queue.json"
    job = _job(head_sha="head123", created_at="2026-06-14T00:00:00Z")
    enqueue_job(path, job)
    claim_job(
        path,
        job_id=job["job_id"],
        claimed_at="2026-06-14T01:00:00Z",
    )

    completed = complete_job(
        path,
        job["job_id"],
        result_artifacts={
            "worker_result": "build/diagnostic-worker-result.json",
            "vector": "build/vector/diagnostic-vector.json",
        },
        completed_at="2026-06-14T02:00:00Z",
    )

    assert completed["state"] == COMPLETED
    assert completed["result_artifacts"] == {
        "vector": "build/vector/diagnostic-vector.json",
        "worker_result": "build/diagnostic-worker-result.json",
    }

    with pytest.raises(ValueError, match="only be claimed from pending state"):
        claim_job(
            path,
            job_id=job["job_id"],
            claimed_at="2026-06-14T03:00:00Z",
        )


def test_failed_job_sanitizes_reason_and_cannot_be_reclaimed(tmp_path: Path) -> None:
    path = tmp_path / "queue.json"
    job = _job(head_sha="head123", created_at="2026-06-14T00:00:00Z")
    enqueue_job(path, job)
    claim_job(
        path,
        job_id=job["job_id"],
        claimed_at="2026-06-14T01:00:00Z",
    )

    failed = fail_job(
        path,
        job["job_id"],
        reason="  worker\nfailed\rwithout repository mutation  ",
        failed_at="2026-06-14T02:00:00Z",
    )

    assert failed["state"] == FAILED
    assert failed["failure_reason"] == "worker failed without repository mutation"

    with pytest.raises(ValueError, match="only be claimed from pending state"):
        claim_job(
            path,
            job_id=job["job_id"],
            claimed_at="2026-06-14T03:00:00Z",
        )


def test_malformed_unsupported_and_authority_expanding_queues_fail_closed(
    tmp_path: Path,
) -> None:
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{", encoding="utf-8")

    with pytest.raises(ValueError, match="unable to read diagnostic job queue"):
        load_queue(malformed)

    unsupported = tmp_path / "unsupported.json"
    unsupported.write_text(
        json.dumps(
            {
                "schema_version": "unsupported",
                "execution_mode": "local_read_only",
                "jobs": [],
                "decision_boundary": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="schema is not supported"):
        load_queue(unsupported)

    expanded = tmp_path / "expanded.json"
    expanded.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "execution_mode": "local_read_only",
                "jobs": [],
                "decision_boundary": {
                    "automation_allowed": True,
                    "patch_application_allowed": False,
                    "merge_authorized": False,
                    "semantic_equivalence_proven": False,
                    "proof_commands_executed": False,
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="expands authority"):
        load_queue(expanded)


def test_queue_never_executes_diagnostic_worker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sdetkit.diagnostic_job as diagnostic_job

    def forbidden_worker(*args: object, **kwargs: object) -> None:
        raise AssertionError("queue must not execute the diagnostic worker")

    monkeypatch.setattr(diagnostic_job, "run_diagnostic_worker", forbidden_worker)

    path = tmp_path / "queue.json"
    job = _job(head_sha="head123", created_at="2026-06-14T00:00:00Z")
    enqueue_job(path, job)
    claim_job(
        path,
        job_id=job["job_id"],
        claimed_at="2026-06-14T01:00:00Z",
    )
    complete_job(
        path,
        job["job_id"],
        result_artifacts={"worker_result": "build/result.json"},
        completed_at="2026-06-14T02:00:00Z",
    )

    assert load_queue(path)["jobs"][0]["state"] == COMPLETED
