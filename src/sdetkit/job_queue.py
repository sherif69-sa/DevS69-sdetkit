from __future__ import annotations

import copy
import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sdetkit.diagnostic_job import EXECUTION_MODE, validate_job

SCHEMA_VERSION = "sdetkit.local_diagnostic_job_queue.v1"

PENDING = "pending"
CLAIMED = "claimed"
COMPLETED = "completed"
FAILED = "failed"
ALLOWED_STATES = frozenset({PENDING, CLAIMED, COMPLETED, FAILED})

JsonObject = dict[str, Any]


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes"}


def _boundary() -> JsonObject:
    return {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "proof_commands_executed": False,
    }


def _assert_boundary(payload: Mapping[str, Any], *, source: str) -> None:
    denied = (
        "automation_allowed",
        "patch_application_allowed",
        "merge_authorized",
        "semantic_equivalence_proven",
        "proof_commands_executed",
    )
    expanded = [key for key in denied if _bool(payload.get(key))]
    if expanded:
        raise ValueError(f"{source} expands authority: " + ", ".join(expanded))


def _empty_queue() -> JsonObject:
    return {
        "schema_version": SCHEMA_VERSION,
        "execution_mode": EXECUTION_MODE,
        "jobs": [],
        "decision_boundary": _boundary(),
    }


def _record_sort_key(record: Mapping[str, Any]) -> tuple[str, str]:
    job = _as_dict(record.get("job"))
    return (_string(job.get("created_at")), _string(record.get("job_id")))


def _normalize_artifacts(value: Mapping[str, str]) -> dict[str, str]:
    return {
        _string(name): _string(path)
        for name, path in sorted(value.items())
        if _string(name) and _string(path)
    }


def _sanitize_failure_reason(reason: str) -> str:
    normalized = " ".join(_string(reason).split())
    if not normalized:
        raise ValueError("failed diagnostic job requires a failure reason")
    return normalized[:500]


def _record_for_job(job: Mapping[str, Any], *, enqueued_at: str) -> JsonObject:
    validate_job(job)
    job_id = _string(job.get("job_id"))
    if not job_id:
        raise ValueError("diagnostic job id is required")

    timestamp = _string(enqueued_at) or _string(job.get("created_at"))
    if not timestamp:
        raise ValueError("diagnostic queue enqueue timestamp is required")

    return {
        "job_id": job_id,
        "state": PENDING,
        "enqueued_at": timestamp,
        "claimed_at": "",
        "completed_at": "",
        "failed_at": "",
        "job": copy.deepcopy(dict(job)),
        "result_artifacts": {},
        "failure_reason": "",
        "decision_boundary": _boundary(),
    }


def _validate_record(record: Mapping[str, Any]) -> None:
    job = _as_dict(record.get("job"))
    validate_job(job)

    job_id = _string(record.get("job_id"))
    if not job_id:
        raise ValueError("diagnostic queue record requires a job id")
    if job_id != _string(job.get("job_id")):
        raise ValueError("diagnostic queue record job id does not match job")

    state = _string(record.get("state"))
    if state not in ALLOWED_STATES:
        raise ValueError(f"diagnostic queue state is not supported: {state or 'missing'}")

    if not _string(record.get("enqueued_at")):
        raise ValueError("diagnostic queue record requires enqueued_at")

    _assert_boundary(
        _as_dict(record.get("decision_boundary")),
        source=f"diagnostic queue record {job_id}",
    )

    claimed_at = _string(record.get("claimed_at"))
    completed_at = _string(record.get("completed_at"))
    failed_at = _string(record.get("failed_at"))
    result_artifacts = _as_dict(record.get("result_artifacts"))
    failure_reason = _string(record.get("failure_reason"))

    if state == PENDING:
        if claimed_at or completed_at or failed_at or result_artifacts or failure_reason:
            raise ValueError("pending diagnostic queue record contains terminal state evidence")
    elif state == CLAIMED:
        if not claimed_at:
            raise ValueError("claimed diagnostic queue record requires claimed_at")
        if completed_at or failed_at or result_artifacts or failure_reason:
            raise ValueError("claimed diagnostic queue record contains terminal state evidence")
    elif state == COMPLETED:
        if not claimed_at or not completed_at:
            raise ValueError(
                "completed diagnostic queue record requires claim and completion times"
            )
        if not result_artifacts:
            raise ValueError("completed diagnostic queue record requires result artifacts")
        if failed_at or failure_reason:
            raise ValueError("completed diagnostic queue record contains failure evidence")
    elif state == FAILED:
        if not claimed_at or not failed_at:
            raise ValueError("failed diagnostic queue record requires claim and failure times")
        if not failure_reason:
            raise ValueError("failed diagnostic queue record requires a failure reason")
        if completed_at or result_artifacts:
            raise ValueError("failed diagnostic queue record contains completion evidence")


