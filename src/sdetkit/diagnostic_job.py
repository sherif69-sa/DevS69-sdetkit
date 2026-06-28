from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sdetkit.diagnostic_execution_plan import (
    SCHEMA_VERSION as DIAGNOSTIC_EXECUTION_PLAN_SCHEMA_VERSION,
)
from sdetkit.diagnostic_execution_plan import (
    validate_diagnostic_execution_plan,
)
from sdetkit.diagnostic_vector_engine import (
    ACTUAL_FAILURE,
    DEFAULT_GENERATED_AT,
    DIAGNOSIS_ID,
    FAILURE_SURFACE,
    HEADLINE_FAILURE,
    RECOMMENDED_NEXT_ACTION,
    REVIEW_FIRST,
    SAFE_FIX_CANDIDATE,
    build_diagnostic_vector,
    write_diagnostic_vector,
)

SCHEMA_VERSION = "sdetkit.diagnostic_job.v1"
WORKER_RESULT_SCHEMA_VERSION = "sdetkit.diagnostic_worker_result.v1"
REVIEW_HANDOFF_SCHEMA_VERSION = "sdetkit.queue_review_handoff.v1"
EXECUTION_PLAN_HANDOFF_SCHEMA_VERSION = "sdetkit.diagnostic_execution_plan_handoff.v1"
JOB_TYPE = "diagnostic_vector"
WORKER_NAME = "diagnostic_worker"
EXECUTION_MODE = "local_read_only"
JOB_JSON = "diagnostic-job.json"
RESULT_JSON = "diagnostic-worker-result.json"
REPORT_MD = "diagnostic-job.md"
VECTOR_DIR = "vector"
DEFAULT_OUT_DIR = Path("build") / "diagnostic-job"

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


def _read_json(path: Path | None) -> JsonObject:
    if path is None:
        return {}
    if not path.exists():
        raise ValueError(f"declared diagnostic job evidence input is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _boundary() -> JsonObject:
    return {
        "current_pr_decision_input": False,
        "automation_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "patch_application_allowed": False,
        "proof_commands_executed": False,
    }


def _job_id(*, repo: str, head_sha: str, event_name: str, pr_number: int) -> str:
    basis = "|".join((repo, head_sha, event_name, str(pr_number), JOB_TYPE))
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]
    return f"diagnostic-job-{digest}"


def build_diagnostic_job(
    *,
    repo: str,
    base_sha: str,
    head_sha: str,
    event_name: str,
    pr_number: int,
    input_artifacts: Mapping[str, str],
    generated_at: str = DEFAULT_GENERATED_AT,
) -> JsonObject:
    normalized_inputs = {
        _string(name): _string(path)
        for name, path in sorted(input_artifacts.items())
        if _string(name) and _string(path)
    }
    if not _string(head_sha):
        raise ValueError("diagnostic job requires a head SHA")
    if not normalized_inputs:
        raise ValueError("diagnostic job requires at least one evidence input artifact")

    return {
        "schema_version": SCHEMA_VERSION,
        "job_id": _job_id(
            repo=_string(repo),
            head_sha=_string(head_sha),
            event_name=_string(event_name),
            pr_number=pr_number,
        ),
        "job_type": JOB_TYPE,
        "created_at": generated_at,
        "execution_mode": EXECUTION_MODE,
        "event": {
            "repo": _string(repo),
            "base_sha": _string(base_sha),
            "head_sha": _string(head_sha),
            "event_name": _string(event_name),
            "pr_number": pr_number,
        },
        "input_artifacts": normalized_inputs,
        "worker_contract": {
            "worker": WORKER_NAME,
            "reads_current_pr_evidence": True,
            "writes_artifacts_only": True,
            "runs_proof_commands": False,
            "applies_patch": False,
            "publishes_decision": False,
        },
        "decision_boundary": _boundary(),
    }


