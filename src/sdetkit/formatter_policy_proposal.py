from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from sdetkit import formatter_candidate_verifier, remediation_research_contract

SCHEMA_VERSION = "sdetkit.formatter_policy_proposal.v1"
APPROVAL_SCHEMA_VERSION = "sdetkit.formatter_policy_approval.v1"
CONTRACT_SCHEMA_VERSION = "sdetkit.formatter_policy_proposal_contract.v1"
DEFAULT_CONTRACT = Path("docs/contracts/formatter-policy-proposal.v1.json")
DEFAULT_OUT_DIR = Path("build") / "formatter-policy-proposal"
REPORT_JSON = "formatter-policy-proposal.json"
REPORT_MD = "formatter-policy-proposal.md"

JsonObject = dict[str, Any]

REQUIRED_VERIFIER_FILES = (
    formatter_candidate_verifier.REPORT_JSON,
    formatter_candidate_verifier.PROTECTED_VERIFIER_JSON,
    formatter_candidate_verifier.REPLAY_REPORT_JSON,
    formatter_candidate_verifier.TRAJECTORY_JSONL,
    formatter_candidate_verifier.REPO_MEMORY_JSON,
    formatter_candidate_verifier.CONTROLLED_VALIDATION_JSON,
)

AUTHORITY_FIELDS = (
    "automation_allowed",
    "patch_application_allowed",
    "merge_authorized",
    "publication_authorized",
    "security_dismissal_allowed",
    "semantic_equivalence_proven",
)


def _as_dict(value: object) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def _string(value: object) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _read_json(path: Path) -> JsonObject:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(root.iterdir())
        if path.is_file()
    }


def _artifact(root: Path, filename: str) -> Path:
    path = root / filename
    if path.is_symlink():
        raise ValueError(f"policy proposal evidence cannot use a symlink: {filename}")
    resolved_root = root.resolve()
    resolved = path.resolve()
    if resolved.parent != resolved_root or not resolved.is_file():
        raise ValueError(f"policy proposal evidence artifact is missing or shadowed: {filename}")
    return resolved


def _assert_authority_denied(payload: Mapping[str, Any], *, source: str) -> None:
    expanded = [field for field in AUTHORITY_FIELDS if _bool(payload.get(field))]
    if expanded:
        raise ValueError(f"{source} expands authority: {', '.join(expanded)}")


def _assert_boundary_denied(payload: Mapping[str, Any], *, source: str) -> None:
    aliases = {
        "automation_allowed": "automation_allowed",
        "patch_application_allowed": "patch_application_allowed",
        "merge_authorized": "merge_authorized",
        "publication_authorized": "publication_authorized",
        "security_dismissal_allowed": "security_dismissal_allowed",
        "semantic_equivalence_proven": "semantic_equivalence_proven",
        "semantic_equivalence_claim": "semantic_equivalence_proven",
    }
    expanded = sorted({target for key, target in aliases.items() if _bool(payload.get(key))})
    if expanded:
        raise ValueError(f"{source} expands authority: {', '.join(expanded)}")


def _validate_timestamp(value: str, *, field: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be RFC3339") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include timezone")


def _validate_contract(contract: Mapping[str, Any]) -> None:
    if _string(contract.get("schema_version")) != CONTRACT_SCHEMA_VERSION:
        raise ValueError(f"contract schema_version must be {CONTRACT_SCHEMA_VERSION}")
    if contract.get("allowed_candidate_families") != ["formatter_only"]:
        raise ValueError("contract must allow exactly formatter_only")
    if contract.get("promotion_mode") != "proposal_only":
        raise ValueError("contract promotion_mode must be proposal_only")
    boundary = _as_dict(contract.get("authority_boundary"))
    _assert_authority_denied(boundary, source="policy proposal contract")
    if any(value is not False for value in boundary.values()):
        raise ValueError("policy proposal contract authority boundary must be explicitly false")


def _validate_approval(
    approval: Mapping[str, Any],
    *,
    verifier_report: Mapping[str, Any],
    verifier_report_sha256: str,
) -> JsonObject:
    if _string(approval.get("schema_version")) != APPROVAL_SCHEMA_VERSION:
        raise ValueError(f"approval schema_version must be {APPROVAL_SCHEMA_VERSION}")
    if _string(approval.get("provider")) != "github":
        raise ValueError("approval provider must be github")
    if not _bool(approval.get("provider_identity_verified")):
        raise ValueError("approval identity must be verified by the provider")
    reviewer_id = _string(approval.get("reviewer_id"))
    if not reviewer_id:
        raise ValueError("approval reviewer_id must be non-empty")
    approved_at = _string(approval.get("approved_at"))
    _validate_timestamp(approved_at, field="approval approved_at")
    if _string(approval.get("decision")) != "approve_proposal":
        raise ValueError("approval decision must be approve_proposal")
    if not _bool(approval.get("limitations_acknowledged")):
        raise ValueError("approval must acknowledge proposal limitations")

    source_repository = _string(verifier_report.get("source_repository"))
    source_commit_sha = _string(verifier_report.get("source_commit_sha"))
    source_pr_number = int(verifier_report.get("pr_number", 0))
    expected_reference = f"https://github.com/{source_repository}/pull/{source_pr_number}"
    expected = {
        "source_repository": source_repository,
        "source_commit_sha": source_commit_sha,
        "source_pr_number": source_pr_number,
        "approval_reference": expected_reference,
        "verifier_report_sha256": verifier_report_sha256,
    }
    for key, value in expected.items():
        if approval.get(key) != value:
            raise ValueError(f"approval {key} does not match verifier evidence")

    return {
        "provider": "github",
        "provider_identity_verified": True,
        "reviewer_id": reviewer_id,
        "approved_at": approved_at,
        "decision": "approve_proposal",
        "approval_reference": expected_reference,
        "limitations_acknowledged": True,
        "identity_authentication": "asserted_by_hosting_provider_not_reverified_locally",
    }