def validate_queue(queue: Mapping[str, Any]) -> None:
    if _string(queue.get("schema_version")) != SCHEMA_VERSION:
        raise ValueError("diagnostic job queue schema is not supported")
    if _string(queue.get("execution_mode")) != EXECUTION_MODE:
        raise ValueError("diagnostic job queue execution mode must be local read-only")

    _assert_boundary(
        _as_dict(queue.get("decision_boundary")),
        source="diagnostic job queue",
    )

    raw_jobs = queue.get("jobs")
    if not isinstance(raw_jobs, list):
        raise ValueError("diagnostic job queue jobs must be a list")

    records = [_as_dict(item) for item in raw_jobs]
    if any(not record for record in records):
        raise ValueError("diagnostic job queue contains a malformed record")

    seen: set[str] = set()
    for record in records:
        _validate_record(record)
        job_id = _string(record.get("job_id"))
        if job_id in seen:
            raise ValueError(f"diagnostic job queue contains duplicate job id: {job_id}")
        seen.add(job_id)

    if records != sorted(records, key=_record_sort_key):
        raise ValueError("diagnostic job queue records are not in deterministic order")


def load_queue(path: Path) -> JsonObject:
    if not path.exists():
        return _empty_queue()

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to read diagnostic job queue: {path}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in diagnostic job queue: {path}")

    validate_queue(payload)
    return copy.deepcopy(payload)


def _write_queue(path: Path, queue: Mapping[str, Any]) -> None:
    normalized = copy.deepcopy(dict(queue))
    normalized["jobs"] = sorted(
        [_as_dict(item) for item in _as_list(normalized.get("jobs"))],
        key=_record_sort_key,
    )
    validate_queue(normalized)

    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(normalized, indent=2, sort_keys=True) + "\n"

    fd, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _record_index(queue: Mapping[str, Any], job_id: str) -> int:
    normalized_job_id = _string(job_id)
    for index, item in enumerate(_as_list(queue.get("jobs"))):
        record = _as_dict(item)
        if _string(record.get("job_id")) == normalized_job_id:
            return index
    raise ValueError(f"unknown diagnostic queue job: {normalized_job_id or 'missing'}")


def enqueue_job(
    path: Path,
    job: Mapping[str, Any],
    *,
    enqueued_at: str = "",
) -> JsonObject:
    queue = load_queue(path)
    job_id = _string(job.get("job_id"))

    if any(_string(_as_dict(item).get("job_id")) == job_id for item in _as_list(queue.get("jobs"))):
        raise ValueError(f"duplicate diagnostic queue job: {job_id}")

    record = _record_for_job(job, enqueued_at=enqueued_at)
    jobs = _as_list(queue.get("jobs"))
    jobs.append(record)
    queue["jobs"] = jobs
    _write_queue(path, queue)
    return copy.deepcopy(record)


def claim_job(
    path: Path,
    *,
    claimed_at: str,
    job_id: str = "",
) -> JsonObject:
    timestamp = _string(claimed_at)
    if not timestamp:
        raise ValueError("diagnostic queue claim timestamp is required")

    queue = load_queue(path)
    records = [_as_dict(item) for item in _as_list(queue.get("jobs"))]

    if _string(job_id):
        index = _record_index(queue, job_id)
        record = records[index]
        if _string(record.get("state")) != PENDING:
            raise ValueError("diagnostic queue job can only be claimed from pending state")
    else:
        pending = [
            (index, record)
            for index, record in enumerate(records)
            if _string(record.get("state")) == PENDING
        ]
        if not pending:
            raise ValueError("diagnostic job queue has no pending jobs")
        index, record = min(pending, key=lambda item: _record_sort_key(item[1]))

    record["state"] = CLAIMED
    record["claimed_at"] = timestamp
    records[index] = record
    queue["jobs"] = records
    _write_queue(path, queue)
    return copy.deepcopy(record)


def complete_job(
    path: Path,
    job_id: str,
    *,
    result_artifacts: Mapping[str, str],
    completed_at: str,
) -> JsonObject:
    timestamp = _string(completed_at)
    if not timestamp:
        raise ValueError("diagnostic queue completion timestamp is required")

    artifacts = _normalize_artifacts(result_artifacts)
    if not artifacts:
        raise ValueError("completed diagnostic queue job requires result artifacts")

    queue = load_queue(path)
    records = [_as_dict(item) for item in _as_list(queue.get("jobs"))]
    index = _record_index(queue, job_id)
    record = records[index]

    if _string(record.get("state")) != CLAIMED:
        raise ValueError("diagnostic queue job can only complete from claimed state")

    record["state"] = COMPLETED
    record["completed_at"] = timestamp
    record["result_artifacts"] = artifacts
    records[index] = record
    queue["jobs"] = records
    _write_queue(path, queue)
    return copy.deepcopy(record)


def fail_job(
    path: Path,
    job_id: str,
    *,
    reason: str,
    failed_at: str,
) -> JsonObject:
    timestamp = _string(failed_at)
    if not timestamp:
        raise ValueError("diagnostic queue failure timestamp is required")

    queue = load_queue(path)
    records = [_as_dict(item) for item in _as_list(queue.get("jobs"))]
    index = _record_index(queue, job_id)
    record = records[index]

    if _string(record.get("state")) != CLAIMED:
        raise ValueError("diagnostic queue job can only fail from claimed state")

    record["state"] = FAILED
    record["failed_at"] = timestamp
    record["failure_reason"] = _sanitize_failure_reason(reason)
    records[index] = record
    queue["jobs"] = records
    _write_queue(path, queue)
    return copy.deepcopy(record)
