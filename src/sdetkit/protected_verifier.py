from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sdetkit.patch_scorer import PROTECTED_EXACT_PATHS, PROTECTED_PREFIXES

SCHEMA_VERSION = "sdetkit.protected_verifier.decision.v1"
DEFAULT_OUT_DIR = Path("build") / "protected-verifier"
PROTECTED_VERIFIER_JSON = "protected-verifier-decision.json"
PROTECTED_VERIFIER_MD = "protected-verifier-decision.md"
RESULT_JSON = "protected-verifier-result.json"
RESULT_MD = "protected-verifier-result.md"

JsonObject = dict[str, Any]

AUTHORITY_KEYS = (
    "automation_allowed",
    "patch_application_allowed",
    "merge_authorized",
    "semantic_equivalence_proven",
    "automatic_security_fix_allowed",
    "automatic_dismissal_allowed",
    "security_dismissal",
)

CANDIDATE_FOR_PROTECTED_VERIFICATION = "_".join(("candidate", "for", "protected", "verification"))
REVIEW_REQUIRED = "_".join(("review", "required"))
BLOCKED_REVIEW_FIRST = "_".join(("blocked", "review", "first"))
RESOLVE_BLOCKING_VERIFICATION_FLAGS = "_".join(("resolve", "blocking", "verification", "flags"))
HUMAN_REVIEW_REQUIRED_BEFORE_PATCH_APPLICATION = "_".join(
    ("human", "review", "required", "before", "patch", "application")
)
REPORTING_ONLY_NOTE = " ".join(
    (
        "This verifier is reporting-only.",
        "It does not apply patches, authorize merge,",
        "or claim semantic equivalence.",
    )
)


RESULT_REPORTING_ONLY_NOTE = " ".join(
    (
        "This result is reporting-only.",
        "It does not apply patches, authorize merge,",
        "or prove semantic equivalence.",
    )
)

PATCH_SCORE_NOT_CANDIDATE = "_".join(("PATCH", "SCORE", "NOT", "CANDIDATE"))
AUTOMATION_BOUNDARY_VIOLATION = "_".join(("AUTOMATION", "BOUNDARY", "VIOLATION"))
VERIFICATION_FILE_INVENTORY_MISSING = "_".join(("VERIFICATION", "FILE", "INVENTORY", "MISSING"))
CHANGED_FILE_INVENTORY_MISMATCH = "_".join(("CHANGED", "FILE", "INVENTORY", "MISMATCH"))
OUTSIDE_SCORED_SCOPE = "_".join(("OUTSIDE", "SCORED", "SCOPE"))
PROTECTED_PATH_CHANGED = "_".join(("PROTECTED", "PATH", "CHANGED"))
PROOF_REQUIREMENTS_MISSING = "_".join(("PROOF", "REQUIREMENTS", "MISSING"))
REQUIRED_PROOF_NOT_CAPTURED = "_".join(("REQUIRED", "PROOF", "NOT", "CAPTURED"))
REQUIRED_PROOF_FAILED = "_".join(("REQUIRED", "PROOF", "FAILED"))
SEMANTIC_EQUIVALENCE_NOT_PROVEN = "_".join(("SEMANTIC", "EQUIVALENCE", "NOT", "PROVEN"))
SAFETYGATE_EVIDENCE_AUTHORITY_VIOLATION = "_".join(
    ("SAFETYGATE", "EVIDENCE", "AUTHORITY", "VIOLATION")
)
FAILURE_VECTOR_CONTRACT_EVIDENCE_AUTHORITY_VIOLATION = "_".join(
    ("FAILURE", "VECTOR", "CONTRACT", "EVIDENCE", "AUTHORITY", "VIOLATION")
)
STRUCTURALLY_VERIFIED_CANDIDATE = "_".join(("structurally", "verified", "candidate"))


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


def _string_list(value: Any) -> list[str]:
    seen: set[str] = set()
    rendered: list[str] = []
    for item in _as_list(value):
        text = _string(item)
        if text and text not in seen:
            seen.add(text)
            rendered.append(text)
    return rendered


def _read_json(path: Path | None) -> JsonObject:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"expected JSON object in {path}"
        raise ValueError(msg)
    return payload


