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

    trajectory_jsonl = (
        tmp_path / "worker" / job["job_id"] / "trajectory" / "diagnostic-worker-trajectory.jsonl"
    )
    trajectory_summary = (
        tmp_path
        / "worker"
        / job["job_id"]
        / "trajectory"
        / "diagnostic-worker-trajectory-summary.json"
    )
    trajectory_markdown = (
        tmp_path / "worker" / job["job_id"] / "trajectory" / "diagnostic-worker-trajectory.md"
    )

    assert result_path.exists()
    assert vector_path.exists()
    assert trajectory_jsonl.exists()
    assert trajectory_summary.exists()
    assert trajectory_markdown.exists()

    assert result["trajectory"]["summary"]["status"] == "recorded"
    assert result["trajectory"]["summary"]["reporting_only"] is True
    assert result["trajectory"]["summary"]["current_pr_decision_input"] is False
    assert result["trajectory"]["summary"]["automation_allowed"] is False
    assert result["trajectory"]["summary"]["merge_authorized"] is False

    assert "diagnostic_worker_trajectory_jsonl" in record["result_artifacts"]
    assert "diagnostic_worker_trajectory_summary_json" in record["result_artifacts"]
    assert "diagnostic_worker_trajectory_markdown" in record["result_artifacts"]


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


def test_trajectory_recording_failure_marks_job_failed(
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
        head_sha="trajectory-error",
        created_at="2026-06-14T00:00:00Z",
        input_artifacts={
            "check_intelligence": str(input_path),
        },
    )

    enqueue_job(queue_path, job)

    def fail_trajectory_writer(
        *args: object,
        **kwargs: object,
    ) -> dict:
        raise RuntimeError("bounded trajectory recording failure")

    monkeypatch.setattr(
        queued_worker,
        "write_worker_trajectory_artifacts",
        fail_trajectory_writer,
    )

    with pytest.raises(
        RuntimeError,
        match="bounded trajectory recording failure",
    ):
        run_queued_diagnostic_job(
            queue_path,
            claimed_at="2026-06-14T01:00:00Z",
            finished_at="2026-06-14T02:00:00Z",
            out_root=tmp_path / "worker",
        )

    record = load_queue(queue_path)["jobs"][0]

    assert record["state"] == FAILED
    assert record["failure_reason"] == ("RuntimeError: bounded trajectory recording failure")


def _safety_gate_decision() -> dict:
    return {
        "schema_version": "sdetkit.safety_gate.v1",
        "failure_class": "formatter_only",
        "risk": "low",
        "scope": "pr_owned_only",
        "failure_kind": "formatter_only",
        "affected_surface": "source",
        "ownership_area": "src/sdetkit/example.py",
        "retryability": "not_retryable_without_change",
        "security_relevance": False,
        "recommended_next_human_action": "review formatter-only candidate",
        "reporting_only": True,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "security_dismissal_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_claim": False,
        "safe_fix_allowed": True,
        "review_first": False,
        "reason": "eligible for protected verification only",
        "allowed_files": ["src/sdetkit/example.py"],
        "blocked_actions": [],
        "proof_commands": ["python -m pre_commit run -a", "make proof-after-format"],
    }


def _patch_score() -> dict:
    return {
        "schema_version": "sdetkit.patch_score.v1",
        "patch_id": "patch-1",
        "diagnosis_id": "diagnosis-1",
        "failure_surface": "formatting",
        "classification": "formatter_only",
        "risk_level": "low",
        "strategy": "run_pre_commit",
        "changed_files": ["src/sdetkit/example.py"],
        "allowed_files": ["src/sdetkit/example.py"],
        "score": 90,
        "minimum_score": 80,
        "risk_flags": [],
        "decision": {
            "status": "candidate_for_protected_verification",
            "candidate_for_protected_verification": True,
            "automation_allowed": False,
            "reason": "candidate for protected verification only",
        },
        "proof_requirements": [
            "python -m pre_commit run -a",
            "make proof-after-format",
        ],
    }


