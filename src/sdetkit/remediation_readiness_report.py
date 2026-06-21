from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from sdetkit import adaptive_remediation_policy
from sdetkit.protected_verifier import verify_candidate

SCHEMA_VERSION = "sdetkit.remediation_readiness_report.v2"
DEFAULT_OUT = "build/sdetkit/remediation-readiness-report.json"
DEFAULT_POLICY_PATH = "config/adaptive_remediation_policy.default.json"
SAFETYGATE_POLICY_PATH = "docs/contracts/safety-gate-policy-matrix.v1.json"

INPUT_DIGEST_ALGORITHM = "sha256"
GENERATOR_SOURCE_LABEL = "src/sdetkit/remediation_readiness_report.py"
CONTRACT_FILES = (
    "src/sdetkit/safety_gate.py",
    "src/sdetkit/failure_vector.py",
    SAFETYGATE_POLICY_PATH,
    "docs/safety-gate-policy-matrix.md",
    "src/sdetkit/adaptive_remediation_policy.py",
    "src/sdetkit/adaptive_patch_plan.py",
    "src/sdetkit/adaptive_fix_audit.py",
    "src/sdetkit/protected_verifier.py",
    "src/sdetkit/patch_scorer.py",
    DEFAULT_POLICY_PATH,
)


def _update_input_digest(hasher: Any, label: str, content: bytes) -> None:
    label_bytes = label.encode("utf-8")
    hasher.update(len(label_bytes).to_bytes(8, "big"))
    hasher.update(label_bytes)
    hasher.update(len(content).to_bytes(8, "big"))
    hasher.update(content)


def _display_input_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def remediation_readiness_input_provenance(
    root: str | Path = ".",
    *,
    policy_path: str | Path | None = None,
    generator_path: str | Path | None = None,
) -> dict[str, Any]:
    repo_root = Path(root).resolve()
    generator = (
        Path(generator_path).resolve() if generator_path is not None else Path(__file__).resolve()
    )
    policy_file = Path(policy_path) if policy_path is not None else Path(DEFAULT_POLICY_PATH)
    if not policy_file.is_absolute():
        policy_file = repo_root / policy_file

    candidate_paths: list[tuple[str, Path]] = [(GENERATOR_SOURCE_LABEL, generator)]
    for configured_path in CONTRACT_FILES:
        path = repo_root / configured_path
        candidate_paths.append((configured_path, path))

    policy_label = _display_input_path(repo_root, policy_file)
    if all(label != policy_label for label, _path in candidate_paths):
        candidate_paths.append((policy_label, policy_file))

    unique_paths: dict[str, Path] = {}
    for label, path in candidate_paths:
        unique_paths.setdefault(label, path)

    inputs: list[tuple[str, bytes]] = [
        ("schema_version", SCHEMA_VERSION.encode("utf-8")),
    ]
    missing_inputs: list[str] = []
    for label, path in sorted(unique_paths.items()):
        if path.is_file():
            content = path.read_bytes()
        else:
            content = b"<missing>"
            missing_inputs.append(label)
        inputs.append((label, content))

    hasher = hashlib.sha256()
    for label, content in sorted(inputs, key=lambda item: item[0]):
        _update_input_digest(hasher, label, content)

    return {
        "digest_algorithm": INPUT_DIGEST_ALGORITHM,
        "input_digest": hasher.hexdigest(),
        "input_count": len(inputs),
        "input_file_count": len(unique_paths),
        "missing_input_count": len(missing_inputs),
        "missing_inputs": missing_inputs,
        "input_paths": sorted(unique_paths),
        "policy_path": policy_label,
        "generator_schema_version": SCHEMA_VERSION,
        "generator_source": GENERATOR_SOURCE_LABEL,
    }