def _boundary_payloads(
    *,
    patch_score: Mapping[str, Any],
    failure_bundle: Mapping[str, Any],
    runtime_proof: Mapping[str, Any],
) -> list[tuple[str, JsonObject]]:
    patch_safety_gate = _as_dict(patch_score.get("safety_gate_evidence"))
    failure_safety_gate = _as_dict(failure_bundle.get("safety_gate"))
    runtime_safety_gate = _as_dict(runtime_proof.get("safety_gate"))

    return [
        ("patch_score", _as_dict(patch_score)),
        ("patch_score.decision", _as_dict(patch_score.get("decision"))),
        ("patch_score.decision_boundary", _as_dict(patch_score.get("decision_boundary"))),
        ("patch_score.authority_boundary", _as_dict(patch_score.get("authority_boundary"))),
        (
            "patch_score.safety_gate_evidence.decision_boundary",
            _as_dict(patch_safety_gate.get("decision_boundary")),
        ),
        ("failure_bundle.decision_boundary", _as_dict(failure_bundle.get("decision_boundary"))),
        ("failure_bundle.authority_boundary", _as_dict(failure_bundle.get("authority_boundary"))),
        ("failure_bundle.safety_gate", failure_safety_gate),
        (
            "failure_bundle.safety_gate.decision_boundary",
            _as_dict(failure_safety_gate.get("decision_boundary")),
        ),
        ("runtime_proof.decision_boundary", _as_dict(runtime_proof.get("decision_boundary"))),
        ("runtime_proof.authority_boundary", _as_dict(runtime_proof.get("authority_boundary"))),
        ("runtime_proof.safety_gate", runtime_safety_gate),
        (
            "runtime_proof.safety_gate.decision_boundary",
            _as_dict(runtime_safety_gate.get("decision_boundary")),
        ),
    ]


def _authority_expansion_flags(
    *,
    patch_score: Mapping[str, Any],
    failure_bundle: Mapping[str, Any],
    runtime_proof: Mapping[str, Any],
) -> list[JsonObject]:
    flags: list[JsonObject] = []
    for source, payload in _boundary_payloads(
        patch_score=patch_score,
        failure_bundle=failure_bundle,
        runtime_proof=runtime_proof,
    ):
        expanded = [key for key in AUTHORITY_KEYS if _bool(payload.get(key))]
        if not expanded:
            continue
        flags.append(
            {
                "code": "AUTHORITY_EXPANSION_ATTEMPT",
                "message": f"{source} attempted to expand ProtectedVerifier authority.",
                "blocking": True,
                "source": source,
                "fields": expanded,
            }
        )
    return flags


def _repo_memory_failure_vector_contract_evidence(
    repo_memory_profile: Mapping[str, Any],
) -> JsonObject:
    denied = {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "security_dismissal_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_claim": False,
    }
    payload = _as_dict(repo_memory_profile.get("failure_vector_contract_evidence"))
    if not payload:
        return {
            "collection_status": "not_collected",
            "status": "not_collected",
            "source": "repo_memory.failure_vector_contract_evidence",
            "record_count": 0,
            "security_relevance_count": 0,
            "authority_boundary_preserved_count": 0,
            "failure_kinds": [],
            "affected_surfaces": [],
            "expanded_authority_fields": [],
            "decision_boundary": denied,
        }

    boundary = _as_dict(payload.get("decision_boundary"))
    expanded = [key for key in denied if _bool(boundary.get(key))]
    return {
        "collection_status": _string(payload.get("collection_status")) or "collected",
        "status": _string(payload.get("status")) or "failure_vector_contract_evidence_observed",
        "source": _string(payload.get("source")) or "repo_memory.failure_vector_contract_evidence",
        "record_count": _int(payload.get("record_count")),
        "security_relevance_count": _int(payload.get("security_relevance_count")),
        "authority_boundary_preserved_count": _int(
            payload.get("authority_boundary_preserved_count")
        ),
        "failure_kinds": [
            {
                "value": _string(item.get("value")),
                "count": _int(item.get("count")),
            }
            for item in (_as_dict(row) for row in _as_list(payload.get("failure_kinds")))
            if _string(item.get("value"))
        ],
        "affected_surfaces": [
            {
                "value": _string(item.get("value")),
                "count": _int(item.get("count")),
            }
            for item in (_as_dict(row) for row in _as_list(payload.get("affected_surfaces")))
            if _string(item.get("value"))
        ],
        "expanded_authority_fields": expanded,
        "decision_boundary": denied,
    }


