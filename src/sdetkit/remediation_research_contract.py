from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

CONTRACT_SCHEMA = "sdetkit.remediation_research_contract.v1"
EVIDENCE_SCHEMA = "sdetkit.remediation_research_evidence.v1"
REPORT_SCHEMA = "sdetkit.remediation_research_report.v1"
DEFAULT_CONTRACT = "docs/contracts/remediation-research.v1.json"
GENERATOR_SOURCE = "src/sdetkit/remediation_research_contract.py"
AUTHORITY_FIELDS = (
    "automation_allowed",
    "patch_application_allowed",
    "merge_authorized",
    "publication_authorized",
    "security_dismissal_allowed",
    "semantic_equivalence_proven",
)


def authority_boundary() -> dict[str, bool]:
    return {field: False for field in AUTHORITY_FIELDS}


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def load_object(path: str | Path) -> dict[str, Any]:
    resolved = Path(path)
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"invalid JSON object: {resolved}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {resolved}")
    return payload


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _digest_parts(parts: list[tuple[str, bytes]]) -> str:
    hasher = hashlib.sha256()
    for label, content in sorted(parts):
        label_bytes = label.encode("utf-8")
        hasher.update(len(label_bytes).to_bytes(8, "big"))
        hasher.update(label_bytes)
        hasher.update(len(content).to_bytes(8, "big"))
        hasher.update(content)
    return hasher.hexdigest()


def _schema(payload: dict[str, Any]) -> str:
    return str(payload.get("schema_version", "")).strip()


def _display(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _is_sha256(value: str) -> bool:
    return re.fullmatch(r"[0-9a-fA-F]{64}", value) is not None


def _is_commit_sha(value: str) -> bool:
    return re.fullmatch(r"[0-9a-fA-F]{7,64}", value) is not None


def _is_repo_name(value: str) -> bool:
    return re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value) is not None


def _is_identifier(value: str) -> bool:
    return re.fullmatch(r"[a-z][a-z0-9_]{1,63}", value) is not None


def _is_safe_repo_path(value: str) -> bool:
    path = value.strip().replace("\\", "/")
    if not path or path.startswith(("/", "~")):
        return False
    if path in {".", ".."} or "/../" in f"/{path}/":
        return False
    return "<" not in path and ">" not in path


