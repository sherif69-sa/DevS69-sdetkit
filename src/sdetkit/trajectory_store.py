from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.trajectory.v1"
DEFAULT_GENERATED_AT = "1970-01-01T00:00:00Z"
DEFAULT_OUT = str(Path("build") / "sdetkit" / "trajectory.jsonl")

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


def _string_list(value: Any) -> list[str]:
    return sorted({_string(item) for item in _as_list(value) if _string(item)})


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"


def _read_json(path: Path | None) -> JsonObject:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"expected JSON object in {path}"
        raise ValueError(msg)
    return payload


def _write_jsonl(path: Path, records: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(record, sort_keys=True) for record in records]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _diagnoses_by_id(diagnostic_vector: Mapping[str, Any]) -> dict[str, JsonObject]:
    diagnoses: dict[str, JsonObject] = {}
    for item in _as_list(diagnostic_vector.get("diagnoses")):
        diagnosis = _as_dict(item)
        diagnosis_id = _string(diagnosis.get("diagnosis_id"))
        if diagnosis_id:
            diagnoses[diagnosis_id] = diagnosis
    return diagnoses


def _plans(
    remediation_plan: Mapping[str, Any], diagnoses: Mapping[str, JsonObject]
) -> list[JsonObject]:
    plan_rows = [_as_dict(item) for item in _as_list(remediation_plan.get("plans"))]
    if plan_rows:
        return [row for row in plan_rows if row]

    generated: list[JsonObject] = []
    for diagnosis_id, diagnosis in diagnoses.items():
        review_first = _bool(diagnosis.get("review_first"))
        safe_candidate = _bool(diagnosis.get("safe_fix_candidate")) and not review_first
        failure_vector = _as_dict(diagnosis.get("failure_vector"))
        generated.append(
            {
                "diagnosis_id": diagnosis_id,
                "failure_surface": _string(diagnosis.get("failure_surface")) or "unknown",
                "classification": _string(failure_vector.get("failure_class")) or "unknown",
                "safe_to_auto_fix": safe_candidate,
                "allowed_strategy": _string(diagnosis.get("recommended_next_action"))
                or "collect_logs_and_classify",
                "blocked_reason": "" if safe_candidate else "review-first diagnosis",
                "affected_files": _string_list(diagnosis.get("affected_files")),
                "commands_to_run": [],
                "proof_commands": _string_list(diagnosis.get("proof_commands")),
                "human_review_action": "review diagnosis and run focused proof",
                "history_context": _string(diagnosis.get("history_context")) or "unknown",
            }
        )
    return generated


def _first_command(plan: Mapping[str, Any]) -> str:
    commands = _string_list(plan.get("commands_to_run"))
    if commands:
        return commands[0]
    proof_commands = _string_list(plan.get("proof_commands"))
    if proof_commands:
        return proof_commands[0]
    return "none"


def _response_type(plan: Mapping[str, Any], diagnosis: Mapping[str, Any]) -> str:
    if _bool(plan.get("safe_to_auto_fix")):
        return "safe_fix_candidate"
    surface = _string(plan.get("failure_surface")) or _string(diagnosis.get("failure_surface"))
    if surface == "unknown":
        return "unknown_review_required"
    if surface:
        return f"{surface}_review_required"
    return "review_required"


def _final_result(plan: Mapping[str, Any], safe_fix_outcome: Mapping[str, Any]) -> str:
    if safe_fix_outcome:
        if _bool(safe_fix_outcome.get("remediation_ok")):
            return "proof_passed"
        if _bool(safe_fix_outcome.get("attempted")):
            return "proof_failed"
    if _bool(plan.get("safe_to_auto_fix")):
        return "safe_fix_candidate"
    return "review_required"


def _trajectory_id(*, repo: str, commit_sha: str, diagnosis_id: str, action: str) -> str:
    basis = "|".join((repo or "repo", commit_sha or "head", diagnosis_id, action))
    return _slug(basis)