def _risk_flag(code: str, message: str, *, blocking: bool) -> JsonObject:
    return {
        "code": code,
        "message": message,
        "blocking": blocking,
    }


def verify_patch(
    *,
    patch_score: Mapping[str, Any],
    failure_bundle: Mapping[str, Any] | None = None,
    runtime_proof: Mapping[str, Any] | None = None,
    repo_memory_profile: Mapping[str, Any] | None = None,
) -> JsonObject:
    bundle = _as_dict(failure_bundle)
    runtime = _as_dict(runtime_proof)
    repo_memory = _as_dict(repo_memory_profile)
    failure_vector_contract_evidence = _repo_memory_failure_vector_contract_evidence(repo_memory)
    patch_decision = _as_dict(patch_score.get("decision"))

    patch_id = _string(patch_score.get("patch_id")) or "unknown"
    diagnosis_id = _string(patch_score.get("diagnosis_id")) or "unknown"
    patch_score_status = _string(patch_decision.get("status")) or "unknown"
    candidate = _bool(patch_decision.get(CANDIDATE_FOR_PROTECTED_VERIFICATION))
    score = _int(patch_score.get("score"))
    minimum_score = _int(patch_score.get("minimum_score"))
    proof_requirements = _string_list(patch_score.get("proof_requirements"))
    changed_files = _string_list(patch_score.get("changed_files"))
    allowed_files = _string_list(patch_score.get("allowed_files"))

    flags = _authority_expansion_flags(
        patch_score=patch_score,
        failure_bundle=bundle,
        runtime_proof=runtime,
    )

    expanded_contract_fields = _string_list(
        failure_vector_contract_evidence.get("expanded_authority_fields")
    )
    if expanded_contract_fields:
        flags.append(
            {
                "code": FAILURE_VECTOR_CONTRACT_EVIDENCE_AUTHORITY_VIOLATION,
                "message": "RepoMemory FailureVector contract evidence attempted to expand verifier authority.",
                "blocking": True,
                "source": "repo_memory.failure_vector_contract_evidence",
                "fields": expanded_contract_fields,
            }
        )

    if patch_score_status != CANDIDATE_FOR_PROTECTED_VERIFICATION or not candidate:
        flags.append(
            _risk_flag(
                "PATCH_SCORE_NOT_CANDIDATE",
                "PatchScorer did not mark this patch as a protected-verification candidate.",
                blocking=True,
            )
        )

    if score < minimum_score:
        flags.append(
            _risk_flag(
                "PATCH_SCORE_BELOW_MINIMUM",
                "Patch score is below the configured minimum verification threshold.",
                blocking=True,
            )
        )

    if not proof_requirements:
        flags.append(
            _risk_flag(
                "PROOF_REQUIREMENTS_MISSING",
                "Protected verification requires explicit proof commands from PatchScorer.",
                blocking=True,
            )
        )

    blocked = any(_bool(flag.get("blocking")) for flag in flags)
    status = BLOCKED_REVIEW_FIRST if blocked else REVIEW_REQUIRED
    next_action = (
        RESOLVE_BLOCKING_VERIFICATION_FLAGS
        if blocked
        else HUMAN_REVIEW_REQUIRED_BEFORE_PATCH_APPLICATION
    )
    reason = (
        "Blocking verification flags prevent protected review."
        if blocked
        else "Candidate is reviewable, but ProtectedVerifier grants no patch, merge, or semantic authority."
    )

    decision_boundary = {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "automatic_security_fix_allowed": False,
        "automatic_dismissal_allowed": False,
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "sdetkit.protected_verifier",
        "collection_status": "collected",
        "patch_id": patch_id,
        "diagnosis_id": diagnosis_id,
        "inputs": {
            "patch_score_schema": _string(patch_score.get("schema_version")) or "unknown",
            "patch_score_status": patch_score_status,
            "failure_bundle_status": _string(bundle.get("status")) or "not_collected",
            "runtime_proof_status": _string(runtime.get("status")) or "not_collected",
            "repo_memory_profile_status": _string(repo_memory.get("profile_status"))
            or "not_collected",
        },
        "repo_memory_evidence": {
            "failure_vector_contract_evidence": failure_vector_contract_evidence,
        },
        "verification_evidence": {
            "score": score,
            "minimum_score": minimum_score,
            "changed_files": changed_files,
            "allowed_files": allowed_files,
            "proof_requirements": proof_requirements,
            "patch_score_risk_flags": [
                _string(_as_dict(item).get("code"))
                for item in _as_list(patch_score.get("risk_flags"))
                if _string(_as_dict(item).get("code"))
            ],
        },
        "risk_flags": flags,
        "decision": {
            "status": status,
            "review_first": True,
            CANDIDATE_FOR_PROTECTED_VERIFICATION: candidate and not blocked,
            "protected_verification_passed": False,
            "automation_allowed": False,
            "patch_application_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
            "reason": reason,
            "next_action": next_action,
        },
        "decision_boundary": decision_boundary,
    }


