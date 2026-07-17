from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sdetkit.adoption_surface import discover_adoption_surface
from sdetkit.doctor_report import build_doctor_report_contract, render_doctor_report_markdown
from sdetkit.failure_vector import BUNDLE_SCHEMA_VERSION
from sdetkit.failure_vector import SCHEMA_VERSION as FAILURE_VECTOR_SCHEMA_VERSION
from sdetkit.failure_vector_cpp import CppFailureVectorResult, extract_cpp_failure_vector
from sdetkit.protected_verifier import render_markdown as render_protected_verifier_markdown
from sdetkit.protected_verifier import verify_patch
from sdetkit.repo_memory import build_repo_memory_profile
from sdetkit.safety_gate import (
    SafetyGateDecision,
    evaluate_failure_vector,
    render_safety_gate_decision_report,
)

SCHEMA_VERSION = "sdetkit.ecosystem_operator_proof.v1"
TRAJECTORY_SCHEMA_VERSION = "sdetkit.trajectory_pattern_insights.v1"
DEFAULT_OUT_DIR = Path("build") / "cpp-operator-proof"
PROOF_JSON = "cpp-operator-proof.json"
PROOF_MD = "cpp-operator-proof.md"
DOCTOR_JSON = "doctor-report.json"
DOCTOR_MD = "doctor-report.md"
SAFETY_GATE_JSON = "safety-gate-decision.json"
SAFETY_GATE_MD = "safety-gate-decision.md"
PROTECTED_VERIFIER_JSON = "protected-verifier-decision.json"
PROTECTED_VERIFIER_MD = "protected-verifier-decision.md"
REPO_MEMORY_JSON = "repo-memory-profile.json"

JsonObject = dict[str, Any]

_AUTHORITY_BOUNDARY: JsonObject = {
    "target_code_execution": False,
    "automation_allowed": False,
    "patch_application_allowed": False,
    "security_dismissal_allowed": False,
    "publication_authorized": False,
    "merge_authorized": False,
    "semantic_equivalence_proven": False,
}

_ARTIFACT_FILENAMES = (
    PROOF_JSON,
    PROOF_MD,
    DOCTOR_JSON,
    DOCTOR_MD,
    SAFETY_GATE_JSON,
    SAFETY_GATE_MD,
    PROTECTED_VERIFIER_JSON,
    PROTECTED_VERIFIER_MD,
    REPO_MEMORY_JSON,
)

