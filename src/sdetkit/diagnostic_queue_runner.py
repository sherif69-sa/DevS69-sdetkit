from __future__ import annotations

import copy
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sdetkit.job_queue import (
    CLAIMED,
    COMPLETED,
    FAILED,
    PENDING,
    load_queue,
)
from sdetkit.queued_diagnostic_worker import run_queued_diagnostic_job

SCHEMA_VERSION = "sdetkit.bounded_diagnostic_queue_runner.v1"

JsonObject = dict[str, Any]


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _records(queue: Mapping[str, Any]) -> list[JsonObject]:
    return [_as_dict(item) for item in _as_list(queue.get("jobs"))]


def _pending_job_ids(queue: Mapping[str, Any]) -> list[str]:
    return [
        _string(record.get("job_id"))
        for record in _records(queue)
        if _string(record.get("state")) == PENDING
    ]


def _record_state(
    queue: Mapping[str, Any],
    job_id: str,
) -> str:
    for record in _records(queue):
        if _string(record.get("job_id")) == job_id:
            return _string(record.get("state"))

    return ""


def _state_counts(queue: Mapping[str, Any]) -> dict[str, int]:
    records = _records(queue)

    return {
        PENDING: sum(_string(record.get("state")) == PENDING for record in records),
        CLAIMED: sum(_string(record.get("state")) == CLAIMED for record in records),
        COMPLETED: sum(_string(record.get("state")) == COMPLETED for record in records),
        FAILED: sum(_string(record.get("state")) == FAILED for record in records),
    }


def _decision_boundary() -> JsonObject:
    return {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "proof_commands_executed": False,
        "automatic_retry": False,
    }


def run_bounded_diagnostic_queue(
    queue_path: Path,
    *,
    max_jobs: int,
    claimed_at: str,
    finished_at: str,
    out_root: Path,
    input_root: Path = Path("."),
) -> JsonObject:
    if isinstance(max_jobs, bool) or not isinstance(max_jobs, int) or max_jobs < 1:
        raise ValueError("bounded diagnostic queue runner requires a positive integer max_jobs")

    if not _string(claimed_at):
        raise ValueError("bounded diagnostic queue runner requires claimed_at")

    if not _string(finished_at):
        raise ValueError("bounded diagnostic queue runner requires finished_at")

    successful_results: list[JsonObject] = []
    failure: JsonObject = {}
    jobs_attempted = 0
    stop_reason = "max_jobs_reached"

    for _ in range(max_jobs):
        queue_before = load_queue(queue_path)
        pending_before = _pending_job_ids(queue_before)

        if not pending_before:
            stop_reason = "no_pending_jobs"
            break

        jobs_attempted += 1

        try:
            result = run_queued_diagnostic_job(
                queue_path,
                claimed_at=claimed_at,
                finished_at=finished_at,
                out_root=out_root,
                input_root=input_root,
            )
        except Exception as exc:
            queue_after = load_queue(queue_path)

            failed_job_ids = [
                job_id for job_id in pending_before if _record_state(queue_after, job_id) == FAILED
            ]

            failure = {
                "job_id": (failed_job_ids[0] if len(failed_job_ids) == 1 else ""),
                "exception_type": type(exc).__name__,
                "message": _string(exc) or type(exc).__name__,
            }
            stop_reason = "job_failed"
            break

        successful_results.append(copy.deepcopy(result))

    final_queue = load_queue(queue_path)
    jobs_failed = 1 if failure else 0

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "failed" if failure else "completed",
        "stop_reason": stop_reason,
        "max_jobs": max_jobs,
        "jobs_attempted": jobs_attempted,
        "jobs_completed": len(successful_results),
        "jobs_failed": jobs_failed,
        "successful_results": successful_results,
        "failure": failure,
        "queue_state_counts": _state_counts(final_queue),
        "decision_boundary": _decision_boundary(),
        "execution": {
            "automatic_retry": False,
            "proof_commands_executed": False,
            "patch_attempted": False,
            "merge_authorized": False,
        },
    }