def validate_job(job: Mapping[str, Any]) -> None:
    if _string(job.get("schema_version")) != SCHEMA_VERSION:
        raise ValueError("diagnostic job schema is not supported")
    if _string(job.get("job_type")) != JOB_TYPE:
        raise ValueError("diagnostic job type is not supported")
    if _string(job.get("execution_mode")) != EXECUTION_MODE:
        raise ValueError("diagnostic job execution mode must be local read-only")
    if not _string(job.get("job_id")):
        raise ValueError("diagnostic job id is required")
    if not _as_dict(job.get("input_artifacts")):
        raise ValueError("diagnostic job input artifacts are required")

    boundary = _as_dict(job.get("decision_boundary"))
    denied = (
        "current_pr_decision_input",
        "automation_allowed",
        "merge_authorized",
        "semantic_equivalence_proven",
        "patch_application_allowed",
        "proof_commands_executed",
    )
    expanded = [key for key in denied if _bool(boundary.get(key))]
    if expanded:
        raise ValueError("diagnostic job expands authority: " + ", ".join(expanded))

    contract = _as_dict(job.get("worker_contract"))
    if _string(contract.get("worker")) != WORKER_NAME:
        raise ValueError("diagnostic job worker is not supported")
    if not _bool(contract.get("reads_current_pr_evidence")):
        raise ValueError("diagnostic worker must consume current PR evidence")
    if not _bool(contract.get("writes_artifacts_only")):
        raise ValueError("diagnostic worker must be artifact-only")
    prohibited = [
        key
        for key in ("runs_proof_commands", "applies_patch", "publishes_decision")
        if _bool(contract.get(key))
    ]
    if prohibited:
        raise ValueError("diagnostic worker contract expands authority: " + ", ".join(prohibited))


def _repo_slug(value: Any) -> str:
    normalized = _string(value).lower().replace("\\", "/")
    if not normalized:
        return ""
    if normalized.startswith("git@") and ":" in normalized:
        normalized = normalized.split(":", 1)[1]
    elif "://" in normalized:
        normalized = normalized.split("://", 1)[1]
        normalized = normalized.split("/", 1)[1] if "/" in normalized else ""
    normalized = normalized.strip("/")
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    parts = [part for part in normalized.split("/") if part]
    return "/".join(parts[-2:]) if len(parts) >= 2 else normalized


