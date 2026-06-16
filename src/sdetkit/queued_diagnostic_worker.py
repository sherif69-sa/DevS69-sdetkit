from __future__ import annotations

import copy
import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sdetkit.diagnostic_job import (
    RESULT_JSON,
    REVIEW_HANDOFF_SCHEMA_VERSION,
    run_diagnostic_worker,
)
from sdetkit.diagnostic_worker_trajectory import (
    build_worker_trajectory_records,
)
from sdetkit.diagnostic_worker_trajectory import (
    write_artifacts as write_worker_trajectory_artifacts,
)
from sdetkit.job_queue import claim_job, complete_job, fail_job
from sdetkit.patch_scorer import SCHEMA_VERSION as PATCH_SCORE_SCHEMA_VERSION
from sdetkit.safety_gate import SCHEMA_VERSION as SAFETY_GATE_SCHEMA_VERSION

SCHEMA_VERSION = "sdetkit.queued_diagnostic_worker.v1"
TRAJECTORY_DIR = "trajectory"
SUPPORTED_INPUTS = frozenset(
    {
        "check_intelligence",
        "evidence_graph",
        "pr_quality_action_report",
        "security_review",
        "runtime_proof_artifacts",
        "patch_score",
        "safety_gate_decision",
    }
)

JsonObject = dict[str, Any]


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


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


def _assert_review_authority_boundary(
    payload: Mapping[str, Any],
    *,
    source: str,
) -> None:
    denied = (
        "automation_allowed",
        "patch_application_allowed",
        "security_dismissal_allowed",
        "merge_authorized",
        "semantic_equivalence_proven",
        "semantic_equivalence_claim",
    )
    expanded = [key for key in denied if _bool(payload.get(key))]
    if expanded:
        raise ValueError(f"{source} expands authority: " + ", ".join(expanded))


def _build_review_handoff(
    worker_inputs: Mapping[str, Mapping[str, Any]],
) -> JsonObject:
    safety = _as_dict(worker_inputs.get("safety_gate_decision"))
    patch = _as_dict(worker_inputs.get("patch_score"))

    safety_projection: JsonObject = {}
    patch_projection: JsonObject = {}

    if safety:
        if _string(safety.get("schema_version")) != SAFETY_GATE_SCHEMA_VERSION:
            raise ValueError("queued safety-gate decision schema is not supported")
        if not _bool(safety.get("reporting_only")):
            raise ValueError("queued safety-gate decision must be reporting-only")
        _assert_review_authority_boundary(
            safety,
            source="queued safety-gate decision",
        )
        safety_projection = {
            "schema_version": SAFETY_GATE_SCHEMA_VERSION,
            "failure_class": _string(safety.get("failure_class")) or "unknown",
            "risk": _string(safety.get("risk")) or "unknown",
            "review_first": _bool(safety.get("review_first")),
            "safe_fix_allowed": _bool(safety.get("safe_fix_allowed")),
            "reason": _string(safety.get("reason")),
            "reporting_only": True,
            "authority_boundary_preserved": True,
        }

    if patch:
        if _string(patch.get("schema_version")) != PATCH_SCORE_SCHEMA_VERSION:
            raise ValueError("queued patch-score schema is not supported")
        _assert_review_authority_boundary(
            patch,
            source="queued patch-score",
        )
        decision = _as_dict(patch.get("decision"))
        _assert_review_authority_boundary(
            decision,
            source="queued patch-score decision",
        )
        patch_projection = {
            "schema_version": PATCH_SCORE_SCHEMA_VERSION,
            "patch_id": _string(patch.get("patch_id")) or "unknown",
            "diagnosis_id": _string(patch.get("diagnosis_id")) or "unknown",
            "score": int(patch.get("score", 0) or 0),
            "minimum_score": int(patch.get("minimum_score", 0) or 0),
            "decision_status": _string(decision.get("status")) or "unknown",
            "candidate_for_protected_verification": _bool(
                decision.get("candidate_for_protected_verification")
            ),
            "risk_flag_count": len(patch.get("risk_flags") or []),
            "automation_allowed": False,
            "reporting_only": True,
            "authority_boundary_preserved": True,
        }

    observed = bool(safety_projection or patch_projection)

    return {
        "schema_version": REVIEW_HANDOFF_SCHEMA_VERSION,
        "status": "observed" if observed else "not_provided",
        "sources": {
            "pr_quality_action_report": bool(
                _as_dict(worker_inputs.get("pr_quality_action_report"))
            ),
            "runtime_proof_artifacts": bool(_as_dict(worker_inputs.get("runtime_proof_artifacts"))),
            "safety_gate_decision": bool(safety_projection),
            "patch_score": bool(patch_projection),
        },
        "safety_gate_decision": safety_projection,
        "patch_score": patch_projection,
        "reporting_only": True,
        "current_pr_decision_input": False,
        "decision_boundary": _boundary(),
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
        review_handoff = _build_review_handoff(worker_inputs)

        worker_result = run_diagnostic_worker(
            job,
            check_intelligence=worker_inputs.get("check_intelligence"),
            evidence_graph=worker_inputs.get("evidence_graph"),
            pr_quality_action_report=worker_inputs.get("pr_quality_action_report"),
            security_review=worker_inputs.get("security_review"),
            runtime_proof_artifacts=worker_inputs.get("runtime_proof_artifacts"),
            out_dir=out_dir,
        )
        worker_result["review_handoff"] = review_handoff

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