def _validate_verifier_report(report: Mapping[str, Any]) -> None:
    if _string(report.get("schema_version")) != formatter_candidate_verifier.SCHEMA_VERSION:
        raise ValueError("unsupported formatter verifier report schema")
    if _string(report.get("status")) != "passed":
        raise ValueError("formatter verifier report has not passed")
    if _string(report.get("candidate_family")) != "formatter_only":
        raise ValueError("only formatter_only may enter policy proposal eligibility")
    checks = _as_dict(report.get("checks"))
    required_checks = {
        "claimed_files_equal_actual_writes",
        "proof_inputs_unchanged",
        "rollback_exact_bytes",
        "all_six_scenarios_retained",
        "false_authority_count_zero",
    }
    if not required_checks.issubset(checks) or not all(
        _bool(checks.get(key)) for key in required_checks
    ):
        raise ValueError("formatter verifier checks are incomplete or failed")
    if _string(report.get("protected_verifier_status")) != "structurally_verified_candidate":
        raise ValueError("formatter evidence is not structurally verified")
    if not _bool(report.get("structural_verification_passed")):
        raise ValueError("formatter structural verification did not pass")
    record_count = int(report.get("trajectory_record_count", 0))
    if record_count < 1:
        raise ValueError("formatter proposal requires at least one reviewed trajectory")
    if int(report.get("trajectory_review_first_count", 0)) != record_count:
        raise ValueError("all formatter trajectories must remain review-first")
    if int(report.get("trajectory_auto_fix_allowed_count", -1)) != 0:
        raise ValueError("formatter trajectories record automatic fix authority")
    if int(report.get("repo_memory_known_safe_candidate_count", -1)) != 0:
        raise ValueError("RepoMemory must not authorize a known safe candidate")
    if _string(report.get("controlled_validation_status")) != "controlled_validation_passed":
        raise ValueError("controlled formatter validation has not passed")
    _assert_authority_denied(report, source="formatter verifier report")


def _validate_protected_verifier(payload: Mapping[str, Any]) -> None:
    decision = _as_dict(payload.get("decision"))
    if _string(decision.get("status")) != "structurally_verified_candidate":
        raise ValueError("ProtectedVerifier decision is not structurally verified")
    if not _bool(decision.get("structural_verification_passed")):
        raise ValueError("ProtectedVerifier structural verification failed")
    _assert_boundary_denied(decision, source="ProtectedVerifier decision")


def _validate_trajectory(path: Path) -> int:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        raise ValueError("formatter trajectory evidence is empty")
    for line in lines:
        record = json.loads(line)
        if not isinstance(record, dict):
            raise ValueError("formatter trajectory record must be an object")
        decision = _as_dict(record.get("decision"))
        if not _bool(decision.get("review_first")) or _bool(decision.get("auto_fix_allowed")):
            raise ValueError("formatter trajectory must remain review-first without auto-fix")
        if _string(record.get("final_result")) != "review_required":
            raise ValueError("formatter trajectory final_result must remain review_required")
        _assert_boundary_denied(
            _as_dict(record.get("authority_boundary")), source="formatter trajectory"
        )
    return len(lines)


def _validate_repo_memory(payload: Mapping[str, Any]) -> None:
    if int(payload.get("known_safe_candidate_count", -1)) != 0:
        raise ValueError("RepoMemory known safe candidate count must remain zero")
    _assert_boundary_denied(_as_dict(payload.get("decision_boundary")), source="RepoMemory")
    controlled = _as_dict(payload.get("controlled_candidate_validation"))
    if _bool(controlled.get("current_pr_decision_input")):
        raise ValueError("RepoMemory current-PR decision input must remain false")


def _validate_controlled_validation(payload: Mapping[str, Any]) -> None:
    if _string(payload.get("status")) != "passed":
        raise ValueError("controlled validation artifact has not passed")
    boundary = _as_dict(payload.get("boundary"))
    if _bool(boundary.get("contributes_to_current_pr_decision")):
        raise ValueError("controlled validation must not decide the current PR")
    _assert_boundary_denied(boundary, source="controlled validation")