def _protected_path(path: str) -> bool:
    return path in PROTECTED_EXACT_PATHS or path.startswith(PROTECTED_PREFIXES)


def _finding(
    code: str,
    message: str,
    *,
    blocking: bool,
    files: list[str] | None = None,
    commands: list[str] | None = None,
) -> JsonObject:
    return {
        "code": code,
        "message": message,
        "blocking": blocking,
        "files": files or [],
        "commands": commands or [],
    }


def _proof_results_by_command(evidence: Mapping[str, Any]) -> dict[str, JsonObject]:
    results: dict[str, JsonObject] = {}
    for item in _as_list(evidence.get("proof_results")):
        result = _as_dict(item)
        command = _string(result.get("command"))
        if command:
            results[command] = result
    return results


def _proof_passed(result: Mapping[str, Any]) -> bool:
    status = _string(result.get("status")).lower()
    return (
        status in {"ok", "pass", "passed", "success", "succeeded"}
        and _int(result.get("exit_code")) == 0
    )


def _compat_safety_gate_evidence(evidence: Mapping[str, Any]) -> JsonObject:
    denied = {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }
    payload = _as_dict(evidence.get("safety_gate_evidence"))
    if not payload:
        return {
            "collection_status": "not_collected",
            "status": "not_collected",
            "source": "verification_evidence.safety_gate_evidence",
            "record_count": 0,
            "review_first_count": 0,
            "safe_fix_allowed_count": 0,
            "reporting_only_count": 0,
            "report_paths": [],
            "expanded_authority_fields": [],
            "decision_boundary": denied,
        }

    boundary = _as_dict(payload.get("decision_boundary"))
    expanded = [key for key in denied if _bool(boundary.get(key))]
    return {
        "collection_status": _string(payload.get("collection_status")) or "collected",
        "status": _string(payload.get("status")) or "safety_gate_evidence_observed",
        "source": _string(payload.get("source")) or "verification_evidence.safety_gate_evidence",
        "record_count": _int(payload.get("record_count")),
        "review_first_count": _int(payload.get("review_first_count")),
        "safe_fix_allowed_count": _int(payload.get("safe_fix_allowed_count")),
        "reporting_only_count": _int(payload.get("reporting_only_count")),
        "report_paths": [
            _string(item) for item in _as_list(payload.get("report_paths")) if _string(item)
        ],
        "expanded_authority_fields": expanded,
        "decision_boundary": denied,
    }