def _execution_plan_handoff(
    job: Mapping[str, Any],
    payload: Mapping[str, Any] | None,
) -> JsonObject:
    plan = _as_dict(payload)
    boundary = _boundary()
    if not plan:
        return {
            "schema_version": EXECUTION_PLAN_HANDOFF_SCHEMA_VERSION,
            "status": "not_provided",
            "plan_schema_version": "",
            "plan_status": "",
            "repo_identity": {},
            "source_artifacts": {},
            "summary": {
                "command_count": 0,
                "required_count": 0,
                "recommended_count": 0,
                "review_command_count": 0,
                "review_first_item_count": 0,
            },
            "command_evidence": [],
            "reporting_only": True,
            "current_pr_decision_input": False,
            "execution_allowed": False,
            "decision_boundary": boundary,
        }

    errors = validate_diagnostic_execution_plan(plan)
    if errors:
        raise ValueError("invalid diagnostic execution plan: " + "; ".join(errors))
    if _string(plan.get("plan_status")) != "generated":
        raise ValueError("diagnostic execution plan status must be generated")

    policies = _as_dict(plan.get("policies"))
    required_policies = {
        "execution_default": "deny",
        "explicit_execution_authorization_required": True,
        "workspace_mode": "isolated_copy_required",
        "source_target_used_as_command_cwd": False,
        "network_default": "deny",
        "automatic_dependency_install_allowed": False,
        "source_target_mutation_allowed": False,
    }
    policy_errors = [
        key for key, expected in required_policies.items() if policies.get(key) != expected
    ]
    if policy_errors:
        raise ValueError(
            "diagnostic execution plan expands or weakens policy: " + ", ".join(policy_errors)
        )

    rules = _as_dict(plan.get("rules"))
    required_rules = (
        "plan_only",
        "read_only",
        "no_command_execution",
        "no_dependency_install",
        "no_target_repo_mutation",
        "no_patch_application",
    )
    rule_errors = [key for key in required_rules if rules.get(key) is not True]
    if rule_errors:
        raise ValueError(
            "diagnostic execution plan expands or weakens rules: " + ", ".join(rule_errors)
        )

    event = _as_dict(job.get("event"))
    job_repo = _repo_slug(event.get("repo"))
    repo_identity = _as_dict(plan.get("repo_identity"))
    plan_repo = _repo_slug(repo_identity.get("remote_url"))
    if job_repo and plan_repo and job_repo != plan_repo:
        raise ValueError(
            "diagnostic execution plan repository identity does not match diagnostic job"
        )

    commands = [_as_dict(item) for item in _as_list(plan.get("commands"))]
    review_first_items = _as_list(plan.get("review_first_items"))
    summary = _as_dict(plan.get("summary"))
    actual_summary = {
        "command_count": len(commands),
        "required_count": sum(
            _string(item.get("operator_level")) == "required" for item in commands
        ),
        "recommended_count": sum(
            _string(item.get("operator_level")) == "recommended" for item in commands
        ),
        "review_command_count": sum(_bool(item.get("review_required")) for item in commands),
        "review_first_item_count": len(review_first_items),
    }
    inconsistent = [
        key
        for key, value in actual_summary.items()
        if isinstance(summary.get(key), bool)
        or not isinstance(summary.get(key), int)
        or summary.get(key) != value
    ]
    if inconsistent:
        raise ValueError(
            "diagnostic execution plan summary does not match plan contents: "
            + ", ".join(inconsistent)
        )

    source_artifacts = {
        _string(name): _string(schema)
        for name, schema in sorted(_as_dict(plan.get("source_artifacts")).items())
        if _string(name) and _string(schema)
    }
    evidence_rows: list[JsonObject] = []
    for item in commands:
        references: list[JsonObject] = []
        for raw_reference in _as_list(item.get("evidence")):
            reference = _as_dict(raw_reference)
            if not reference:
                continue
            projected_reference: JsonObject = {
                "source": _string(reference.get("source")),
                "schema_version": _string(reference.get("schema_version")),
            }
            location = _string(reference.get("location"))
            if location:
                projected_reference["location"] = location
            paths = sorted(
                {
                    _string(raw_path)
                    for raw_path in _as_list(reference.get("paths"))
                    if _string(raw_path)
                }
            )
            if paths:
                projected_reference["paths"] = paths
            references.append(projected_reference)
        evidence_rows.append(
            {
                "step": int(item.get("step", 0) or 0),
                "command_id": _string(item.get("command_id")),
                "surface": _string(item.get("surface")) or "unknown",
                "purpose": _string(item.get("purpose")) or "unknown",
                "operator_level": _string(item.get("operator_level")) or "review_first",
                "cwd": _string(item.get("cwd")) or ".",
                "review_required": _bool(item.get("review_required")),
                "evidence": references,
                "execution_allowed": False,
            }
        )

    return {
        "schema_version": EXECUTION_PLAN_HANDOFF_SCHEMA_VERSION,
        "status": "observed",
        "plan_schema_version": DIAGNOSTIC_EXECUTION_PLAN_SCHEMA_VERSION,
        "plan_status": "generated",
        "repo_identity": {
            "name": _string(repo_identity.get("name")),
            "remote_url": _string(repo_identity.get("remote_url")),
            "job_repo": _string(event.get("repo")),
            "identity_match_checked": bool(job_repo and plan_repo),
            "identity_match": not (job_repo and plan_repo) or job_repo == plan_repo,
        },
        "source_artifacts": source_artifacts,
        "summary": actual_summary,
        "command_evidence": evidence_rows,
        "reporting_only": True,
        "current_pr_decision_input": False,
        "execution_allowed": False,
        "decision_boundary": boundary,
    }


def _primary_diagnosis(payload: Mapping[str, Any]) -> JsonObject:
    rows = [_as_dict(item) for item in _as_list(payload.get("diagnoses")) if _as_dict(item)]
    if not rows:
        return {}
    row = rows[0]
    return {
        DIAGNOSIS_ID: _string(row.get(DIAGNOSIS_ID)),
        FAILURE_SURFACE: _string(row.get(FAILURE_SURFACE)),
        HEADLINE_FAILURE: _string(row.get(HEADLINE_FAILURE)),
        ACTUAL_FAILURE: _string(row.get(ACTUAL_FAILURE)),
        RECOMMENDED_NEXT_ACTION: _string(row.get(RECOMMENDED_NEXT_ACTION)),
        REVIEW_FIRST: _bool(row.get(REVIEW_FIRST)),
        SAFE_FIX_CANDIDATE: _bool(row.get(SAFE_FIX_CANDIDATE)),
    }