_IGNORED_DIGEST_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "build",
    "cmake-build-debug",
    "cmake-build-release",
    "node_modules",
    "out",
    "target",
    "vendor",
}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_excluded(path: Path, *, root: Path, output_dir: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False

    try:
        output_relative = output_dir.relative_to(root)
    except ValueError:
        output_relative = None

    if output_relative is not None and (
        relative == output_relative or output_relative in relative.parents
    ):
        return True
    return any(part.lower() in _IGNORED_DIGEST_PARTS for part in relative.parts)


def _repository_digest(root: Path, *, output_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if _is_excluded(path, root=root, output_dir=output_dir):
            continue
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _failure_bundle(
    result: CppFailureVectorResult,
    *,
    environment: str,
    safety_gate: SafetyGateDecision,
) -> JsonObject:
    vector_payload = result.to_dict()
    failure_class = result.vector.failure_class
    risk = result.vector.risk
    return {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "vector_schema_version": FAILURE_VECTOR_SCHEMA_VERSION,
        "status": "review_required",
        "environment": environment,
        "failure_vector_count": 1,
        "summary": {
            "by_failure_class": {failure_class: 1},
            "by_risk": {risk: 1},
            "safe_fix_candidate_count": int(result.vector.safe_fix_candidate),
            "review_first_count": int(safety_gate.review_first),
        },
        "failure_vectors": [vector_payload],
        "safety_gate": safety_gate.to_dict(),
        "decision_boundary": {
            "automation_allowed": False,
            "patch_application_allowed": False,
            "security_dismissal_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }


def _trajectory_pattern_insights(
    result: CppFailureVectorResult,
    safety_gate: SafetyGateDecision,
) -> JsonObject:
    denied = {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }
    extended_denied = {
        **denied,
        "automatic_security_fix_allowed": False,
        "automatic_dismissal_allowed": False,
    }
    vector_denied = {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "security_dismissal_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_claim": False,
    }
    return {
        "schema_version": TRAJECTORY_SCHEMA_VERSION,
        "record_count": 1,
        "recurring_review_first_surfaces": [
            {"value": f"cpp_{safety_gate.failure_kind}", "count": 1}
        ],
        "recurring_safe_fix_patterns": [],
        "safety_gate_evidence": {
            "collection_status": "collected",
            "status": "safety_gate_evidence_observed",
            "source": "cpp_operator_proof.safety_gate",
            "record_count": 1,
            "review_first_count": int(safety_gate.review_first),
            "safe_fix_allowed_count": int(safety_gate.safe_fix_allowed),
            "reporting_only_count": int(safety_gate.reporting_only),
            "report_paths": [SAFETY_GATE_JSON, SAFETY_GATE_MD],
            "decision_boundary": denied,
        },
        "authority_boundary_evidence": {
            "collection_status": "collected",
            "status": "authority_boundary_evidence_observed",
            "source": "cpp_operator_proof",
            "record_count": 1,
            "review_first_count": int(safety_gate.review_first),
            "auto_fix_allowed_count": int(safety_gate.safe_fix_allowed),
            "reporting_only_count": 1,
            "sources": ["adoption_surface", "failure_vector_cpp", "safety_gate"],
            "decision_boundary": extended_denied,
        },
        "failure_vector_contract_evidence": {
            "collection_status": "collected",
            "status": "failure_vector_contract_evidence_observed",
            "source": "cpp_operator_proof.failure_vector",
            "record_count": 1,
            "security_relevance_count": int(safety_gate.security_relevance),
            "authority_boundary_preserved_count": 1,
            "failure_kinds": [{"value": result.vector.failure_class, "count": 1}],
            "affected_surfaces": [{"value": safety_gate.affected_surface, "count": 1}],
            "decision_boundary": vector_denied,
        },
    }


def _unproven_benchmark_report() -> JsonObject:
    return {
        "schema_version": "sdetkit.replayable_benchmark_report.v1",
        "status": "not_collected",
        "required_contract": {
            "all_required_present": False,
            "all_required_passed": False,
        },
        "safety_boundary": {
            "preserved": True,
            "automation_allowed_count": 0,
            "merge_authorized_count": 0,
            "semantic_equivalence_claimed_count": 0,
        },
        "scenarios": [],
    }


def _doctor_input() -> JsonObject:
    return {
        "ok": True,
        "score": 100,
        "quality": {"selected_checks": 1, "passed_checks": 1},
        "next_actions": [],
    }


def _named(items: object) -> dict[str, JsonObject]:
    if not isinstance(items, list):
        return {}
    return {
        str(item["name"]): item
        for item in items
        if isinstance(item, dict) and str(item.get("name", ""))
    }


def _proof_commands(adoption: Mapping[str, Any]) -> list[JsonObject]:
    commands = adoption.get("recommended_proof_commands")
    if not isinstance(commands, list):
        return []
    return [
        dict(item) for item in commands if isinstance(item, dict) and item.get("surface") == "cpp"
    ]


def _verify_payload(payload: Mapping[str, Any]) -> JsonObject:
    adoption = payload.get("adoption_surface")
    adoption_payload = adoption if isinstance(adoption, dict) else {}
    languages = _named(adoption_payload.get("detected_languages"))

    vector = payload.get("failure_vector")
    vector_payload = vector if isinstance(vector, dict) else {}
    adapter = vector_payload.get("adapter")
    adapter_payload = adapter if isinstance(adapter, dict) else {}

    safety = payload.get("safety_gate")
    safety_payload = safety if isinstance(safety, dict) else {}

    verifier = payload.get("protected_verifier")
    verifier_payload = verifier if isinstance(verifier, dict) else {}
    verifier_decision = verifier_payload.get("decision")
    verifier_decision_payload = verifier_decision if isinstance(verifier_decision, dict) else {}

    doctor = payload.get("doctor_report")
    doctor_payload = doctor if isinstance(doctor, dict) else {}

    repo_memory = payload.get("repo_memory_profile")
    repo_memory_payload = repo_memory if isinstance(repo_memory, dict) else {}
    command_profile = repo_memory_payload.get("command_profile")
    command_profile_payload = command_profile if isinstance(command_profile, dict) else {}

    boundary = payload.get("authority_boundary")
    boundary_payload = boundary if isinstance(boundary, dict) else {}
    false_authority = all(value is False for value in boundary_payload.values())

    checks = {
        "cpp_repository_detected": "cpp" in languages,
        "advisory_commands_present": bool(_proof_commands(adoption_payload)),
        "failure_vector_is_cpp": adapter_payload.get("ecosystem") == "cpp",
        "saved_evidence_only": adapter_payload.get("target_code_execution") is False,
        "safety_gate_review_first": safety_payload.get("review_first") is True,
        "protected_verifier_review_first": verifier_decision_payload.get("review_first") is True,
        "doctor_review_required": doctor_payload.get("status") == "review_required",
        "repo_memory_read_only": (
            command_profile_payload.get("commands_executed_by_repo_memory") is False
        ),
        "repository_unchanged": payload.get("repository_unchanged") is True,
        "authority_boundary_preserved": false_authority,
    }
    return {"ok": all(checks.values()), "checks": checks}


def _cli_success_manifest() -> JsonObject:
    return {
        "schema_version": SCHEMA_VERSION,
        "ecosystem": "cpp",
        "status": "review_required",
        "verification_ok": True,
        "artifacts": list(_ARTIFACT_FILENAMES),
        "authority_boundary": dict(_AUTHORITY_BOUNDARY),
    }


def render_cpp_operator_proof_markdown(payload: Mapping[str, Any]) -> str:
    adoption = payload.get("adoption_surface")
    adoption_payload = adoption if isinstance(adoption, dict) else {}

    vector = payload.get("failure_vector")
    vector_payload = vector if isinstance(vector, dict) else {}
    adapter = vector_payload.get("adapter")
    adapter_payload = adapter if isinstance(adapter, dict) else {}

    safety = payload.get("safety_gate")
    safety_payload = safety if isinstance(safety, dict) else {}

    verifier = payload.get("protected_verifier")
    verifier_payload = verifier if isinstance(verifier, dict) else {}
    verifier_decision = verifier_payload.get("decision")
    verifier_decision_payload = verifier_decision if isinstance(verifier_decision, dict) else {}

    doctor = payload.get("doctor_report")
    doctor_payload = doctor if isinstance(doctor, dict) else {}
    evidence = doctor_payload.get("failure_vector_evidence")
    evidence_payload = evidence if isinstance(evidence, dict) else {}
    top_failure = evidence_payload.get("top_failure")
    top_failure_payload = top_failure if isinstance(top_failure, dict) else {}

    repo_memory = payload.get("repo_memory_profile")
    repo_memory_payload = repo_memory if isinstance(repo_memory, dict) else {}

    verification = payload.get("verification")
    verification_payload = verification if isinstance(verification, dict) else {}
    checks = verification_payload.get("checks")
    checks_payload = checks if isinstance(checks, dict) else {}

    lines = [
        "# C++ adoption-to-diagnosis operator proof",
        "",
        "This artifact composes shared SDETKit contracts from repository-owned and saved evidence.",
        "It does not execute target commands or authorize remediation.",
        "",
        "## What is detected",
        "",
    ]
    for command in _proof_commands(adoption_payload):
        source = command.get("source")
        source_payload = source if isinstance(source, dict) else {}
        lines.append(
            "- `{command}` from `{file}` in `{working_directory}` "
            "(manual, auto_run_allowed=false)".format(
                command=command.get("command", ""),
                file=source_payload.get("file", ""),
                working_directory=source_payload.get("working_directory", "."),
            )
        )

    lines.extend(
        [
            "",
            "## What is inferred",
            "",
            f"- Failure adapter: `{adapter_payload.get('tool', 'unknown')}`",
            f"- Confidence: `{adapter_payload.get('confidence', 'unknown')}`",
            f"- Failure class: `{vector_payload.get('failure_class', 'unknown')}`",
            f"- Local reproduction command: `{vector_payload.get('local_repro_command') or 'not proven'}`",
            "",
            "## What is proven",
            "",
            f"- SafetyGate review first: `{str(bool(safety_payload.get('review_first'))).lower()}`",
            f"- ProtectedVerifier status: `{verifier_decision_payload.get('status', 'unknown')}`",
            f"- Doctor status: `{doctor_payload.get('status', 'unknown')}`",
            f"- Top failure: `{top_failure_payload.get('check', 'unknown')}: "
            f"{top_failure_payload.get('failure_type', 'unknown')}`",
            f"- RepoMemory profile: `{repo_memory_payload.get('profile_status', 'unknown')}`",
            f"- Repository unchanged: `{str(bool(payload.get('repository_unchanged'))).lower()}`",
            "",
            "## Unsupported and manual",
            "",
        ]
    )
    for item in payload.get("unsupported", []):
        lines.append(f"- {item}")
    for item in payload.get("manual_actions", []):
        lines.append(f"- {item}")

    lines.extend(["", "## Authority boundary", "", "```text"])
    for key, value in _AUTHORITY_BOUNDARY.items():
        lines.append(f"{key}={str(value).lower()}")
    lines.extend(
        [
            "```",
            "",
            "## Verification",
            "",
            f"- Overall: `{str(bool(verification_payload.get('ok'))).lower()}`",
        ]
    )
    for key in sorted(checks_payload):
        lines.append(f"- {key}: `{str(bool(checks_payload[key])).lower()}`")
    return "\n".join(lines).rstrip() + "\n"


def build_cpp_operator_proof(
    *,
    repo: Path,
    failure_log: Path,
    out_dir: Path = DEFAULT_OUT_DIR,
    check: str = "ctest",
    environment: str = "github_actions",
) -> JsonObject:
    """Build a deterministic C++ operator proof from read-only repository and log evidence."""

    repo = repo.resolve()
    failure_log = failure_log.resolve()
    out_dir = out_dir.resolve()
    if not repo.is_dir():
        raise ValueError(f"C++ proof repository does not exist: {repo}")
    if not failure_log.is_file():
        raise ValueError(f"C++ saved failure log does not exist: {failure_log}")

    before_digest = _repository_digest(repo, output_dir=out_dir)
    log_text = failure_log.read_text(encoding="utf-8")
    adoption = discover_adoption_surface(repo)
    result = extract_cpp_failure_vector(
        log_text,
        check=check,
        log_url=failure_log.name,
        environment=environment,
    )
    safety_gate = evaluate_failure_vector(result.vector)
    failure_bundle = _failure_bundle(result, environment=environment, safety_gate=safety_gate)
    trajectory = _trajectory_pattern_insights(result, safety_gate)
    repo_memory = build_repo_memory_profile(
        pattern_insights=trajectory,
        benchmark_report=_unproven_benchmark_report(),
    )
    protected_verifier = verify_patch(
        patch_score={},
        failure_bundle=failure_bundle,
        repo_memory_profile=repo_memory,
    )
    doctor_report = build_doctor_report_contract(
        _doctor_input(),
        failure_vector_bundle=failure_bundle,
    )
    after_digest = _repository_digest(repo, output_dir=out_dir)

    payload: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "ecosystem": "cpp",
        "status": "review_required",
        "source_evidence": {
            "failure_log": failure_log.name,
            "failure_log_sha256": _sha256_text(log_text),
            "repository_digest_before": before_digest,
            "repository_digest_after": after_digest,
        },
        "repository_unchanged": before_digest == after_digest,
        "adoption_surface": adoption,
        "failure_vector": result.to_dict(),
        "failure_bundle": failure_bundle,
        "safety_gate": safety_gate.to_dict(),
        "protected_verifier": protected_verifier,
        "doctor_report": doctor_report,
        "trajectory_evidence": trajectory,
        "repo_memory_profile": repo_memory,
        "unsupported": [
            "target CMake, Meson, compiler, analyzer, or test execution",
            "dynamic workflow, matrix, template, and shell-command resolution",
            "automatic patches, dependency changes, security dismissal, publication, or merge",
            "semantic equivalence or runtime correctness claims",
        ],
        "manual_actions": [
            "Review the repository-owned commands and saved failure evidence.",
            "Decide whether the exact C++ proof command is safe to run in the target environment.",
            "Inspect the affected source or test file and approve any proposed change separately.",
            "Rerun the relevant build or test proof after human-approved remediation.",
        ],
        "authority_boundary": dict(_AUTHORITY_BOUNDARY),
    }
    payload["verification"] = _verify_payload(payload)
    if not payload["repository_unchanged"]:
        raise RuntimeError("C++ operator proof detected a target repository mutation")
    if not payload["verification"]["ok"]:
        raise RuntimeError("C++ operator proof failed its shared-contract verification")

    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(out_dir / PROOF_JSON, payload)
    _write_text(out_dir / PROOF_MD, render_cpp_operator_proof_markdown(payload))
    _write_json(out_dir / DOCTOR_JSON, doctor_report)
    _write_text(out_dir / DOCTOR_MD, render_doctor_report_markdown(doctor_report))
    _write_json(out_dir / SAFETY_GATE_JSON, safety_gate.to_dict())
    _write_text(out_dir / SAFETY_GATE_MD, render_safety_gate_decision_report(safety_gate))
    _write_json(out_dir / PROTECTED_VERIFIER_JSON, protected_verifier)
    _write_text(
        out_dir / PROTECTED_VERIFIER_MD,
        render_protected_verifier_markdown(protected_verifier),
    )
    _write_json(out_dir / REPO_MEMORY_JSON, repo_memory)
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a read-only C++ adoption-to-diagnosis operator proof.",
    )
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--failure-log", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--check", default="ctest")
    parser.add_argument("--environment", default="github_actions")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload = build_cpp_operator_proof(
        repo=args.repo,
        failure_log=args.failure_log,
        out_dir=args.out_dir,
        check=args.check,
        environment=args.environment,
    )
    if args.format == "markdown":
        print(render_cpp_operator_proof_markdown(payload), end="")
    else:
        print(json.dumps(_cli_success_manifest(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