def verify_candidate(
    *,
    patch_score: Mapping[str, Any],
    verification_evidence: Mapping[str, Any],
) -> JsonObject:
    """Backward-compatible wrapper for older read-only candidate surfaces.

    The new contract is verify_patch(). This wrapper preserves the historical
    import surface for replay, repo-memory, readiness, and PR Quality visibility
    callers without granting mutation, merge, or semantic authority.
    """
    decision = _as_dict(patch_score.get("decision"))
    patch_id = _string(patch_score.get("patch_id")) or "unknown"
    diagnosis_id = _string(patch_score.get("diagnosis_id")) or "unknown"
    scored_files = _string_list(patch_score.get("changed_files"))
    allowed_files = _string_list(patch_score.get("allowed_files"))
    evidence_files = _string_list(verification_evidence.get("changed_files"))
    proof_requirements = _string_list(patch_score.get("proof_requirements"))
    proof_results = _proof_results_by_command(verification_evidence)
    safety_gate_evidence = _compat_safety_gate_evidence(verification_evidence)
    findings: list[JsonObject] = []

    if _string(decision.get("status")) != CANDIDATE_FOR_PROTECTED_VERIFICATION or not _bool(
        decision.get(CANDIDATE_FOR_PROTECTED_VERIFICATION)
    ):
        findings.append(
            _finding(
                PATCH_SCORE_NOT_CANDIDATE,
                "PatchScorer did not nominate this patch for protected verification.",
                blocking=True,
            )
        )

    if _bool(decision.get("automation_allowed")):
        findings.append(
            _finding(
                AUTOMATION_BOUNDARY_VIOLATION,
                "PatchScorer output unexpectedly attempts to authorize automation.",
                blocking=True,
            )
        )

    expanded_safetygate_fields = _string_list(safety_gate_evidence.get("expanded_authority_fields"))
    if expanded_safetygate_fields:
        findings.append(
            _finding(
                SAFETYGATE_EVIDENCE_AUTHORITY_VIOLATION,
                "SafetyGate evidence attempted to expand verifier authority.",
                blocking=True,
                files=expanded_safetygate_fields,
            )
        )

    if not evidence_files:
        findings.append(
            _finding(
                VERIFICATION_FILE_INVENTORY_MISSING,
                "Verification evidence must include the observed changed-file inventory.",
                blocking=True,
            )
        )
    elif evidence_files != scored_files:
        findings.append(
            _finding(
                CHANGED_FILE_INVENTORY_MISMATCH,
                "Observed changed files do not exactly match the PatchScorer inventory.",
                blocking=True,
                files=sorted(set(evidence_files).symmetric_difference(scored_files)),
            )
        )

    outside_scope = sorted(set(evidence_files) - set(allowed_files))
    if outside_scope:
        findings.append(
            _finding(
                OUTSIDE_SCORED_SCOPE,
                "Observed changed files exceed PatchScorer approved scope.",
                blocking=True,
                files=outside_scope,
            )
        )

    protected_files = [item for item in evidence_files if _protected_path(item)]
    if protected_files:
        findings.append(
            _finding(
                PROTECTED_PATH_CHANGED,
                "Protected test, workflow, gate, or policy paths remain review-first.",
                blocking=True,
                files=protected_files,
            )
        )

    if not proof_requirements:
        findings.append(
            _finding(
                PROOF_REQUIREMENTS_MISSING,
                "PatchScorer supplied no required proof commands.",
                blocking=True,
            )
        )
    else:
        missing_commands = [
            command for command in proof_requirements if command not in proof_results
        ]
        if missing_commands:
            findings.append(
                _finding(
                    REQUIRED_PROOF_NOT_CAPTURED,
                    "Required proof command results were not captured.",
                    blocking=True,
                    commands=missing_commands,
                )
            )

        failed_commands = [
            command
            for command in proof_requirements
            if command in proof_results and not _proof_passed(proof_results[command])
        ]
        if failed_commands:
            findings.append(
                _finding(
                    REQUIRED_PROOF_FAILED,
                    "One or more required proof commands did not pass.",
                    blocking=True,
                    commands=failed_commands,
                )
            )

    findings.append(
        _finding(
            SEMANTIC_EQUIVALENCE_NOT_PROVEN,
            (
                "This compatibility verifier checks structural scope and captured proof only; "
                "it does not prove semantic equivalence."
            ),
            blocking=False,
        )
    )

    blocked = any(_bool(finding.get("blocking")) for finding in findings)
    status = BLOCKED_REVIEW_FIRST if blocked else STRUCTURALLY_VERIFIED_CANDIDATE

    return {
        "schema_version": SCHEMA_VERSION,
        "patch_id": patch_id,
        "diagnosis_id": diagnosis_id,
        "patch_score": _int(patch_score.get("score")),
        "scored_files": scored_files,
        "observed_changed_files": evidence_files,
        "allowed_files": allowed_files,
        "proof_requirements": proof_requirements,
        "safety_gate_evidence": safety_gate_evidence,
        "findings": findings,
        "decision": {
            "status": status,
            "structural_verification_passed": not blocked,
            "semantic_equivalence_proven": False,
            "automation_allowed": False,
            "merge_authorized": False,
            "reason": (
                "Structural scope and captured proof requirements passed; "
                "semantic proof and automation wiring remain unavailable."
                if not blocked
                else "Protected verification found blocking evidence; keep this patch review-first."
            ),
        },
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    decision = _as_dict(payload.get("decision"))
    evidence = _as_dict(payload.get("verification_evidence"))
    boundary = _as_dict(payload.get("decision_boundary"))
    repo_memory = _as_dict(payload.get("repo_memory_evidence"))
    vector_contract = _as_dict(repo_memory.get("failure_vector_contract_evidence"))
    vector_boundary = _as_dict(vector_contract.get("decision_boundary"))
    flags = [_as_dict(item) for item in _as_list(payload.get("risk_flags"))]

    lines = [
        "# ProtectedVerifier decision",
        "",
        f"- Patch: `{_string(payload.get('patch_id'))}`",
        f"- Diagnosis: `{_string(payload.get('diagnosis_id'))}`",
        f"- Status: `{_string(decision.get('status'))}`",
        f"- Review first: `{str(_bool(decision.get('review_first'))).lower()}`",
        (
            "- Candidate for protected verification: "
            f"`{str(_bool(decision.get('candidate_for_protected_verification'))).lower()}`"
        ),
        (
            "- Protected verification passed: "
            f"`{str(_bool(decision.get('protected_verification_passed'))).lower()}`"
        ),
        f"- Next action: `{_string(decision.get('next_action'))}`",
        "",
        "## Verification evidence",
        "",
        f"- Score: `{_int(evidence.get('score'))}`",
        f"- Minimum score: `{_int(evidence.get('minimum_score'))}`",
        "- Changed files:",
    ]

    changed_files = _string_list(evidence.get("changed_files"))
    lines.extend(f"  - `{path}`" for path in changed_files) if changed_files else lines.append(
        "  - none"
    )

    proof_requirements = _string_list(evidence.get("proof_requirements"))
    lines.extend(["", "## Proof requirements", ""])
    lines.extend(
        f"- `{command}`" for command in proof_requirements
    ) if proof_requirements else lines.append("- none")

    lines.extend(
        [
            "",
            "## RepoMemory FailureVector contract evidence",
            "",
            f"- Collection status: `{_string(vector_contract.get('collection_status'))}`",
            f"- Status: `{_string(vector_contract.get('status'))}`",
            f"- Records: `{_int(vector_contract.get('record_count'))}`",
            (
                "- Security-relevant records: "
                f"`{_int(vector_contract.get('security_relevance_count'))}`"
            ),
            (
                "- Authority boundary preserved records: "
                f"`{_int(vector_contract.get('authority_boundary_preserved_count'))}`"
            ),
            (
                "- Patch application allowed by RepoMemory FailureVector contract evidence: "
                f"`{str(_bool(vector_boundary.get('patch_application_allowed'))).lower()}`"
            ),
            (
                "- Security dismissal allowed by RepoMemory FailureVector contract evidence: "
                f"`{str(_bool(vector_boundary.get('security_dismissal_allowed'))).lower()}`"
            ),
            (
                "- Merge authorized by RepoMemory FailureVector contract evidence: "
                f"`{str(_bool(vector_boundary.get('merge_authorized'))).lower()}`"
            ),
            (
                "- Semantic equivalence claimed by RepoMemory FailureVector contract evidence: "
                f"`{str(_bool(vector_boundary.get('semantic_equivalence_claim'))).lower()}`"
            ),
        ]
    )

    lines.extend(["", "## Risk flags", ""])
    if flags:
        for flag in flags:
            fields = ", ".join(
                _string(item) for item in _as_list(flag.get("fields")) if _string(item)
            )
            suffix = f" fields=`{fields}`" if fields else ""
            lines.append(
                f"- `{_string(flag.get('code'))}`: "
                f"blocking=`{str(_bool(flag.get('blocking'))).lower()}` "
                f"{_string(flag.get('message'))}{suffix}"
            )
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Boundary",
            "",
            f"- Automation allowed: `{str(_bool(boundary.get('automation_allowed'))).lower()}`",
            (
                "- Patch application allowed: "
                f"`{str(_bool(boundary.get('patch_application_allowed'))).lower()}`"
            ),
            f"- Merge authorized: `{str(_bool(boundary.get('merge_authorized'))).lower()}`",
            (
                "- Semantic equivalence proven: "
                f"`{str(_bool(boundary.get('semantic_equivalence_proven'))).lower()}`"
            ),
            (
                "- Automatic security fix allowed: "
                f"`{str(_bool(boundary.get('automatic_security_fix_allowed'))).lower()}`"
            ),
            (
                "- Automatic dismissal allowed: "
                f"`{str(_bool(boundary.get('automatic_dismissal_allowed'))).lower()}`"
            ),
            "",
            REPORTING_ONLY_NOTE,
            "",
        ]
    )
    return "\n".join(lines)


