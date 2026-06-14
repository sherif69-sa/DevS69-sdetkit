from __future__ import annotations

import copy
import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sdetkit.diagnostic_job import RESULT_JSON, run_diagnostic_worker
from sdetkit.diagnostic_worker_trajectory import (
    build_worker_trajectory_records,
)
from sdetkit.diagnostic_worker_trajectory import (
    write_artifacts as write_worker_trajectory_artifacts,
)
from sdetkit.job_queue import claim_job, complete_job, fail_job

SCHEMA_VERSION = "sdetkit.queued_diagnostic_worker.v1"
TRAJECTORY_DIR = "trajectory"
SUPPORTED_INPUTS = frozenset(
    {
        "check_intelligence",
        "evidence_graph",
        "pr_quality_action_report",
        "security_review",
        "runtime_proof_artifacts",
    }
)

JsonObject = dict[str, Any]


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _string(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _boundary() -> JsonObject:
    return {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "proof_commands_executed": False,
    }


def _read_json_object(path: Path) -> JsonObject:
    if not path.exists():
        raise ValueError(f"declared queued diagnostic evidence input is missing: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"queued diagnostic evidence input is not valid JSON: {path}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in queued diagnostic evidence input: {path}")

    return payload


def _resolve_input_path(raw_path: str, *, input_root: Path) -> Path:
    path = Path(_string(raw_path))
    return path if path.is_absolute() else input_root / path


def _load_worker_inputs(
    job: Mapping[str, Any],
    *,
    input_root: Path,
) -> dict[str, JsonObject]:
    declared = _as_dict(job.get("input_artifacts"))
    unknown = sorted(set(declared) - SUPPORTED_INPUTS)

    if unknown:
        raise ValueError(
            "queued diagnostic job declares unsupported evidence inputs: " + ", ".join(unknown)
        )

    return {
        name: _read_json_object(
            _resolve_input_path(
                _string(raw_path),
                input_root=input_root,
            )
        )
        for name, raw_path in sorted(declared.items())
    }


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"

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


def _diagnostic_vector_path(
    worker_result: Mapping[str, Any],
) -> Path:
    candidates = sorted(
        {
            normalized
            for raw_path in _as_dict(worker_result.get("output_artifacts")).values()
            if (normalized := _string(raw_path))
            and Path(normalized).name == "diagnostic-vector.json"
        }
    )

    if len(candidates) != 1:
        raise ValueError("queued diagnostic worker requires exactly one diagnostic vector artifact")

    return Path(candidates[0])


def _record_worker_trajectory(
    *,
    job: Mapping[str, Any],
    worker_result: Mapping[str, Any],
    out_dir: Path,
) -> JsonObject:
    diagnostic_vector = _read_json_object(_diagnostic_vector_path(worker_result))

    records = build_worker_trajectory_records(
        job=job,
        worker_result=worker_result,
        diagnostic_vector=diagnostic_vector,
        repo=(_string(job.get("repo")) or _string(job.get("repository"))),
        branch=_string(job.get("branch")),
        commit_sha=(_string(job.get("head_sha")) or _string(job.get("commit_sha"))),
        pr_number=int(job.get("pr_number") or 0),
        generated_at=_string(job.get("created_at")),
    )

    return write_worker_trajectory_artifacts(
        records,
        worker_result=worker_result,
        out_dir=out_dir / TRAJECTORY_DIR,
    )


def _result_artifacts(
    worker_result: Mapping[str, Any],
    *,
    result_path: Path,
    trajectory_payload: Mapping[str, Any],
) -> dict[str, str]:
    artifacts = {
        "worker_result": str(result_path),
    }

    for name, raw_path in sorted(_as_dict(worker_result.get("output_artifacts")).items()):
        normalized_name = _string(name)
        normalized_path = _string(raw_path)

        if normalized_name and normalized_path:
            artifacts[f"worker_{normalized_name}"] = normalized_path

    for name, raw_path in sorted(_as_dict(trajectory_payload.get("artifacts")).items()):
        normalized_name = _string(name)
        normalized_path = _string(raw_path)

        if normalized_name and normalized_path:
            artifacts[normalized_name] = normalized_path

    return artifacts


def run_queued_diagnostic_job(
    queue_path: Path,
    *,
    claimed_at: str,
    finished_at: str,
    out_root: Path,
    input_root: Path = Path("."),
    job_id: str = "",
) -> JsonObject:
    if not _string(claimed_at):
        raise ValueError("queued diagnostic worker requires claimed_at")

    if not _string(finished_at):
        raise ValueError("queued diagnostic worker requires finished_at")

    claimed = claim_job(
        queue_path,
        claimed_at=claimed_at,
        job_id=job_id,
    )

    claimed_job_id = _string(claimed.get("job_id"))
    job = _as_dict(claimed.get("job"))
    out_dir = out_root / claimed_job_id

    try:
        worker_inputs = _load_worker_inputs(
            job,
            input_root=input_root,
        )

        worker_result = run_diagnostic_worker(
            job,
            check_intelligence=worker_inputs.get("check_intelligence"),
            evidence_graph=worker_inputs.get("evidence_graph"),
            pr_quality_action_report=worker_inputs.get("pr_quality_action_report"),
            security_review=worker_inputs.get("security_review"),
            runtime_proof_artifacts=worker_inputs.get("runtime_proof_artifacts"),
            out_dir=out_dir,
        )

        result_path = out_dir / RESULT_JSON

        _write_json_atomic(
            result_path,
            worker_result,
        )

        trajectory_payload = _record_worker_trajectory(
            job=job,
            worker_result=worker_result,
            out_dir=out_dir,
        )

        completed = complete_job(
            queue_path,
            claimed_job_id,
            result_artifacts=_result_artifacts(
                worker_result,
                result_path=result_path,
                trajectory_payload=trajectory_payload,
            ),
            completed_at=finished_at,
        )

    except Exception as exc:
        try:
            fail_job(
                queue_path,
                claimed_job_id,
                reason=f"{type(exc).__name__}: {exc}",
                failed_at=finished_at,
            )
        except Exception as transition_exc:
            raise RuntimeError(
                "queued diagnostic worker failed and could not record failed state"
            ) from transition_exc

        raise

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "completed",
        "job_id": claimed_job_id,
        "queue_record": copy.deepcopy(completed),
        "worker_result": copy.deepcopy(worker_result),
        "trajectory": copy.deepcopy(trajectory_payload),
        "decision_boundary": _boundary(),
        "execution": {
            "automatic_retry": False,
            "proof_commands_executed": False,
            "patch_attempted": False,
            "merge_authorized": False,
        },
    }