def render_markdown(report: Mapping[str, Any]) -> str:
    approval = _as_dict(report.get("approval_binding"))
    return "\n".join(
        [
            "# Formatter policy proposal eligibility",
            "",
            f"- Status: `{_string(report.get('status'))}`",
            f"- Proposal status: `{_string(report.get('proposal_status'))}`",
            f"- Proposal eligible: `{str(_bool(report.get('proposal_eligible'))).lower()}`",
            f"- Branch execution allowed: `{str(_bool(report.get('branch_execution_allowed'))).lower()}`",
            f"- Reviewer: `{_string(approval.get('reviewer_id'))}`",
            f"- Approval reference: `{_string(approval.get('approval_reference'))}`",
            "",
            "This artifact permits a human-reviewed policy proposal only. It does not apply a patch, execute on a branch, alter SafetyGate, authorize merge or publication, dismiss security findings, or prove semantic equivalence.",
            "",
        ]
    )


def build_formatter_policy_proposal(
    *,
    verifier_dir: Path,
    approval_record_json: Path,
    out_dir: Path = DEFAULT_OUT_DIR,
    contract_json: Path = DEFAULT_CONTRACT,
) -> JsonObject:
    root = verifier_dir.resolve()
    output = out_dir.resolve()
    if output == root or root in output.parents:
        raise ValueError("policy proposal output must be outside verifier evidence directory")

    contract = _read_json(contract_json)
    _validate_contract(contract)
    approval_path = approval_record_json.resolve()
    if approval_path.is_symlink() or not approval_path.is_file():
        raise ValueError("approval record must be a normal JSON file")

    artifacts = {filename: _artifact(root, filename) for filename in REQUIRED_VERIFIER_FILES}
    before_snapshot = _snapshot(root)
    verifier_report_path = artifacts[formatter_candidate_verifier.REPORT_JSON]
    verifier_report = _read_json(verifier_report_path)
    _validate_verifier_report(verifier_report)
    verifier_report_sha256 = _sha256(verifier_report_path)
    approval_binding = _validate_approval(
        _read_json(approval_path),
        verifier_report=verifier_report,
        verifier_report_sha256=verifier_report_sha256,
    )

    _validate_protected_verifier(
        _read_json(artifacts[formatter_candidate_verifier.PROTECTED_VERIFIER_JSON])
    )
    trajectory_count = _validate_trajectory(
        artifacts[formatter_candidate_verifier.TRAJECTORY_JSONL]
    )
    _validate_repo_memory(_read_json(artifacts[formatter_candidate_verifier.REPO_MEMORY_JSON]))
    _validate_controlled_validation(
        _read_json(artifacts[formatter_candidate_verifier.CONTROLLED_VALIDATION_JSON])
    )

    after_snapshot = _snapshot(root)
    if before_snapshot != after_snapshot:
        raise ValueError(
            "formatter verifier evidence was mutated during policy proposal evaluation"
        )

    report: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "status": "passed",
        "proposal_status": "eligible_for_human_policy_proposal",
        "candidate_family": "formatter_only",
        "promotion_mode": "proposal_only",
        "proposal_eligible": True,
        "execution_eligible": False,
        "branch_execution_allowed": False,
        "safe_fix_allowed": False,
        "review_required": True,
        "safety_gate_policy_changed": False,
        "source_repository": verifier_report.get("source_repository"),
        "source_commit_sha": verifier_report.get("source_commit_sha"),
        "source_pr_number": verifier_report.get("pr_number"),
        "verifier_report_sha256": verifier_report_sha256,
        "approval_record_sha256": _sha256(approval_path),
        "approval_binding": approval_binding,
        "checks": {
            "candidate_is_formatter_only": True,
            "verifier_report_passed": True,
            "all_verifier_checks_passed": True,
            "protected_verifier_structural_only": True,
            "all_trajectories_review_first": True,
            "repo_memory_authority_zero": True,
            "provider_identity_verified": True,
            "approval_bound_to_exact_evidence": True,
            "verifier_inputs_unchanged": True,
        },
        "trajectory_record_count": trajectory_count,
        "limitations": list(contract.get("limitations", [])),
        **remediation_research_contract.authority_boundary(),
    }
    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / REPORT_JSON, report)
    (output / REPORT_MD).write_text(render_markdown(report), encoding="utf-8")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.formatter_policy_proposal")
    parser.add_argument("--verifier-dir", type=Path, required=True)
    parser.add_argument("--approval-record", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--contract-json", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = build_formatter_policy_proposal(
            verifier_dir=args.verifier_dir,
            approval_record_json=args.approval_record,
            out_dir=args.out_dir,
            contract_json=args.contract_json,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"status: {report['status']}")
        print(f"proposal_status: {report['proposal_status']}")
        print(f"proposal_eligible: {str(report['proposal_eligible']).lower()}")
        print(f"branch_execution_allowed: {str(report['branch_execution_allowed']).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