def run_diagnostic_worker(
    job: Mapping[str, Any],
    *,
    check_intelligence: Mapping[str, Any] | None = None,
    evidence_graph: Mapping[str, Any] | None = None,
    pr_quality_action_report: Mapping[str, Any] | None = None,
    security_review: Mapping[str, Any] | None = None,
    runtime_proof_artifacts: Mapping[str, Any] | None = None,
    diagnostic_execution_plan: Mapping[str, Any] | None = None,
    out_dir: Path,
) -> JsonObject:
    validate_job(job)
    vector = build_diagnostic_vector(
        check_intelligence=check_intelligence,
        evidence_graph=evidence_graph,
        pr_quality_action_report=pr_quality_action_report,
        security_review=security_review,
        runtime_proof_artifacts=runtime_proof_artifacts,
        generated_at=_string(job.get("created_at")) or DEFAULT_GENERATED_AT,
    )
    vector_artifacts = write_diagnostic_vector(vector, out_dir / VECTOR_DIR)
    execution_plan_handoff = _execution_plan_handoff(job, diagnostic_execution_plan)
    return {
        "schema_version": WORKER_RESULT_SCHEMA_VERSION,
        "job_id": _string(job.get("job_id")),
        "job_type": JOB_TYPE,
        "worker": WORKER_NAME,
        "status": "completed",
        "execution_mode": EXECUTION_MODE,
        "summary": _as_dict(vector.get("summary")),
        "primary_diagnosis": _primary_diagnosis(vector),
        "execution_plan_handoff": execution_plan_handoff,
        "output_artifacts": vector_artifacts,
        "decision_boundary": _boundary(),
        "execution": {
            "proof_commands_executed": False,
            "patch_attempted": False,
            "repository_write_attempted": False,
        },
    }