def build_trajectory_records(
    *,
    diagnostic_vector: Mapping[str, Any],
    remediation_plan: Mapping[str, Any] | None = None,
    safe_fix_outcome: Mapping[str, Any] | None = None,
    repo: str = "",
    branch: str = "",
    commit_sha: str = "",
    pr_number: int = 0,
    generated_at: str = DEFAULT_GENERATED_AT,
) -> list[JsonObject]:
    diagnoses = _diagnoses_by_id(diagnostic_vector)
    plans = _plans(_as_dict(remediation_plan), diagnoses)
    outcome = _as_dict(safe_fix_outcome)

    records: list[JsonObject] = []
    for plan in plans:
        diagnosis_id = _string(plan.get("diagnosis_id")) or "unknown"
        diagnosis = diagnoses.get(diagnosis_id, {})
        failure_vector = _as_dict(diagnosis.get("failure_vector"))
        action = _string(plan.get("allowed_strategy")) or "collect_logs_and_classify"
        auto_fix_allowed = _bool(plan.get("safe_to_auto_fix"))
        proof_commands = _string_list(plan.get("proof_commands"))
        owner_files = _string_list(diagnosis.get("likely_owner_files")) or _string_list(
            plan.get("affected_files")
        )

        records.append(
            {
                "schema_version": SCHEMA_VERSION,
                "trajectory_id": _trajectory_id(
                    repo=repo,
                    commit_sha=commit_sha,
                    diagnosis_id=diagnosis_id,
                    action=action,
                ),
                "repo": repo,
                "branch": branch,
                "commit_sha": commit_sha,
                "pr_number": pr_number,
                "attempt_number": 1,
                "generated_at": generated_at,
                "diagnostic_id": diagnosis_id,
                "action": action,
                "command": _first_command(plan),
                "environment": {
                    "runner": _string(failure_vector.get("environment")) or "unknown",
                    "source": "trajectory_store",
                },
                "response": {
                    "response_type": _response_type(plan, diagnosis),
                    "exit_code": failure_vector.get("exit_code", "unknown"),
                    "first_failing_line": _string(
                        diagnosis.get("first_failure_line")
                        or failure_vector.get("first_failing_line")
                    ),
                },
                "diagnosis": {
                    "failure_class": _string(
                        failure_vector.get("failure_class") or plan.get("classification")
                    )
                    or "unknown",
                    "risk_surface": _string(
                        failure_vector.get("risk_surface") or plan.get("failure_surface")
                    )
                    or "unknown",
                    "root_cause": _string(
                        diagnosis.get("actual_failure") or failure_vector.get("actual_failure")
                    ),
                    "owner_files": owner_files,
                    "confidence": _string(diagnosis.get("confidence")) or "medium",
                },
                "decision": {
                    "review_first": not auto_fix_allowed,
                    "auto_fix_allowed": auto_fix_allowed,
                    "reason": _string(plan.get("blocked_reason"))
                    or "safe mechanical remediation candidate",
                },
                "fix": {
                    "allowed_strategy": action,
                    "patch_files": _string_list(plan.get("affected_files"))
                    if auto_fix_allowed
                    else [],
                    "blocked_reason": _string(plan.get("blocked_reason")),
                },
                "proof": {
                    "commands": proof_commands,
                    "focused_proof": "not_run",
                    "quality_proof": "not_run",
                    "verifier_result": "not_run",
                },
                "final_result": _final_result(plan, outcome),
                "learned_pattern": _string(plan.get("history_context")) or "unknown",
            }
        )

    return records


def summarize_trajectory_records(records: list[Mapping[str, Any]]) -> JsonObject:
    return {
        "schema_version": SCHEMA_VERSION,
        "record_count": len(records),
        "review_first_count": sum(
            1 for record in records if _as_dict(record.get("decision")).get("review_first") is True
        ),
        "auto_fix_allowed_count": sum(
            1
            for record in records
            if _as_dict(record.get("decision")).get("auto_fix_allowed") is True
        ),
    }


def write_trajectory_records(records: list[Mapping[str, Any]], out: Path) -> JsonObject:
    _write_jsonl(out, records)
    summary = summarize_trajectory_records(records)
    summary["trajectory_jsonl"] = out.as_posix()
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.trajectory_store")
    parser.add_argument("--diagnostic-vector", required=True)
    parser.add_argument("--remediation-plan", default="")
    parser.add_argument("--safe-fix-outcome", default="")
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--repo", default="")
    parser.add_argument("--branch", default="")
    parser.add_argument("--commit-sha", default="")
    parser.add_argument("--pr-number", type=int, default=0)
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def _optional_path(value: str) -> Path | None:
    return Path(value) if value else None


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        records = build_trajectory_records(
            diagnostic_vector=_read_json(Path(args.diagnostic_vector)),
            remediation_plan=_read_json(_optional_path(args.remediation_plan)),
            safe_fix_outcome=_read_json(_optional_path(args.safe_fix_outcome)),
            repo=args.repo,
            branch=args.branch,
            commit_sha=args.commit_sha,
            pr_number=args.pr_number,
            generated_at=args.generated_at,
        )
        summary = write_trajectory_records(records, Path(args.out))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(json.dumps({"summary": summary}, indent=2, sort_keys=True))
    else:
        print(f"trajectory_jsonl: {summary['trajectory_jsonl']}")
        print(f"record_count: {summary['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