def render_result_markdown(payload: Mapping[str, Any]) -> str:
    decision = _as_dict(payload.get("decision"))
    findings = [_as_dict(item) for item in _as_list(payload.get("findings"))]
    safety_gate = _as_dict(payload.get("safety_gate_evidence"))

    lines = [
        "# ProtectedVerifier result",
        "",
        f"- Patch: `{_string(payload.get('patch_id'))}`",
        f"- Diagnosis: `{_string(payload.get('diagnosis_id'))}`",
        f"- Status: `{_string(decision.get('status'))}`",
        (
            "- Structural verification passed: "
            f"`{str(_bool(decision.get('structural_verification_passed'))).lower()}`"
        ),
        (
            "- Semantic equivalence proven: "
            f"`{str(_bool(decision.get('semantic_equivalence_proven'))).lower()}`"
        ),
        f"- Automation allowed: `{str(_bool(decision.get('automation_allowed'))).lower()}`",
        f"- Merge authorized: `{str(_bool(decision.get('merge_authorized'))).lower()}`",
        "",
        "## Findings",
        "",
    ]

    if findings:
        for finding in findings:
            files = _string_list(finding.get("files"))
            commands = _string_list(finding.get("commands"))
            detail = ""
            if files:
                detail = f" files=`{', '.join(files)}`"
            if commands:
                detail = f" commands=`{', '.join(commands)}`"
            lines.append(
                f"- `{_string(finding.get('code'))}`: "
                f"blocking=`{str(_bool(finding.get('blocking'))).lower()}` "
                f"{_string(finding.get('message'))}{detail}"
            )
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## SafetyGate evidence",
            "",
            f"- Status: `{_string(safety_gate.get('status'))}`",
            f"- Collection: `{_string(safety_gate.get('collection_status'))}`",
            f"- Record count: `{_int(safety_gate.get('record_count'))}`",
            "",
            RESULT_REPORTING_ONLY_NOTE,
            "",
        ]
    )
    return "\n".join(lines)