def _string_list(value: object, field: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{field} must be a list of strings")
        return []
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{field} must contain only non-empty strings")
            continue
        normalized = item.strip()
        if normalized not in result:
            result.append(normalized)
    return result


def _safe_path_list(value: object, field: str, errors: list[str]) -> list[str]:
    paths = _string_list(value, field, errors)
    unsafe = [path for path in paths if not _is_safe_repo_path(path)]
    if unsafe:
        errors.append(f"{field} contains unsafe repository paths: {', '.join(sorted(unsafe))}")
    return sorted(path for path in paths if path not in unsafe)


def _inventory(
    value: object, field: str, expected_paths: set[str], errors: list[str]
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        errors.append(f"{field} must be a list")
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(value, 1):
        item = _as_dict(raw)
        path = str(item.get("path", "")).strip().replace("\\", "/")
        digest = str(item.get("sha256", "")).strip().lower()
        size_bytes = item.get("size_bytes")
        if not _is_safe_repo_path(path):
            errors.append(f"{field}[{index}].path must be a safe repository path")
            continue
        if path in seen:
            errors.append(f"{field} contains duplicate path: {path}")
            continue
        if not _is_sha256(digest):
            errors.append(f"{field}[{index}].sha256 must be sha256")
            continue
        if not isinstance(size_bytes, int) or isinstance(size_bytes, bool) or size_bytes < 0:
            errors.append(f"{field}[{index}].size_bytes must be a non-negative integer")
            continue
        seen.add(path)
        result.append({"path": path, "sha256": digest, "size_bytes": size_bytes})
    actual_paths = {item["path"] for item in result}
    if actual_paths != expected_paths:
        errors.append(
            f"{field} paths must exactly match pr_owned_scope; "
            f"expected={sorted(expected_paths)} actual={sorted(actual_paths)}"
        )
    return sorted(result, key=lambda item: item["path"])


def _artifacts(value: object, field: str, errors: list[str]) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        errors.append(f"{field} must be a non-empty list")
        return []
    result: list[dict[str, str]] = []
    for index, raw in enumerate(value, 1):
        item = _as_dict(raw)
        path = str(item.get("path", "")).strip().replace("\\", "/")
        digest = str(item.get("sha256", "")).strip().lower()
        if not _is_safe_repo_path(path):
            errors.append(f"{field}[{index}].path must be a safe repository path")
            continue
        if not _is_sha256(digest):
            errors.append(f"{field}[{index}].sha256 must be sha256")
            continue
        result.append({"path": path, "sha256": digest})
    return sorted(result, key=lambda item: item["path"])


def _proof_record(
    value: object, field: str, allowed_statuses: set[str], errors: list[str]
) -> dict[str, Any]:
    item = _as_dict(value)
    status = str(item.get("status", "")).strip()
    commands = _string_list(item.get("commands"), f"{field}.commands", errors)
    artifacts = _artifacts(item.get("artifacts"), f"{field}.artifacts", errors)
    notes = str(item.get("notes", "")).strip()
    if status not in allowed_statuses:
        errors.append(f"{field}.status must be one of {sorted(allowed_statuses)}")
    if not notes:
        errors.append(f"{field}.notes must be non-empty")
    return {
        "status": status,
        "commands": commands,
        "artifacts": artifacts,
        "notes": notes,
    }


def _proposed_diff(
    value: object, expected_paths: set[str], errors: list[str]
) -> dict[str, Any]:
    item = _as_dict(value)
    artifact_path = str(item.get("artifact_path", "")).strip().replace("\\", "/")
    digest = str(item.get("sha256", "")).strip().lower()
    files = _safe_path_list(item.get("files"), "proposed_diff.files", errors)
    line_count = item.get("line_count")
    if not _is_safe_repo_path(artifact_path):
        errors.append("proposed_diff.artifact_path must be a safe repository path")
    if not _is_sha256(digest):
        errors.append("proposed_diff.sha256 must be sha256")
    if not isinstance(line_count, int) or isinstance(line_count, bool) or line_count < 0:
        errors.append("proposed_diff.line_count must be a non-negative integer")
    if set(files) != expected_paths:
        errors.append("proposed_diff.files must exactly match pr_owned_scope")
    return {
        "artifact_path": artifact_path,
        "sha256": digest,
        "files": files,
        "line_count": line_count,
    }


def _rollback_record(value: object, errors: list[str]) -> dict[str, Any]:
    item = _as_dict(value)
    strategy = str(item.get("strategy", "")).strip()
    verified = item.get("verified")
    artifact_path = str(item.get("artifact_path", "")).strip().replace("\\", "/")
    digest = str(item.get("sha256", "")).strip().lower()
    restored_inventory_sha256 = str(item.get("restored_inventory_sha256", "")).strip().lower()
    notes = str(item.get("notes", "")).strip()
    if not strategy:
        errors.append("rollback.strategy must be non-empty")
    if not isinstance(verified, bool):
        errors.append("rollback.verified must be boolean")
    if not _is_safe_repo_path(artifact_path):
        errors.append("rollback.artifact_path must be a safe repository path")
    if not _is_sha256(digest):
        errors.append("rollback.sha256 must be sha256")
    if not _is_sha256(restored_inventory_sha256):
        errors.append("rollback.restored_inventory_sha256 must be sha256")
    if not notes:
        errors.append("rollback.notes must be non-empty")
    return {
        "strategy": strategy,
        "verified": verified,
        "artifact_path": artifact_path,
        "sha256": digest,
        "restored_inventory_sha256": restored_inventory_sha256,
        "notes": notes,
    }


def _reviewer_record(
    value: object, allowed_decisions: set[str], errors: list[str]
) -> dict[str, str]:
    item = _as_dict(value)
    reviewer_id = str(item.get("reviewer_id", "")).strip()
    reviewed_at = str(item.get("reviewed_at", "")).strip()
    decision = str(item.get("decision", "")).strip()
    notes = str(item.get("notes", "")).strip()
    if not reviewer_id:
        errors.append("reviewer_record.reviewer_id must be non-empty")
    try:
        parsed = datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
    except ValueError:
        errors.append("reviewer_record.reviewed_at must be RFC3339")
    else:
        if parsed.tzinfo is None:
            errors.append("reviewer_record.reviewed_at must include timezone")
    if decision not in allowed_decisions:
        errors.append(f"reviewer_record.decision must be one of {sorted(allowed_decisions)}")
    if not notes:
        errors.append("reviewer_record.notes must be non-empty")
    return {
        "reviewer_id": reviewer_id,
        "reviewed_at": reviewed_at,
        "decision": decision,
        "notes": notes,
    }


def _scenario_records(
    value: object,
    expectations: dict[str, str],
    allowed_outcomes: set[str],
    errors: list[str],
) -> dict[str, dict[str, str]]:
    raw = _as_dict(value)
    missing = sorted(set(expectations) - set(raw))
    extra = sorted(set(raw) - set(expectations))
    if missing:
        errors.append(f"scenarios missing required entries: {', '.join(missing)}")
    if extra:
        errors.append(f"scenarios contain unsupported entries: {', '.join(extra)}")
    result: dict[str, dict[str, str]] = {}
    for scenario_id in sorted(expectations):
        item = _as_dict(raw.get(scenario_id))
        outcome = str(item.get("outcome", "")).strip()
        artifact_path = str(item.get("artifact_path", "")).strip().replace("\\", "/")
        digest = str(item.get("sha256", "")).strip().lower()
        notes = str(item.get("notes", "")).strip()
        if outcome not in allowed_outcomes:
            errors.append(f"scenarios.{scenario_id}.outcome must be one of {sorted(allowed_outcomes)}")
        if not _is_safe_repo_path(artifact_path):
            errors.append(f"scenarios.{scenario_id}.artifact_path must be a safe repository path")
        if not _is_sha256(digest):
            errors.append(f"scenarios.{scenario_id}.sha256 must be sha256")
        if not notes:
            errors.append(f"scenarios.{scenario_id}.notes must be non-empty")
        result[scenario_id] = {
            "outcome": outcome,
            "artifact_path": artifact_path,
            "sha256": digest,
            "notes": notes,
        }
    return result


def _validate_contract(contract: dict[str, Any]) -> None:
    if _schema(contract) != CONTRACT_SCHEMA:
        raise ValueError(f"contract schema_version must be {CONTRACT_SCHEMA}")
    if contract.get("evidence_schema_version") != EVIDENCE_SCHEMA:
        raise ValueError(f"contract evidence_schema_version must be {EVIDENCE_SCHEMA}")
    if contract.get("report_schema_version") != REPORT_SCHEMA:
        raise ValueError(f"contract report_schema_version must be {REPORT_SCHEMA}")
    authority = _as_dict(contract.get("authority_boundary"))
    if set(authority) != set(AUTHORITY_FIELDS) or any(authority.values()):
        raise ValueError("contract authority_boundary must deny every authority field")
    if not _as_list(contract.get("allowed_candidate_families")):
        raise ValueError("contract allowed_candidate_families must be non-empty")
    if not _as_dict(contract.get("required_scenarios")):
        raise ValueError("contract required_scenarios must be non-empty")


def normalize_evidence(
    evidence: dict[str, Any], contract: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    required_fields = {
        str(value).strip()
        for value in _as_list(contract.get("required_evidence_fields"))
        if str(value).strip()
    }
    missing_fields = sorted(required_fields - set(evidence))
    if missing_fields:
        errors.append(f"evidence missing required fields: {', '.join(missing_fields)}")

    schema_version = str(evidence.get("schema_version", "")).strip()
    if schema_version != EVIDENCE_SCHEMA:
        errors.append(f"evidence schema_version must be {EVIDENCE_SCHEMA}")

    candidate_family = str(evidence.get("candidate_family", "")).strip()
    allowed_families = {
        str(value).strip()
        for value in _as_list(contract.get("allowed_candidate_families"))
        if str(value).strip()
    }
    if candidate_family not in allowed_families:
        errors.append(f"candidate_family must be one of {sorted(allowed_families)}")

    failure_class = str(evidence.get("failure_class", "")).strip()
    if not _is_identifier(failure_class):
        errors.append("failure_class must be an exact lower_snake_case identifier")

    source_repository = str(evidence.get("source_repository", "")).strip()
    if not _is_repo_name(source_repository):
        errors.append("source_repository must be owner/name")

    source_commit_sha = str(evidence.get("source_commit_sha", "")).strip().lower()
    if not _is_commit_sha(source_commit_sha):
        errors.append("source_commit_sha must be hexadecimal")

    pr_number = evidence.get("pr_number")
    if not isinstance(pr_number, int) or isinstance(pr_number, bool) or pr_number <= 0:
        errors.append("pr_number must be a positive integer")

    scope = _safe_path_list(evidence.get("pr_owned_scope"), "pr_owned_scope", errors)
    if not scope:
        errors.append("pr_owned_scope must be non-empty")
    expected_paths = set(scope)

    before_inventory = _inventory(
        evidence.get("before_inventory"), "before_inventory", expected_paths, errors
    )
    after_inventory = _inventory(
        evidence.get("after_inventory"), "after_inventory", expected_paths, errors
    )
    proposed_diff = _proposed_diff(evidence.get("proposed_diff"), expected_paths, errors)

    allowed_proof_statuses = {
        str(value).strip()
        for value in _as_list(contract.get("allowed_proof_statuses"))
        if str(value).strip()
    }
    focused_proof = _proof_record(
        evidence.get("focused_proof"), "focused_proof", allowed_proof_statuses, errors
    )
    full_proof = _proof_record(
        evidence.get("full_proof"), "full_proof", allowed_proof_statuses, errors
    )
    rollback = _rollback_record(evidence.get("rollback"), errors)

    allowed_decisions = {
        str(value).strip()
        for value in _as_list(contract.get("allowed_reviewer_decisions"))
        if str(value).strip()
    }
    reviewer_record = _reviewer_record(
        evidence.get("reviewer_record"), allowed_decisions, errors
    )

    false_authority_count = evidence.get("false_authority_count")
    if (
        not isinstance(false_authority_count, int)
        or isinstance(false_authority_count, bool)
        or false_authority_count < 0
    ):
        errors.append("false_authority_count must be a non-negative integer")

    limitations = _string_list(evidence.get("limitations"), "limitations", errors)
    if not limitations:
        errors.append("limitations must be non-empty")

    expectations = {
        str(key): str(value)
        for key, value in _as_dict(contract.get("required_scenarios")).items()
    }
    allowed_outcomes = {
        str(value).strip()
        for value in _as_list(contract.get("allowed_scenario_outcomes"))
        if str(value).strip()
    }
    scenarios = _scenario_records(
        evidence.get("scenarios"), expectations, allowed_outcomes, errors
    )

    normalized = {
        "schema_version": schema_version,
        "candidate_family": candidate_family,
        "failure_class": failure_class,
        "source_repository": source_repository,
        "source_commit_sha": source_commit_sha,
        "pr_number": pr_number,
        "pr_owned_scope": scope,
        "before_inventory": before_inventory,
        "after_inventory": after_inventory,
        "proposed_diff": proposed_diff,
        "focused_proof": focused_proof,
        "full_proof": full_proof,
        "rollback": rollback,
        "reviewer_record": reviewer_record,
        "false_authority_count": false_authority_count,
        "limitations": limitations,
        "scenarios": scenarios,
    }
    return normalized, errors


def _readiness_reasons(normalized: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if _as_dict(normalized.get("focused_proof")).get("status") != "pass":
        reasons.append("focused_proof_not_passed")
    if _as_dict(normalized.get("full_proof")).get("status") != "pass":
        reasons.append("full_proof_not_passed")
    if _as_dict(normalized.get("rollback")).get("verified") is not True:
        reasons.append("rollback_not_verified")
    if _as_dict(normalized.get("reviewer_record")).get("decision") != "accept":
        reasons.append("reviewer_has_not_accepted")
    if normalized.get("false_authority_count") != 0:
        reasons.append("false_authority_count_nonzero")
    expectations = {
        str(key): str(value)
        for key, value in _as_dict(contract.get("required_scenarios")).items()
    }
    scenarios = _as_dict(normalized.get("scenarios"))
    for scenario_id, expected_outcome in sorted(expectations.items()):
        actual_outcome = _as_dict(scenarios.get(scenario_id)).get("outcome")
        if actual_outcome != expected_outcome:
            reasons.append(
                f"scenario_outcome_mismatch:{scenario_id}:expected={expected_outcome}:actual={actual_outcome}"
            )
    return reasons


def input_provenance(
    evidence_json: str | Path,
    *,
    contract_json: str | Path = DEFAULT_CONTRACT,
    generator_path: str | Path | None = None,
    root: str | Path = ".",
) -> dict[str, Any]:
    repo_root = Path(root).resolve()
    evidence_path = Path(evidence_json).resolve()
    contract_path = Path(contract_json).resolve()
    generator = Path(generator_path).resolve() if generator_path else Path(__file__).resolve()
    evidence_bytes = evidence_path.read_bytes()
    contract_bytes = contract_path.read_bytes()
    generator_bytes = generator.read_bytes()
    parts = [
        ("contract_schema", CONTRACT_SCHEMA.encode()),
        ("evidence_schema", EVIDENCE_SCHEMA.encode()),
        ("report_schema", REPORT_SCHEMA.encode()),
        ("contract_json", contract_bytes),
        ("evidence_json", evidence_bytes),
        (GENERATOR_SOURCE, generator_bytes),
    ]
    return {
        "digest_algorithm": "sha256",
        "input_digest": _digest_parts(parts),
        "input_count": len(parts),
        "generator_schema_version": REPORT_SCHEMA,
        "generator_source": GENERATOR_SOURCE,
        "generator_sha256": _sha256_bytes(generator_bytes),
        "contract_path": _display(repo_root, contract_path),
        "contract_sha256": _sha256_bytes(contract_bytes),
        "contract_schema_version": _schema(load_object(contract_path)),
        "evidence_path": _display(repo_root, evidence_path),
        "evidence_sha256": _sha256_bytes(evidence_bytes),
        "evidence_schema_version": _schema(load_object(evidence_path)),
    }


def build_report(
    evidence_json: str | Path,
    *,
    contract_json: str | Path = DEFAULT_CONTRACT,
    generator_path: str | Path | None = None,
    root: str | Path = ".",
) -> dict[str, Any]:
    contract = load_object(contract_json)
    _validate_contract(contract)
    evidence = load_object(evidence_json)
    normalized, validation_errors = normalize_evidence(evidence, contract)
    readiness_reasons = [] if validation_errors else _readiness_reasons(normalized, contract)
    ok = not validation_errors
    status = "review_ready" if ok and not readiness_reasons else "review_required"
    boundary = authority_boundary()
    expectations = _as_dict(contract.get("required_scenarios"))
    scenarios = _as_dict(normalized.get("scenarios"))
    return {
        "schema_version": REPORT_SCHEMA,
        "report_status": status,
        "ok": ok,
        "input_provenance": input_provenance(
            evidence_json,
            contract_json=contract_json,
            generator_path=generator_path,
            root=root,
        ),
        "candidate": {
            "candidate_family": normalized.get("candidate_family"),
            "failure_class": normalized.get("failure_class"),
            "source_repository": normalized.get("source_repository"),
            "source_commit_sha": normalized.get("source_commit_sha"),
            "pr_number": normalized.get("pr_number"),
            "pr_owned_scope": normalized.get("pr_owned_scope", []),
        },
        "normalized_evidence": normalized,
        "validation_errors": validation_errors,
        "readiness_reasons": readiness_reasons,
        "scenario_summary": [
            {
                "scenario_id": scenario_id,
                "expected_outcome": expectations[scenario_id],
                "actual_outcome": _as_dict(scenarios.get(scenario_id)).get("outcome"),
                "matches_expectation": _as_dict(scenarios.get(scenario_id)).get("outcome")
                == expectations[scenario_id],
            }
            for scenario_id in sorted(expectations)
        ],
        "rules": dict(_as_dict(contract.get("rules"))),
        "authority_boundary": boundary,
        **boundary,
    }


def render_markdown(report: dict[str, Any]) -> str:
    candidate = _as_dict(report.get("candidate"))
    lines = [
        "# Remediation research contract report",
        "",
        f"- Status: `{report.get('report_status', 'unknown')}`",
        f"- Structurally valid: `{str(report.get('ok', False)).lower()}`",
        f"- Candidate family: `{candidate.get('candidate_family', 'unknown')}`",
        f"- Failure class: `{candidate.get('failure_class', 'unknown')}`",
        f"- Source: `{candidate.get('source_repository', 'unknown')}@{candidate.get('source_commit_sha', 'unknown')}`",
        f"- PR: `{candidate.get('pr_number', 'unknown')}`",
        "",
        "## Scenario summary",
        "",
    ]
    for item in _as_list(report.get("scenario_summary")):
        row = _as_dict(item)
        lines.append(
            "- "
            f"`{row.get('scenario_id', 'unknown')}`: expected={row.get('expected_outcome')} "
            f"actual={row.get('actual_outcome')} match={row.get('matches_expectation')}"
        )
    validation_errors = [str(value) for value in _as_list(report.get("validation_errors"))]
    if validation_errors:
        lines.extend(["", "## Validation errors", ""])
        lines.extend(f"- {value}" for value in validation_errors)
    readiness_reasons = [str(value) for value in _as_list(report.get("readiness_reasons"))]
    if readiness_reasons:
        lines.extend(["", "## Readiness reasons", ""])
        lines.extend(f"- `{value}`" for value in readiness_reasons)
    lines.extend(
        [
            "",
            "## Authority boundary",
            "",
            "This report validates and summarizes evidence only. It does not authorize patch application, merge, publication, security dismissal, automation, or semantic-equivalence claims.",
            "",
        ]
    )
    return "\n".join(lines)


def run_file(
    evidence_json: str | Path,
    *,
    contract_json: str | Path = DEFAULT_CONTRACT,
    out_json: str | Path | None = None,
    out_md: str | Path | None = None,
    generator_path: str | Path | None = None,
    root: str | Path = ".",
) -> dict[str, Any]:
    report = build_report(
        evidence_json,
        contract_json=contract_json,
        generator_path=generator_path,
        root=root,
    )
    if out_json is not None:
        path = Path(out_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if out_md is not None:
        path = Path(out_md)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_markdown(report), encoding="utf-8")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.remediation_research_contract")
    parser.add_argument("evidence_json")
    parser.add_argument("--contract-json", default=DEFAULT_CONTRACT)
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = run_file(
            args.evidence_json,
            contract_json=args.contract_json,
            out_json=args.out_json or None,
            out_md=args.out_md or None,
            root=args.root,
        )
    except ValueError as exc:
        print(f"error={exc}")
        return 2
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"status: {report['report_status']}")
        print(f"ok: {str(report['ok']).lower()}")
        for error in report.get("validation_errors", []):
            print(f"validation_error: {error}")
        for reason in report.get("readiness_reasons", []):
            print(f"readiness_reason: {reason}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