def test_queued_worker_carries_safety_and_patch_score_as_reporting_only_evidence(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "queue.json"
    check_path = tmp_path / "check-intelligence.json"
    safety_path = tmp_path / "safety-gate.json"
    patch_path = tmp_path / "patch-score.json"

    check_path.write_text(json.dumps(_formatting_intelligence()), encoding="utf-8")
    safety_path.write_text(json.dumps(_safety_gate_decision()), encoding="utf-8")
    patch_path.write_text(json.dumps(_patch_score()), encoding="utf-8")

    job = _job(
        head_sha="review-handoff",
        created_at="2026-06-16T00:00:00Z",
        input_artifacts={
            "check_intelligence": str(check_path),
            "safety_gate_decision": str(safety_path),
            "patch_score": str(patch_path),
        },
    )
    enqueue_job(queue_path, job)

    result = run_queued_diagnostic_job(
        queue_path,
        claimed_at="2026-06-16T01:00:00Z",
        finished_at="2026-06-16T02:00:00Z",
        out_root=tmp_path / "worker",
    )

    handoff = result["worker_result"]["review_handoff"]
    assert handoff["schema_version"] == "sdetkit.queue_review_handoff.v1"
    assert handoff["status"] == "observed"
    assert handoff["reporting_only"] is True
    assert handoff["current_pr_decision_input"] is False
    assert handoff["sources"]["safety_gate_decision"] is True
    assert handoff["sources"]["patch_score"] is True
    assert handoff["safety_gate_decision"]["authority_boundary_preserved"] is True
    assert handoff["patch_score"]["authority_boundary_preserved"] is True
    assert handoff["patch_score"]["candidate_for_protected_verification"] is True
    assert all(value is False for value in handoff["decision_boundary"].values())

    trajectory = result["trajectory"]["summary"]
    assert trajectory["review_handoff_count"] == 1
    assert trajectory["safety_gate_decision_observed_count"] == 1
    assert trajectory["patch_score_observed_count"] == 1
    assert trajectory["reporting_only"] is True
    assert trajectory["current_pr_decision_input"] is False

    trajectory_jsonl = Path(
        result["queue_record"]["result_artifacts"]["diagnostic_worker_trajectory_jsonl"]
    )
    record = json.loads(trajectory_jsonl.read_text(encoding="utf-8").splitlines()[0])
    retained = record["worker_evidence"]["review_handoff"]
    assert retained["patch_score"]["score"] == 90
    assert retained["safety_gate_decision"]["safe_fix_allowed"] is True
    assert record["decision"]["review_first"] is True
    assert record["decision"]["auto_fix_allowed"] is False
    assert record["proof"]["commands"] == []


def test_queued_worker_rejects_review_evidence_authority_expansion(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "queue.json"
    check_path = tmp_path / "check-intelligence.json"
    safety_path = tmp_path / "safety-gate.json"

    check_path.write_text(json.dumps(_formatting_intelligence()), encoding="utf-8")
    unsafe = _safety_gate_decision()
    unsafe["automation_allowed"] = True
    safety_path.write_text(json.dumps(unsafe), encoding="utf-8")

    job = _job(
        head_sha="unsafe-review-handoff",
        created_at="2026-06-16T00:00:00Z",
        input_artifacts={
            "check_intelligence": str(check_path),
            "safety_gate_decision": str(safety_path),
        },
    )
    enqueue_job(queue_path, job)

    with pytest.raises(ValueError, match="expands authority"):
        run_queued_diagnostic_job(
            queue_path,
            claimed_at="2026-06-16T01:00:00Z",
            finished_at="2026-06-16T02:00:00Z",
            out_root=tmp_path / "worker",
        )

    record = load_queue(queue_path)["jobs"][0]
    assert record["state"] == FAILED
    assert "expands authority" in record["failure_reason"]