def render_markdown(job: Mapping[str, Any], result: Mapping[str, Any]) -> str:
    summary = _as_dict(result.get("summary"))
    primary = _as_dict(result.get("primary_diagnosis"))
    boundary = _as_dict(result.get("decision_boundary"))
    execution_plan = _as_dict(result.get("execution_plan_handoff"))
    lines = [
        "## Local diagnostic job evidence",
        "",
        "- Evidence type: `current_pr_read_only_worker_result`",
        f"- Job ID: `{_string(job.get('job_id'))}`",
        f"- Job type: `{_string(job.get('job_type'))}`",
        f"- Worker: `{_string(result.get('worker'))}`",
        f"- Execution mode: `{_string(result.get('execution_mode'))}`",
        f"- Status: `{_string(result.get('status'))}`",
        f"- Diagnoses emitted: `{int(summary.get('diagnosis_count', 0) or 0)}`",
        f"- Review-first diagnoses: `{int(summary.get('review_first_count', 0) or 0)}`",
        f"- Safe-fix candidates observed: `{int(summary.get('safe_fix_candidate_count', 0) or 0)}`",
        f"- Primary surface: `{_string(summary.get('primary_surface') or 'none')}`",
        f"- Primary action: `{_string(summary.get('primary_action') or 'none')}`",
        (
            "- Current PR decision input: "
            f"`{str(_bool(boundary.get('current_pr_decision_input'))).lower()}`"
        ),
        (
            "- Proof commands executed by worker: "
            f"`{str(_bool(boundary.get('proof_commands_executed'))).lower()}`"
        ),
        (
            "- Patch application allowed: "
            f"`{str(_bool(boundary.get('patch_application_allowed'))).lower()}`"
        ),
        (f"- Automation allowed: `{str(_bool(boundary.get('automation_allowed'))).lower()}`"),
        (f"- Merge authorized: `{str(_bool(boundary.get('merge_authorized'))).lower()}`"),
        (
            "- Semantic equivalence proven: "
            f"`{str(_bool(boundary.get('semantic_equivalence_proven'))).lower()}`"
        ),
    ]
    if _string(execution_plan.get("status")) == "observed":
        plan_summary = _as_dict(execution_plan.get("summary"))
        lines.extend(
            [
                "",
                "### Diagnostic execution plan handoff",
                "",
                f"- Plan status: `{_string(execution_plan.get('plan_status'))}`",
                f"- Planned commands: `{int(plan_summary.get('command_count', 0) or 0)}`",
                (
                    "- Review-first plan items: "
                    f"`{int(plan_summary.get('review_first_item_count', 0) or 0)}`"
                ),
                "- Commands executed by worker: `false`",
                "- Execution allowed: `false`",
            ]
        )
    if primary:
        lines.extend(
            [
                "",
                "### Primary observed diagnosis",
                "",
                f"- Surface: `{_string(primary.get(FAILURE_SURFACE) or 'unknown')}`",
                f"- Headline: {_string(primary.get(HEADLINE_FAILURE) or 'none')}",
                f"- Actual failure: `{_string(primary.get(ACTUAL_FAILURE) or 'none')}`",
                (
                    "- Recommended next action: "
                    f"`{_string(primary.get(RECOMMENDED_NEXT_ACTION) or 'none')}`"
                ),
                f"- Review first: `{str(_bool(primary.get(REVIEW_FIRST))).lower()}`",
                (
                    "- Safe-fix candidate observed: "
                    f"`{str(_bool(primary.get(SAFE_FIX_CANDIDATE))).lower()}`"
                ),
            ]
        )
    lines.extend(
        [
            "",
            "- Interpretation: this local worker reports current PR diagnosis evidence through the existing diagnostic-vector engine; it does not execute proof, apply a patch, or authorize a merge.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_artifacts(
    job: Mapping[str, Any], result: Mapping[str, Any], *, out_dir: Path
) -> JsonObject:
    out_dir.mkdir(parents=True, exist_ok=True)
    job_path = out_dir / JOB_JSON
    result_path = out_dir / RESULT_JSON
    markdown_path = out_dir / REPORT_MD
    _write_json(job_path, job)
    _write_json(result_path, result)
    markdown_path.write_text(render_markdown(job, result), encoding="utf-8")
    return {
        "diagnostic_job_json": job_path.as_posix(),
        "diagnostic_worker_result_json": result_path.as_posix(),
        "diagnostic_job_markdown": markdown_path.as_posix(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.diagnostic_job")
    parser.add_argument("--check-intelligence", type=Path)
    parser.add_argument("--evidence-graph", type=Path)
    parser.add_argument("--pr-quality-action-report", type=Path)
    parser.add_argument("--security-review", type=Path)
    parser.add_argument("--runtime-proof-artifacts", type=Path)
    parser.add_argument("--diagnostic-execution-plan", type=Path)
    parser.add_argument("--repo", default="")
    parser.add_argument("--base-sha", default="")
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--event-name", default="local")
    parser.add_argument("--pr-number", type=int, default=0)
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    inputs = {
        "check_intelligence": str(args.check_intelligence or ""),
        "evidence_graph": str(args.evidence_graph or ""),
        "pr_quality_action_report": str(args.pr_quality_action_report or ""),
        "security_review": str(args.security_review or ""),
        "runtime_proof_artifacts": str(args.runtime_proof_artifacts or ""),
        "diagnostic_execution_plan": str(args.diagnostic_execution_plan or ""),
    }
    try:
        job = build_diagnostic_job(
            repo=args.repo,
            base_sha=args.base_sha,
            head_sha=args.head_sha,
            event_name=args.event_name,
            pr_number=args.pr_number,
            input_artifacts=inputs,
            generated_at=args.generated_at,
        )
        result = run_diagnostic_worker(
            job,
            check_intelligence=_read_json(args.check_intelligence),
            evidence_graph=_read_json(args.evidence_graph),
            pr_quality_action_report=_read_json(args.pr_quality_action_report),
            security_review=_read_json(args.security_review),
            runtime_proof_artifacts=_read_json(args.runtime_proof_artifacts),
            diagnostic_execution_plan=_read_json(args.diagnostic_execution_plan),
            out_dir=args.out_dir,
        )
        artifacts = write_artifacts(job, result, out_dir=args.out_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(
            json.dumps(
                {
                    "artifacts": artifacts,
                    "job_id": job["job_id"],
                    "summary": result["summary"],
                    "execution_plan_handoff": result["execution_plan_handoff"],
                    "decision_boundary": result["decision_boundary"],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(f"diagnostic_job_json: {artifacts['diagnostic_job_json']}")
        print(f"diagnostic_worker_result_json: {artifacts['diagnostic_worker_result_json']}")
        print(f"diagnostic_job_markdown: {artifacts['diagnostic_job_markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