def write_result(payload: Mapping[str, Any], *, out_dir: Path) -> dict[str, str]:
    json_path = out_dir / RESULT_JSON
    markdown_path = out_dir / RESULT_MD
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_result_markdown(payload), encoding="utf-8")
    return {
        "_".join(("protected", "verifier", "json")): json_path.as_posix(),
        "_".join(("protected", "verifier", "markdown")): markdown_path.as_posix(),
    }


def write_protected_verifier_decision(
    payload: Mapping[str, Any],
    *,
    out_dir: Path,
) -> dict[str, str]:
    json_path = out_dir / PROTECTED_VERIFIER_JSON
    markdown_path = out_dir / PROTECTED_VERIFIER_MD
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(payload), encoding="utf-8")
    return {
        "protected_verifier_json": json_path.as_posix(),
        "protected_verifier_markdown": markdown_path.as_posix(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.protected_verifier")
    parser.add_argument("--patch-score", type=Path, required=True)
    parser.add_argument("--verification-evidence", type=Path)
    parser.add_argument("--failure-bundle", type=Path)
    parser.add_argument("--runtime-proof", type=Path)
    parser.add_argument("--repo-memory-profile", type=Path)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        patch_score_payload = _read_json(args.patch_score)
        if args.verification_evidence is not None:
            payload = verify_candidate(
                patch_score=patch_score_payload,
                verification_evidence=_read_json(args.verification_evidence),
            )
            artifacts = write_result(payload, out_dir=args.out_dir)
        else:
            payload = verify_patch(
                patch_score=patch_score_payload,
                failure_bundle=_read_json(args.failure_bundle),
                runtime_proof=_read_json(args.runtime_proof),
                repo_memory_profile=_read_json(args.repo_memory_profile),
            )
            artifacts = write_protected_verifier_decision(payload, out_dir=args.out_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(
            json.dumps(
                {
                    "artifacts": artifacts,
                    "decision": payload["decision"],
                    "risk_flags": payload.get("risk_flags", payload.get("findings", [])),
                    "schema_version": payload["schema_version"],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        for key, value in artifacts.items():
            print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
