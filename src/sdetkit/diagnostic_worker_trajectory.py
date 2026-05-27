from __future__ import annotations

import argparse
import copy
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sdetkit.diagnostic_job import (
    EXECUTION_MODE,
    JOB_TYPE,
    WORKER_NAME,
    WORKER_RESULT_SCHEMA_VERSION,
    validate_job,
)
from sdetkit.diagnostic_job import (
    SCHEMA_VERSION as JOB_SCHEMA_VERSION,
)
from sdetkit.trajectory_store import (
    DEFAULT_GENERATED_AT,
    build_trajectory_records,
    write_trajectory_records,
)
from sdetkit.trajectory_store import (
    SCHEMA_VERSION as TRAJECTORY_SCHEMA_VERSION,
)

SCHEMA_VERSION = "sdetkit.diagnostic_worker_trajectory.v1"
OUT_JSONL = "diagnostic-worker-trajectory.jsonl"
SUMMARY_JSON = "diagnostic-worker-trajectory-summary.json"
REPORT_MD = "diagnostic-worker-trajectory.md"
DEFAULT_OUT_DIR = Path("build") / "diagnostic-worker-trajectory"

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


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _read_required_json(path: Path) -> JsonObject:
    if not path.exists():
        raise ValueError(f"declared diagnostic worker trajectory input is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _assert_false_fields(payload: Mapping[str, Any], *, source: str) -> None:
    denied = (
        "current_pr_decision_input",
        "proof_commands_executed",
        "patch_application_allowed",
        "automation_allowed",
        "merge_authorized",
        "semantic_equivalence_proven",
    )
    expanded = [key for key in denied if _bool(payload.get(key))]
    if expanded:
        raise ValueError(f"{source} expands authority: " + ", ".join(expanded))


def _summary_projection(payload: Mapping[str, Any]) -> JsonObject:
    return {
        "diagnosis_count": _int(payload.get("diagnosis_count")),
        "review_first_count": _int(payload.get("review_first_count")),
        "safe_fix_candidate_count": _int(payload.get("safe_fix_candidate_count")),
        "primary_surface": _string(payload.get("primary_surface")),
        "primary_action": _string(payload.get("primary_action")),
    }


def validate_worker_handoff(
    *,
    job: Mapping[str, Any],
    worker_result: Mapping[str, Any],
    diagnostic_vector: Mapping[str, Any],
) -> None:
    validate_job(job)
    if _string(job.get("schema_version")) != JOB_SCHEMA_VERSION:
        raise ValueError("diagnostic job schema is not supported for trajectory handoff")
    if _string(worker_result.get("schema_version")) != WORKER_RESULT_SCHEMA_VERSION:
        raise ValueError("diagnostic worker result schema is not supported")
    if _string(worker_result.get("job_id")) != _string(job.get("job_id")):
        raise ValueError("diagnostic worker result job id does not match job")
    if _string(worker_result.get("job_type")) != JOB_TYPE:
        raise ValueError("diagnostic worker result job type is not supported")
    if _string(worker_result.get("worker")) != WORKER_NAME:
        raise ValueError("diagnostic worker result worker is not supported")
    if _string(worker_result.get("status")) != "completed":
        raise ValueError("diagnostic worker result must be completed before trajectory handoff")
    if _string(worker_result.get("execution_mode")) != EXECUTION_MODE:
        raise ValueError("diagnostic worker result execution mode must be local read-only")

    _assert_false_fields(_as_dict(worker_result.get("decision_boundary")), source="worker result")
    execution = _as_dict(worker_result.get("execution"))
    execution_expanded = [
        key
        for key in ("proof_commands_executed", "patch_attempted", "repository_write_attempted")
        if _bool(execution.get(key))
    ]
    if execution_expanded:
        raise ValueError(
            "diagnostic worker execution expands authority: " + ", ".join(execution_expanded)
        )

    result_summary = _summary_projection(_as_dict(worker_result.get("summary")))
    vector_summary = _summary_projection(_as_dict(diagnostic_vector.get("summary")))
    if result_summary != vector_summary:
        raise ValueError("diagnostic worker result summary does not match diagnostic vector")

    vector_diagnoses = [
        _as_dict(row) for row in _as_list(diagnostic_vector.get("diagnoses")) if _as_dict(row)
    ]
    result_primary = _as_dict(worker_result.get("primary_diagnosis"))
    if vector_diagnoses:
        vector_primary = vector_diagnoses[0]
        for key in ("diagnosis_id", "failure_surface", "headline_failure", "actual_failure"):
            if _string(result_primary.get(key)) != _string(vector_primary.get(key)):
                raise ValueError(
                    "diagnostic worker primary diagnosis does not match diagnostic vector"
                )


def build_worker_trajectory_records(
    *,
    job: Mapping[str, Any],
    worker_result: Mapping[str, Any],
    diagnostic_vector: Mapping[str, Any],
    repo: str = "",
    branch: str = "",
    commit_sha: str = "",
    pr_number: int = 0,
    generated_at: str = DEFAULT_GENERATED_AT,
) -> list[JsonObject]:
    validate_worker_handoff(
        job=job,
        worker_result=worker_result,
        diagnostic_vector=diagnostic_vector,
    )
    base_records = build_trajectory_records(
        diagnostic_vector=diagnostic_vector,
        repo=repo,
        branch=branch,
        commit_sha=commit_sha,
        pr_number=pr_number,
        generated_at=generated_at,
    )

    records: list[JsonObject] = []
    for base_record in base_records:
        record = copy.deepcopy(base_record)
        observed_decision = _as_dict(record.get("decision"))
        observed_fix = _as_dict(record.get("fix"))
        original_id = _string(record.get("trajectory_id"))
        record["trajectory_id"] = f"{original_id}-diagnostic-worker-observation"
        record["environment"] = {
            "runner": "github_actions",
            "source": "diagnostic_worker_result",
            "worker": WORKER_NAME,
            "execution_mode": EXECUTION_MODE,
        }
        record["action"] = "record_diagnostic_worker_observation"
        record["command"] = "none"
        response = _as_dict(record.get("response"))
        response["response_type"] = "diagnostic_worker_observation"
        record["response"] = response
        record["decision"] = {
            "review_first": True,
            "auto_fix_allowed": False,
            "reason": "diagnostic worker trajectory is reporting-only evidence",
        }
        record["fix"] = {
            "allowed_strategy": "none",
            "patch_files": [],
            "blocked_reason": "diagnostic worker trajectory is reporting-only evidence",
        }
        record["proof"] = {
            "commands": [],
            "focused_proof": "not_run",
            "quality_proof": "not_run",
            "verifier_result": "not_run",
        }
        record["final_result"] = "advisory_observation_recorded"
        record["learned_pattern"] = "diagnostic_worker_observation"
        record["worker_evidence"] = {
            "job_id": _string(job.get("job_id")),
            "worker_result_status": _string(worker_result.get("status")),
            "observed_safe_fix_candidate": _bool(observed_decision.get("auto_fix_allowed"))
            or bool(_as_list(observed_fix.get("patch_files"))),
            "reporting_only": True,
            "current_pr_decision_input": False,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        }
        records.append(record)
    return records


def build_summary(
    records: list[Mapping[str, Any]],
    *,
    worker_result: Mapping[str, Any],
    trajectory_jsonl: str,
) -> JsonObject:
    return {
        "schema_version": SCHEMA_VERSION,
        "trajectory_schema_version": TRAJECTORY_SCHEMA_VERSION,
        "status": "recorded",
        "record_count": len(records),
        "review_first_count": sum(
            1 for row in records if _as_dict(row.get("decision")).get("review_first") is True
        ),
        "observed_safe_fix_candidate_count": sum(
            1
            for row in records
            if _as_dict(row.get("worker_evidence")).get("observed_safe_fix_candidate") is True
        ),
        "worker_result_status": _string(worker_result.get("status")),
        "trajectory_jsonl": trajectory_jsonl,
        "reporting_only": True,
        "current_pr_decision_input": False,
        "proof_commands_executed": False,
        "patch_application_allowed": False,
        "automation_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def render_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "## Local diagnostic worker trajectory handoff",
        "",
        "- Evidence type: `post_decision_reporting_only_trajectory`",
        f"- Status: `{_string(summary.get('status'))}`",
        f"- Records written: `{_int(summary.get('record_count'))}`",
        f"- Review-first records: `{_int(summary.get('review_first_count'))}`",
        (
            "- Observed safe-fix candidates retained as advisory only: "
            f"`{_int(summary.get('observed_safe_fix_candidate_count'))}`"
        ),
        f"- Reporting only: `{str(_bool(summary.get('reporting_only'))).lower()}`",
        (
            "- Current PR decision input: "
            f"`{str(_bool(summary.get('current_pr_decision_input'))).lower()}`"
        ),
        (
            "- Proof commands executed: "
            f"`{str(_bool(summary.get('proof_commands_executed'))).lower()}`"
        ),
        (
            "- Patch application allowed: "
            f"`{str(_bool(summary.get('patch_application_allowed'))).lower()}`"
        ),
        f"- Automation allowed: `{str(_bool(summary.get('automation_allowed'))).lower()}`",
        f"- Merge authorized: `{str(_bool(summary.get('merge_authorized'))).lower()}`",
        (
            "- Semantic equivalence proven: "
            f"`{str(_bool(summary.get('semantic_equivalence_proven'))).lower()}`"
        ),
        "",
        "- Interpretation: this separate trajectory records the DiagnosticWorkerResult for observation only; it is not consumed by current-run candidate decisions or RepoMemory.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def write_artifacts(
    records: list[Mapping[str, Any]],
    *,
    worker_result: Mapping[str, Any],
    out_dir: Path,
) -> JsonObject:
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / OUT_JSONL
    write_trajectory_records(records, jsonl_path)
    summary = build_summary(
        records,
        worker_result=worker_result,
        trajectory_jsonl=jsonl_path.as_posix(),
    )
    summary_path = out_dir / SUMMARY_JSON
    markdown_path = out_dir / REPORT_MD
    _write_json(summary_path, summary)
    markdown_path.write_text(render_markdown(summary), encoding="utf-8")
    return {
        "summary": summary,
        "artifacts": {
            "diagnostic_worker_trajectory_jsonl": jsonl_path.as_posix(),
            "diagnostic_worker_trajectory_summary_json": summary_path.as_posix(),
            "diagnostic_worker_trajectory_markdown": markdown_path.as_posix(),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.diagnostic_worker_trajectory")
    parser.add_argument("--diagnostic-job", type=Path, required=True)
    parser.add_argument("--diagnostic-worker-result", type=Path, required=True)
    parser.add_argument("--diagnostic-vector", type=Path, required=True)
    parser.add_argument("--repo", default="")
    parser.add_argument("--branch", default="")
    parser.add_argument("--commit-sha", default="")
    parser.add_argument("--pr-number", type=int, default=0)
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        job = _read_required_json(args.diagnostic_job)
        worker_result = _read_required_json(args.diagnostic_worker_result)
        diagnostic_vector = _read_required_json(args.diagnostic_vector)
        records = build_worker_trajectory_records(
            job=job,
            worker_result=worker_result,
            diagnostic_vector=diagnostic_vector,
            repo=args.repo,
            branch=args.branch,
            commit_sha=args.commit_sha,
            pr_number=args.pr_number,
            generated_at=args.generated_at,
        )
        payload = write_artifacts(records, worker_result=worker_result, out_dir=args.out_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            "diagnostic_worker_trajectory_jsonl: "
            + payload["artifacts"]["diagnostic_worker_trajectory_jsonl"]
        )
        print(f"record_count: {payload['summary']['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