def validate_remediation_readiness_report_freshness(
    root: str | Path,
    payload: dict[str, Any],
    *,
    policy_path: str | Path | None = None,
    generator_path: str | Path | None = None,
) -> dict[str, Any]:
    current = remediation_readiness_input_provenance(
        root,
        policy_path=policy_path,
        generator_path=generator_path,
    )
    reasons: list[str] = []
    recorded = payload.get("input_provenance")
    if not isinstance(recorded, dict):
        recorded = {}
        reasons.append("missing_input_provenance")

    for field in (
        "digest_algorithm",
        "input_digest",
        "input_count",
        "input_file_count",
        "missing_input_count",
        "missing_inputs",
        "input_paths",
        "policy_path",
        "generator_schema_version",
        "generator_source",
    ):
        if recorded.get(field) != current.get(field):
            reasons.append(f"{field}_mismatch")

    schema_valid = payload.get("schema_version") == SCHEMA_VERSION
    if not schema_valid:
        reasons.append("schema_version_mismatch")

    authority_valid = True
    for field in AUTHORITY_FIELDS:
        if payload.get(field) is not False:
            authority_valid = False
            reasons.append(f"{field}_mismatch")

    boundary = payload.get("authority_boundary")
    if not isinstance(boundary, dict):
        authority_valid = False
        reasons.append("missing_authority_boundary")
    else:
        for field in AUTHORITY_FIELDS:
            if boundary.get(field) is not False:
                authority_valid = False
                reasons.append(f"authority_boundary_{field}_mismatch")

    rules = payload.get("rules")
    expected_rules = {
        "read_only": True,
        "dry_run_only": True,
        "target_repo_mutation": False,
        "review_first": True,
        "safe_to_patch": False,
    }
    if not isinstance(rules, dict):
        authority_valid = False
        reasons.append("missing_rules")
    else:
        for field, expected in expected_rules.items():
            if rules.get(field) is not expected:
                authority_valid = False
                reasons.append(f"rules_{field}_mismatch")

    reasons = sorted(set(reasons))
    fresh = not reasons
    return {
        "status": "fresh" if fresh else "stale",
        "fresh": fresh,
        "schema_valid": schema_valid,
        "authority_valid": authority_valid,
        "reasons": reasons,
        "recorded_input_digest": recorded.get("input_digest", ""),
        "current_input_digest": current["input_digest"],
        "reporting_only": True,
        "repo_mutation": False,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def check_remediation_readiness_report_freshness(
    *,
    root: str | Path,
    report_path: str | Path,
    policy_path: str | Path | None = None,
    generator_path: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(report_path)
    if not path.is_file():
        result = validate_remediation_readiness_report_freshness(
            root,
            {},
            policy_path=policy_path,
            generator_path=generator_path,
        )
        result["reasons"] = sorted(set([*result["reasons"], "report_missing"]))
        result["status"] = "stale"
        result["fresh"] = False
        return result

    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        result = validate_remediation_readiness_report_freshness(
            root,
            {},
            policy_path=policy_path,
            generator_path=generator_path,
        )
        result["reasons"] = sorted(set([*result["reasons"], "report_invalid_json"]))
        result["status"] = "stale"
        result["fresh"] = False
        return result

    if not isinstance(loaded, dict):
        result = validate_remediation_readiness_report_freshness(
            root,
            {},
            policy_path=policy_path,
            generator_path=generator_path,
        )
        result["reasons"] = sorted(set([*result["reasons"], "report_not_object"]))
        result["status"] = "stale"
        result["fresh"] = False
        return result

    return validate_remediation_readiness_report_freshness(
        root,
        loaded,
        policy_path=policy_path,
        generator_path=generator_path,
    )


def render_remediation_readiness_freshness_text(payload: dict[str, Any]) -> str:
    reasons = payload.get("reasons", [])
    reason_text = ",".join(str(reason) for reason in reasons) if reasons else "none"
    return "\n".join(
        [
            f"freshness_status={payload.get('status', 'stale')}",
            f"fresh={str(bool(payload.get('fresh', False))).lower()}",
            f"schema_valid={str(bool(payload.get('schema_valid', False))).lower()}",
            f"authority_valid={str(bool(payload.get('authority_valid', False))).lower()}",
            f"freshness_reasons={reason_text}",
            f"recorded_input_digest={payload.get('recorded_input_digest', '')}",
            f"current_input_digest={payload.get('current_input_digest', '')}",
            "reporting_only=true",
            "repo_mutation=false",
            "automation_allowed=false",
            "patch_application_allowed=false",
            "merge_authorized=false",
            "semantic_equivalence_proven=false",
        ]
    )


AUTHORITY_FIELDS = (
    "automation_allowed",
    "patch_application_allowed",
    "merge_authorized",
    "semantic_equivalence_proven",
)


def _authority_boundary() -> dict[str, bool]:
    return {field: False for field in AUTHORITY_FIELDS}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_text(value: Any, limit: int = 240) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _load_policy(path: Path) -> dict[str, Any]:
    if not path.exists():
        return adaptive_remediation_policy.default_policy()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"expected JSON object in {path}"
        raise ValueError(msg)
    return payload


def _review_only_patch_plan() -> dict[str, Any]:
    return {
        "schema_version": "sdetkit.adaptive.patch_plan.v1",
        "status": "review_required",
        "source_status": "needs_fix",
        "source_code": "UNKNOWN_REVIEW_REQUIRED",
        "safe_to_auto_fix": False,
        "dry_run_only": True,
        "requires_human_review": True,
        "affected_files": ["pyproject.toml"],
        "proof_commands": ["python -m pytest -q tests/test_example.py -o addopts="],
        "guardrails": {
            "automation_mutation_allowed": False,
            "deterministic_reproduction_required": True,
            "post_fix_proof_required": True,
        },
    }


def _safe_fix_plan() -> dict[str, Any]:
    return {
        "schema_version": "sdetkit.adaptive_safe_fix.v1",
        "source_status": "needs_fix",
        "source_code": "PRE_COMMIT_FORMAT_DRIFT",
        "safe_to_auto_fix": True,
        "fix_type": "format_only",
        "requires_human_review": False,
        "affected_files": ["src/sdetkit/example.py"],
        "proof_commands": ["python -m pre_commit run -a"],
    }


def _patch_score_candidate() -> dict[str, Any]:
    return {
        "patch_id": "readiness-format-patch",
        "diagnosis_id": "readiness-formatting",
        "score": 100,
        "changed_files": ["src/sdetkit/example.py"],
        "allowed_files": ["src/sdetkit/example.py"],
        "proof_requirements": ["python -m pre_commit run -a"],
        "decision": {
            "status": "candidate_for_protected_verification",
            "candidate_for_protected_verification": True,
            "automation_allowed": False,
            "patch_application_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }


def _verification_evidence() -> dict[str, Any]:
    return {
        "changed_files": ["src/sdetkit/example.py"],
        "proof_results": [
            {
                "command": "python -m pre_commit run -a",
                "status": "passed",
                "exit_code": 0,
            }
        ],
        "safety_gate_evidence": {
            "collection_status": "collected",
            "status": "review_first_boundary_preserved",
            "record_count": 1,
            "review_first_count": 1,
            "safe_fix_allowed_count": 0,
            "reporting_only_count": 1,
            "report_paths": ["build/sdetkit/remediation-readiness-report.json"],
            "decision_boundary": _authority_boundary(),
        },
    }


def _safety_gate_policy_summary(root: Path) -> dict[str, Any]:
    policy_path = root / SAFETYGATE_POLICY_PATH
    payload: dict[str, Any] = {}
    if policy_path.exists():
        loaded = json.loads(policy_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            payload = loaded

    requirements = _as_dict(payload.get("safe_fix_allowed_only_when"))
    local_repro_requirement = _safe_text(requirements.get("local_repro_command"), 80)

    return {
        "path": SAFETYGATE_POLICY_PATH,
        "present": policy_path.exists(),
        "schema_version": _safe_text(payload.get("schema_version"), 120),
        "local_repro_command": local_repro_requirement,
        "requires_local_repro_command": local_repro_requirement == "non_empty",
    }


def _contract_status(path: Path, *, display_path: str | None = None) -> dict[str, Any]:
    return {
        "path": display_path or path.as_posix(),
        "present": path.exists(),
    }


def _policy_summary(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": _safe_text(policy.get("schema_version"), 120),
        "name": _safe_text(policy.get("name"), 120),
        "allowed_safe_fix_types": [
            _safe_text(item, 80) for item in _as_list(policy.get("allowed_safe_fix_types"))
        ],
        "allow_review_required_auto_fix": bool(policy.get("allow_review_required_auto_fix")),
        "max_changed_files": int(policy.get("max_changed_files", 0) or 0),
        "required_proof_outcomes": [
            _safe_text(item, 80) for item in _as_list(policy.get("required_proof_outcomes"))
        ],
    }


def build_remediation_readiness_report(
    root: str | Path = ".",
    *,
    policy_path: str | Path | None = None,
) -> dict[str, Any]:
    repo_root = Path(root).resolve()
    policy_file = repo_root / (str(policy_path) if policy_path else DEFAULT_POLICY_PATH)
    policy = _load_policy(policy_file)
    safety_gate_policy = _safety_gate_policy_summary(repo_root)

    dry_run_plan = _review_only_patch_plan()
    safe_fix_plan = _safe_fix_plan()

    dry_run_policy_result = adaptive_remediation_policy.evaluate_policy(policy, dry_run_plan)
    safe_fix_policy_result = adaptive_remediation_policy.evaluate_policy(policy, safe_fix_plan)
    verifier_result = verify_candidate(
        patch_score=_patch_score_candidate(),
        verification_evidence=_verification_evidence(),
    )

    verifier_decision = _as_dict(verifier_result.get("decision"))
    structural_verification_passed = bool(verifier_decision.get("structural_verification_passed"))
    semantic_equivalence_proven = bool(verifier_decision.get("semantic_equivalence_proven"))

    readiness_checks = {
        "policy_accepts_review_only_dry_run_plan": bool(dry_run_policy_result.get("ok")),
        "policy_accepts_narrow_safe_fix_candidate": bool(safe_fix_policy_result.get("ok")),
        "protected_verifier_structural_check_passed": structural_verification_passed,
        "protected_verifier_keeps_semantic_equivalence_false": not semantic_equivalence_proven,
        "safety_gate_requires_local_repro_command": bool(
            safety_gate_policy.get("requires_local_repro_command")
        ),
        "dry_run_plan_mutation_blocked": all(
            not bool(step.get("mutation_allowed"))
            for step in _as_list(dry_run_plan.get("patch_steps"))
        )
        if "patch_steps" in dry_run_plan
        else bool(dry_run_plan.get("dry_run_only")),
    }

    blocking_gaps = [name for name, passed in readiness_checks.items() if not passed]

    contract_files = list(CONTRACT_FILES)

    return {
        "schema_version": SCHEMA_VERSION,
        "report_status": "review_required" if not blocking_gaps else "blocked",
        "root": repo_root.as_posix(),
        "policy_path": policy_file.relative_to(repo_root).as_posix()
        if policy_file.is_relative_to(repo_root)
        else policy_file.as_posix(),
        "policy": _policy_summary(policy),
        "input_provenance": remediation_readiness_input_provenance(
            repo_root,
            policy_path=policy_file,
        ),
        "safety_gate_policy": safety_gate_policy,
        "contract_files": [
            _contract_status(repo_root / path, display_path=path) for path in contract_files
        ],
        "readiness_checks": readiness_checks,
        "blocking_gap_count": len(blocking_gaps),
        "blocking_gaps": blocking_gaps,
        "dry_run_policy_result": {
            "ok": bool(dry_run_policy_result.get("ok")),
            "recommendation": _safe_text(dry_run_policy_result.get("recommendation"), 80),
            "plan_kind": _safe_text(dry_run_policy_result.get("plan_kind"), 80),
            "finding_count": int(dry_run_policy_result.get("finding_count", 0) or 0),
            "safe_to_auto_fix": bool(dry_run_policy_result.get("safe_to_auto_fix")),
        },
        "safe_fix_policy_result": {
            "ok": bool(safe_fix_policy_result.get("ok")),
            "recommendation": _safe_text(safe_fix_policy_result.get("recommendation"), 80),
            "plan_kind": _safe_text(safe_fix_policy_result.get("plan_kind"), 80),
            "finding_count": int(safe_fix_policy_result.get("finding_count", 0) or 0),
            "safe_to_auto_fix": bool(safe_fix_policy_result.get("safe_to_auto_fix")),
        },
        "protected_verifier_result": {
            "decision_status": _safe_text(verifier_decision.get("status"), 120),
            "structural_verification_passed": structural_verification_passed,
            "semantic_equivalence_proven": False,
            "automation_allowed": False,
            "merge_authorized": False,
            "finding_count": len(_as_list(verifier_result.get("findings"))),
        },
        "recommended_next_actions": [
            "Use this report as readiness evidence only.",
            "Use adaptive patch plans for review-first dry-run planning.",
            "Use PatchScorer and ProtectedVerifier before treating any candidate as structurally verified.",
            "Require focused proof results after any human-applied patch.",
            "Do not infer semantic equivalence or merge authorization from this report.",
        ],
        "rules": {
            "read_only": True,
            "dry_run_only": True,
            "verifier_backed": True,
            "patch_application_attempted": False,
            "target_repo_mutation": False,
            "review_first": True,
            "safe_to_patch": False,
        },
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "authority_boundary": _authority_boundary(),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    provenance = _as_dict(payload.get("input_provenance"))
    lines = [
        "# SDETKit remediation readiness report",
        "",
        f"- report_status: {payload['report_status']}",
        f"- policy_path: `{payload['policy_path']}`",
        f"- blocking_gap_count: {payload['blocking_gap_count']}",
        f"- input_digest: `{provenance.get('input_digest', '')}`",
        f"- digest_algorithm: `{provenance.get('digest_algorithm', '')}`",
        f"- input_count: {provenance.get('input_count', 0)}",
        f"- generator_source: `{provenance.get('generator_source', '')}`",
        "- verifier_backed: true",
        "- dry_run_only: true",
        "- review_first: true",
        "- safe_to_patch: false",
        "",
        "## Readiness checks",
        "",
    ]

    checks = _as_dict(payload.get("readiness_checks"))
    for name, passed in sorted(checks.items()):
        lines.append(f"- {name}: {str(bool(passed)).lower()}")

    safety_gate_policy = _as_dict(payload.get("safety_gate_policy"))
    lines.extend(
        [
            "",
            "## SafetyGate proof contract",
            "",
            f"- policy_path: `{safety_gate_policy.get('path', SAFETYGATE_POLICY_PATH)}`",
            f"- present: {str(bool(safety_gate_policy.get('present'))).lower()}",
            f"- local_repro_command: {safety_gate_policy.get('local_repro_command', '')}",
            "- requires_local_repro_command: "
            f"{str(bool(safety_gate_policy.get('requires_local_repro_command'))).lower()}",
        ]
    )

    lines.extend(["", "## Protected verifier", ""])
    verifier = _as_dict(payload.get("protected_verifier_result"))
    lines.extend(
        [
            f"- decision_status: {verifier.get('decision_status')}",
            f"- structural_verification_passed: {str(bool(verifier.get('structural_verification_passed'))).lower()}",
            "- semantic_equivalence_proven: false",
            "- automation_allowed: false",
            "- merge_authorized: false",
        ]
    )

    lines.extend(["", "## Blocking gaps", ""])
    gaps = _as_list(payload.get("blocking_gaps"))
    if gaps:
        for gap in gaps:
            lines.append(f"- {gap}")
    else:
        lines.append("- none")

    lines.extend(["", "## Recommended next actions", ""])
    for action in _as_list(payload.get("recommended_next_actions")):
        lines.append(f"- {action}")

    lines.extend(
        [
            "",
            "## Authority boundary",
            "",
            "- automation_allowed: false",
            "- patch_application_allowed: false",
            "- merge_authorized: false",
            "- semantic_equivalence_proven: false",
            "",
        ]
    )
    return "\n".join(lines)


def write_artifacts(
    *,
    root: str | Path = ".",
    policy_path: str | Path | None = None,
    out: str | Path = DEFAULT_OUT,
    markdown_out: str | Path | None = None,
) -> dict[str, Any]:
    payload = build_remediation_readiness_report(root=root, policy_path=policy_path)
    out_path = Path(out)
    markdown_path = Path(markdown_out) if markdown_out else out_path.with_suffix(".md")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)

    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(payload) + "\n", encoding="utf-8")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit remediation-readiness-report",
        description="Build a read-only verifier-backed dry-run remediation readiness report.",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--policy", default="")
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--markdown-out", default="")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    parser.add_argument(
        "--check-freshness",
        action="store_true",
        help="Check the existing report against current inputs, schema, and authority without rewriting it.",
    )
    ns = parser.parse_args(list(argv) if argv is not None else None)

    if ns.check_freshness:
        freshness = check_remediation_readiness_report_freshness(
            root=ns.root,
            policy_path=ns.policy or None,
            report_path=ns.out,
        )
        if ns.format == "json":
            sys.stdout.write(json.dumps(freshness, indent=2, sort_keys=True) + "\n")
        else:
            sys.stdout.write(render_remediation_readiness_freshness_text(freshness) + "\n")
        return 0 if freshness["fresh"] else 1

    payload = write_artifacts(
        root=ns.root,
        policy_path=ns.policy or None,
        out=ns.out,
        markdown_out=ns.markdown_out or None,
    )

    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_markdown(payload) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
