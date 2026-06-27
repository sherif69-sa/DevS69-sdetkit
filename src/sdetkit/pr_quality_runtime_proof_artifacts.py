from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.pr_quality_runtime_proof_artifacts.v1"
DEFAULT_OUT_DIR = Path("build") / "pr-quality" / "runtime-proof" / "summary"
SUMMARY_JSON = "runtime-proof-artifacts.json"
SUMMARY_MD = "runtime-proof-artifacts.md"

COLLECTED = "collected"
NOT_COLLECTED = "_".join(("not", "collected"))
REPLAY_MANIFEST = "_".join(("replay", "manifest"))
REPLAY_MANIFEST_PRESENT = "_".join(("replay", "manifest", "present"))
REPLAY_MANIFEST_SCENARIO_COUNT = "_".join(("replay", "manifest", "scenario", "count"))
REPLAY_MANIFEST_REPORTING_ONLY = "_".join(("replay", "manifest", "reporting", "only"))
REPLAY_MANIFEST_AUTOMATION_ALLOWED = "_".join(("replay", "manifest", "automation", "allowed"))
REPLAY_MANIFEST_MERGE_AUTHORIZED = "_".join(("replay", "manifest", "merge", "authorized"))
REPLAY_MANIFEST_SEMANTIC_EQUIVALENCE_PROVEN = "_".join(
    ("replay", "manifest", "semantic", "equivalence", "proven")
)
BENCHMARK_RUNTIME_PROOF_CONTRACT_EVIDENCE = "_".join(
    ("runtime", "proof", "protected", "verifier", "contract", "evidence")
)
BENCHMARK_RUNTIME_PROOF_CONTRACT_REPLAYED = "_".join(
    (
        "runtime",
        "proof",
        "protected",
        "verifier",
        "contract",
        "evidence",
        "replayed",
    )
)
BENCHMARK_RUNTIME_CONTRACT_COLLECTION_STATUS = "_".join(
    ("runtime", "contract", "collection", "status")
)
BENCHMARK_RUNTIME_CONTRACT_STATUS = "_".join(("runtime", "contract", "status"))
BENCHMARK_RUNTIME_CONTRACT_SCENARIO_COUNT = "_".join(("runtime", "contract", "scenario", "count"))
BENCHMARK_RUNTIME_CONTRACT_RECORD_COUNT = "_".join(("runtime", "contract", "record", "count"))
BENCHMARK_RUNTIME_CONTRACT_SECURITY_RELEVANCE_COUNT = "_".join(
    ("runtime", "contract", "security", "relevance", "count")
)
BENCHMARK_RUNTIME_CONTRACT_AUTHORITY_BOUNDARY_PRESERVED_COUNT = "_".join(
    ("runtime", "contract", "authority", "boundary", "preserved", "count")
)
BENCHMARK_RUNTIME_CONTRACT_EXPANDED_AUTHORITY_FIELDS = "_".join(
    ("runtime", "contract", "expanded", "authority", "fields")
)
BENCHMARK_RUNTIME_CONTRACT_PATCH_APPLICATION_ALLOWED = "_".join(
    ("runtime", "contract", "patch", "application", "allowed")
)
BENCHMARK_RUNTIME_CONTRACT_SECURITY_DISMISSAL_ALLOWED = "_".join(
    ("runtime", "contract", "security", "dismissal", "allowed")
)
BENCHMARK_RUNTIME_CONTRACT_MERGE_AUTHORIZED = "_".join(
    ("runtime", "contract", "merge", "authorized")
)
BENCHMARK_RUNTIME_CONTRACT_SEMANTIC_EQUIVALENCE_CLAIM = "_".join(
    ("runtime", "contract", "semantic", "equivalence", "claim")
)
TRUSTED_HISTORY = "_".join(("trusted", "history"))
FLAKY_TEST_REGISTRY_COLLECTION_STATUS = "_".join(
    ("flaky", "test", "registry", "collection", "status")
)
FLAKY_TEST_REGISTRY_STATUS = "_".join(("flaky", "test", "registry", "status"))
FLAKY_TEST_REGISTRY_ENTRY_COUNT = "_".join(("flaky", "test", "registry", "entry", "count"))
FLAKY_TEST_REGISTRY_OBSERVATION_STATUS = "_".join(
    ("flaky", "test", "registry", "observation", "status")
)
FLAKY_TEST_REGISTRY_OBSERVATIONS_COLLECTED = "_".join(
    ("flaky", "test", "registry", "observations", "collected")
)
FLAKY_TEST_REGISTRY_PRODUCER_VETTED = "_".join(("flaky", "test", "registry", "producer", "vetted"))
FLAKY_TEST_REGISTRY_RAW_TEST_IDENTITY_EMITTED = "_".join(
    ("flaky", "test", "registry", "raw", "test", "identity", "emitted")
)
FLAKY_TEST_REGISTRY_CURRENT_PR_DECISION_INPUT = "_".join(
    ("flaky", "test", "registry", "current", "pr", "decision", "input")
)
TRUSTED_DIAGNOSTIC_SIGNAL_SNAPSHOT_HISTORY = "_".join(
    ("trusted", "diagnostic", "signal", "snapshot", "history")
)
BASE_ANCESTRY_VERIFIED = "_".join(("base", "ancestry", "verified"))
LIVE_PROVEN_RECORD_COUNT = "_".join(("live", "contract", "proven", "record", "count"))
PRIOR_HISTORY_READ_ONLY_INPUT = "_".join(("prior", "history", "is", "read", "only", "input"))
PROOF_COMMANDS_EXECUTED_BY_READER = "_".join(("proof", "commands", "executed", "by", "reader"))
TRUSTED_HISTORY_STATUS = "_".join(("trusted", "history", "status"))
CONTROLLED_VALIDATION_RECORD_COUNT = "_".join(("controlled", "validation", "record", "count"))
CONTROLLED_VALIDATION_SCENARIO_COUNT = "_".join(("controlled", "validation", "scenario", "count"))
CONTROLLED_STRUCTURALLY_VERIFIED_COUNT = "_".join(
    ("controlled", "structurally", "verified", "count")
)
CONTROLLED_REVIEW_FIRST_COUNT = "_".join(("controlled", "review", "first", "count"))
FAILURE_VECTOR_CONTRACT_EVIDENCE = "_".join(("failure", "vector", "contract", "evidence"))
SECURITY_DISMISSAL_ALLOWED = "_".join(("security", "dismissal", "allowed"))
SEMANTIC_EQUIVALENCE_CLAIM = "_".join(("semantic", "equivalence", "claim"))
PROTECTED_VERIFIER_RUNTIME_PROOF_EVIDENCE = "_".join(("runtime", "proof", "evidence"))
PROTECTED_VERIFIER_BENCHMARK_CONTRACT_REPLAY_EVIDENCE = "_".join(
    ("benchmark", "contract", "replay", "evidence")
)
PROTECTED_VERIFIER_BENCHMARK_CONTRACT_COLLECTION_STATUS = "_".join(
    ("benchmark", "contract", "collection", "status")
)
PROTECTED_VERIFIER_BENCHMARK_CONTRACT_STATUS = "_".join(("benchmark", "contract", "status"))
PROTECTED_VERIFIER_BENCHMARK_CONTRACT_SCENARIO_COUNT = "_".join(
    ("benchmark", "contract", "scenario", "count")
)
PROTECTED_VERIFIER_BENCHMARK_CONTRACT_RECORD_COUNT = "_".join(
    ("benchmark", "contract", "record", "count")
)
PROTECTED_VERIFIER_BENCHMARK_CONTRACT_SECURITY_RELEVANCE_COUNT = "_".join(
    ("benchmark", "contract", "security", "relevance", "count")
)
PROTECTED_VERIFIER_BENCHMARK_CONTRACT_AUTHORITY_BOUNDARY_PRESERVED_COUNT = "_".join(
    ("benchmark", "contract", "authority", "boundary", "preserved", "count")
)
PROTECTED_VERIFIER_BENCHMARK_CONTRACT_EXPANDED_AUTHORITY_FIELDS = "_".join(
    ("benchmark", "contract", "expanded", "authority", "fields")
)
PROTECTED_VERIFIER_BENCHMARK_CONTRACT_PATCH_APPLICATION_ALLOWED = "_".join(
    ("benchmark", "contract", "patch", "application", "allowed")
)
PROTECTED_VERIFIER_BENCHMARK_CONTRACT_SECURITY_DISMISSAL_ALLOWED = "_".join(
    ("benchmark", "contract", "security", "dismissal", "allowed")
)
PROTECTED_VERIFIER_BENCHMARK_CONTRACT_MERGE_AUTHORIZED = "_".join(
    ("benchmark", "contract", "merge", "authorized")
)
PROTECTED_VERIFIER_BENCHMARK_CONTRACT_SEMANTIC_EQUIVALENCE_CLAIM = "_".join(
    ("benchmark", "contract", "semantic", "equivalence", "claim")
)

JsonObject = dict[str, Any]


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    return value is True


def _read_json(path: Path | None) -> JsonObject:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _as_dict(payload)


def _isolated_profile_results(evidence: Mapping[str, Any]) -> list[JsonObject]:
    payload = _as_dict(evidence)
    if not payload:
        return []

    decision_boundary = _as_dict(payload.get("decision_boundary"))
    isolation = _as_dict(payload.get("isolation"))
    network_boundary = _as_dict(payload.get("network_boundary"))
    claim_value = payload.get("inventory_claim_match")
    inventory_claim_match = None if claim_value is None else _bool(claim_value)
    git_inventory_verified = _bool(decision_boundary.get("git_inventory_verified"))

    boundary_authority_expansion = any(
        _bool(decision_boundary.get(field))
        for field in (
            "automation_allowed",
            "patch_application_allowed",
            "security_dismissal_allowed",
            "merge_authorized",
            "semantic_equivalence_proven",
        )
    )

    profiles: list[JsonObject] = []
    for raw in _as_list(payload.get("proof_results")):
        item = _as_dict(raw)
        if not item:
            continue

        runtime_guard = _as_dict(item.get("runtime_guard"))
        authority_expansion = boundary_authority_expansion or any(
            _bool(item.get(field))
            for field in (
                "automation_allowed",
                "patch_application_allowed",
                "security_dismissal_allowed",
                "merge_authorized",
                "semantic_equivalence_proven",
            )
        )
        status = _string(item.get("status") or "unknown")
        timed_out = _bool(item.get("timed_out"))
        workspace_mutated = _bool(item.get("workspace_mutated_during_execution"))
        runtime_guard_violation = _bool(runtime_guard.get("runtime_guard_violation"))
        review_first = (
            status != "passed"
            or timed_out
            or workspace_mutated
            or runtime_guard_violation
            or inventory_claim_match is False
            or not git_inventory_verified
            or authority_expansion
        )

        profiles.append(
            {
                "profile_id": _string(item.get("profile_id") or "unknown"),
                "command": _string(item.get("command") or "unknown"),
                "status": status,
                "exit_code": _int(item.get("exit_code")),
                "timed_out": timed_out,
                "workspace_mutated": workspace_mutated,
                "runtime_guard_status": _string(runtime_guard.get("status") or "unknown"),
                "runtime_guard_violation": runtime_guard_violation,
                "inventory_claim_match": inventory_claim_match,
                "git_inventory_verified": git_inventory_verified,
                "network_boundary_status": _string(
                    network_boundary.get("status")
                    or isolation.get("network_boundary_status")
                    or "unknown"
                ),
                "network_isolation_required": _bool(isolation.get("network_isolation_required")),
                "network_isolation_enforced": _bool(isolation.get("network_isolation_enforced")),
                "network_backend": _string(
                    item.get("network_backend") or network_boundary.get("backend") or "none"
                ),
                "network_backend_variant": _string(
                    item.get("network_backend_variant")
                    or network_boundary.get("backend_variant")
                    or "none"
                ),
                "network_backend_command_wrapped": _bool(
                    item.get("network_backend_command_wrapped")
                ),
                "review_first": review_first,
                "reporting_only": True,
                "automation_allowed": False,
                "patch_application_allowed": False,
                "security_dismissal_allowed": False,
                "merge_authorized": False,
                "semantic_equivalence_proven": False,
                "authority_expansion_detected": authority_expansion,
            }
        )

    return profiles


def _isolated_proof_summary(evidence: Mapping[str, Any]) -> JsonObject:
    payload = _as_dict(evidence)
    if not payload:
        return {
            "collection_status": NOT_COLLECTED,
            "status": NOT_COLLECTED,
            "profile_visibility_status": NOT_COLLECTED,
            "profile_results": [],
        }

    proof_summary = _as_dict(payload.get("proof_summary"))
    runtime_guard = _as_dict(payload.get("runtime_guard"))
    network_boundary = _as_dict(payload.get("network_boundary"))
    isolation = _as_dict(payload.get("isolation"))
    decision_boundary = _as_dict(payload.get("decision_boundary"))
    profile_results = _isolated_profile_results(payload)
    executed_count = _int(proof_summary.get("executed_count"))
    profile_review_first_count = sum(
        1 for item in profile_results if _bool(item.get("review_first"))
    )
    profile_authority_expansion_detected = any(
        _bool(item.get("authority_expansion_detected")) for item in profile_results
    )

    if not profile_results:
        profile_visibility_status = NOT_COLLECTED if executed_count == 0 else "incomplete"
    elif len(profile_results) != executed_count:
        profile_visibility_status = "incomplete"
    elif profile_review_first_count:
        profile_visibility_status = "review_first"
    else:
        profile_visibility_status = COLLECTED

    claim_value = payload.get("inventory_claim_match")
    inventory_claim_match = None if claim_value is None else _bool(claim_value)

    return {
        "collection_status": COLLECTED,
        "status": _string(payload.get("status") or "unknown"),
        "git_inventory_verified": _bool(decision_boundary.get("git_inventory_verified")),
        "inventory_claim_match": inventory_claim_match,
        "runtime_guard_checked": _bool(runtime_guard.get("checked")),
        "runtime_guard_passed": _bool(runtime_guard.get("passed")),
        "runtime_guard_violation_count": _int(runtime_guard.get("violation_count")),
        "runtime_guard_status_counts": _as_dict(runtime_guard.get("status_counts")),
        "network_boundary_status": _string(
            network_boundary.get("status") or isolation.get("network_boundary_status")
        ),
        "network_isolation_required": _bool(isolation.get("network_isolation_required")),
        "network_isolation_enforced": _bool(isolation.get("network_isolation_enforced")),
        "proof_execution_blocked": _bool(isolation.get("proof_execution_blocked")),
        "profiles_requested": _int(proof_summary.get("requested_count")),
        "profiles_executed": executed_count,
        "profiles_blocked": _int(proof_summary.get("blocked_count")),
        "profiles_passed": _int(proof_summary.get("passed_count")),
        "profiles_failed": _int(proof_summary.get("failed_count")),
        "requested_profile_ids": _string_list(payload.get("requested_profiles")),
        "profile_visibility_status": profile_visibility_status,
        "profile_review_first_count": profile_review_first_count,
        "profile_authority_expansion_detected": profile_authority_expansion_detected,
        "profile_results": profile_results,
    }


def _string_list(value: object) -> list[str]:
    return [_string(item) for item in _as_list(value) if _string(item)]


def _live_benchmark_summary(report: Mapping[str, Any]) -> JsonObject:
    payload = _as_dict(report)
    if not payload:
        return {
            "collection_status": NOT_COLLECTED,
            "status": NOT_COLLECTED,
        }

    live = _as_dict(payload.get("live_evidence"))
    boundary = _as_dict(payload.get("safety_boundary"))
    replay = _as_dict(payload.get(REPLAY_MANIFEST))
    runtime_contract = _as_dict(payload.get(BENCHMARK_RUNTIME_PROOF_CONTRACT_EVIDENCE))
    runtime_contract_boundary = _as_dict(runtime_contract.get("decision_boundary"))
    return {
        "collection_status": COLLECTED,
        "status": _string(payload.get("status") or "unknown"),
        "report_mode": _string(payload.get("report_mode") or "unknown"),
        "scenario_count": _int(payload.get("scenario_count")),
        "passed_count": _int(payload.get("passed_count")),
        "failed_count": _int(payload.get("failed_count")),
        "git_inventory_verified_count": _int(live.get("git_inventory_verified_count")),
        "expected_failed_evidence_count": _int(live.get("expected_failed_evidence_count")),
        "network_boundary_blocked_count": _int(live.get("network_boundary_blocked_count")),
        "anti_cheat_rejection_count": _int(live.get("anti_cheat_rejection_count")),
        "network_isolation_enforced_count": _int(live.get("network_isolation_enforced_count")),
        "automation_allowed_count": _int(boundary.get("automation_allowed_count")),
        "merge_authorized_count": _int(boundary.get("merge_authorized_count")),
        "semantic_equivalence_claimed_count": _int(
            boundary.get("semantic_equivalence_claimed_count")
        ),
        "boundary_preserved": _bool(boundary.get("preserved")),
        BENCHMARK_RUNTIME_CONTRACT_COLLECTION_STATUS: _string(
            runtime_contract.get("collection_status")
        )
        or NOT_COLLECTED,
        BENCHMARK_RUNTIME_CONTRACT_STATUS: _string(runtime_contract.get("status")) or NOT_COLLECTED,
        BENCHMARK_RUNTIME_CONTRACT_SCENARIO_COUNT: _int(runtime_contract.get("scenario_count")),
        BENCHMARK_RUNTIME_CONTRACT_RECORD_COUNT: _int(runtime_contract.get("record_count")),
        BENCHMARK_RUNTIME_CONTRACT_SECURITY_RELEVANCE_COUNT: _int(
            runtime_contract.get("security_relevance_count")
        ),
        BENCHMARK_RUNTIME_CONTRACT_AUTHORITY_BOUNDARY_PRESERVED_COUNT: _int(
            runtime_contract.get("authority_boundary_preserved_count")
        ),
        BENCHMARK_RUNTIME_CONTRACT_EXPANDED_AUTHORITY_FIELDS: _string_list(
            runtime_contract.get("expanded_authority_fields")
        ),
        BENCHMARK_RUNTIME_CONTRACT_PATCH_APPLICATION_ALLOWED: _bool(
            runtime_contract_boundary.get("patch_application_allowed")
        ),
        BENCHMARK_RUNTIME_CONTRACT_SECURITY_DISMISSAL_ALLOWED: _bool(
            runtime_contract_boundary.get("security_dismissal_allowed")
        ),
        BENCHMARK_RUNTIME_CONTRACT_MERGE_AUTHORIZED: _bool(
            runtime_contract_boundary.get("merge_authorized")
        ),
        BENCHMARK_RUNTIME_CONTRACT_SEMANTIC_EQUIVALENCE_CLAIM: _bool(
            runtime_contract_boundary.get("semantic_equivalence_claim")
        ),
        REPLAY_MANIFEST_PRESENT: bool(replay),
        REPLAY_MANIFEST_SCENARIO_COUNT: _int(replay.get("scenario_count")),
        REPLAY_MANIFEST_REPORTING_ONLY: _bool(replay.get("reporting_only")),
        REPLAY_MANIFEST_AUTOMATION_ALLOWED: _bool(replay.get("automation_allowed")),
        REPLAY_MANIFEST_MERGE_AUTHORIZED: _bool(replay.get("merge_authorized")),
        REPLAY_MANIFEST_SEMANTIC_EQUIVALENCE_PROVEN: _bool(
            replay.get("semantic_equivalence_proven")
        ),
    }


def _repo_memory_summary(profile: Mapping[str, Any]) -> JsonObject:
    payload = _as_dict(profile)
    if not payload:
        return {
            "collection_status": NOT_COLLECTED,
            "status": NOT_COLLECTED,
        }

    provenance = _as_dict(payload.get("proof_provenance"))
    safety_gate = _as_dict(payload.get("safety_gate_evidence"))
    safety_boundary = _as_dict(safety_gate.get("decision_boundary"))
    trajectory_authority = _as_dict(payload.get("trajectory_authority_evidence"))
    trajectory_authority_boundary = _as_dict(trajectory_authority.get("decision_boundary"))
    boundary = _as_dict(payload.get("decision_boundary"))
    return {
        "collection_status": COLLECTED,
        "status": _string(payload.get("profile_status") or "unknown"),
        "live_contract_proven": _bool(provenance.get("live_contract_proven")),
        "known_safe_candidate_count": _int(payload.get("known_safe_candidate_count")),
        "live_safe_candidate_count": _int(payload.get("live_safe_candidate_count")),
        "git_verified_scenario_count": _int(provenance.get("git_verified_scenario_count")),
        "expected_failed_scenario_count": _int(provenance.get("expected_failed_scenario_count")),
        "network_boundary_blocked_scenario_count": _int(
            provenance.get("network_boundary_blocked_scenario_count")
        ),
        "anti_cheat_rejection_scenario_count": _int(
            provenance.get("anti_cheat_rejection_scenario_count")
        ),
        "safety_gate_status": _string(safety_gate.get("status") or NOT_COLLECTED),
        "safety_gate_record_count": _int(safety_gate.get("record_count")),
        "safety_gate_safe_fix_allowed_count": _int(safety_gate.get("safe_fix_allowed_count")),
        "safety_gate_review_first_count": _int(safety_gate.get("review_first_count")),
        "safety_gate_automation_allowed": _bool(safety_boundary.get("automation_allowed")),
        "safety_gate_merge_authorized": _bool(safety_boundary.get("merge_authorized")),
        "safety_gate_semantic_equivalence_proven": _bool(
            safety_boundary.get("semantic_equivalence_proven")
        ),
        "trajectory_authority_status": _string(trajectory_authority.get("status") or NOT_COLLECTED),
        "trajectory_authority_record_count": _int(trajectory_authority.get("record_count")),
        "trajectory_authority_review_first_count": _int(
            trajectory_authority.get("review_first_count")
        ),
        "trajectory_authority_auto_fix_allowed_count": _int(
            trajectory_authority.get("auto_fix_allowed_count")
        ),
        "trajectory_authority_reporting_only_count": _int(
            trajectory_authority.get("reporting_only_count")
        ),
        "trajectory_authority_automation_allowed": _bool(
            trajectory_authority_boundary.get("automation_allowed")
        ),
        "trajectory_authority_patch_application_allowed": _bool(
            trajectory_authority_boundary.get("patch_application_allowed")
        ),
        "trajectory_authority_security_dismissal_allowed": _bool(
            trajectory_authority_boundary.get("automatic_dismissal_allowed")
        ),
        "trajectory_authority_merge_authorized": _bool(
            trajectory_authority_boundary.get("merge_authorized")
        ),
        "trajectory_authority_semantic_equivalence_proven": _bool(
            trajectory_authority_boundary.get("semantic_equivalence_proven")
        ),
        "automation_allowed": _bool(boundary.get("automation_allowed")),
        "merge_authorized": _bool(boundary.get("merge_authorized")),
        "semantic_equivalence_proven": _bool(boundary.get("semantic_equivalence_proven")),
    }


def _protected_verifier_summary(result: Mapping[str, Any]) -> JsonObject:
    payload = _as_dict(result)
    if not payload:
        return {
            "collection_status": NOT_COLLECTED,
            "status": NOT_COLLECTED,
        }

    decision = _as_dict(payload.get("decision"))
    decision_boundary = _as_dict(payload.get("decision_boundary"))
    repo_memory = _as_dict(payload.get("repo_memory_evidence"))
    contract = _as_dict(repo_memory.get(FAILURE_VECTOR_CONTRACT_EVIDENCE))
    contract_boundary = _as_dict(contract.get("decision_boundary"))
    runtime_proof = _as_dict(payload.get(PROTECTED_VERIFIER_RUNTIME_PROOF_EVIDENCE))
    benchmark_contract = _as_dict(
        runtime_proof.get(PROTECTED_VERIFIER_BENCHMARK_CONTRACT_REPLAY_EVIDENCE)
    )
    benchmark_contract_boundary = _as_dict(benchmark_contract.get("decision_boundary"))

    return {
        "collection_status": COLLECTED,
        "status": _string(decision.get("status") or payload.get("status") or "unknown"),
        "review_first": _bool(decision.get("review_first")),
        "contract_status": _string(contract.get("status") or NOT_COLLECTED),
        "contract_record_count": _int(contract.get("record_count")),
        "contract_security_relevance_count": _int(contract.get("security_relevance_count")),
        "contract_authority_boundary_preserved_count": _int(
            contract.get("authority_boundary_preserved_count")
        ),
        "contract_patch_application_allowed": _bool(
            contract_boundary.get("patch_application_allowed")
        ),
        "contract_security_dismissal_allowed": _bool(
            contract_boundary.get(SECURITY_DISMISSAL_ALLOWED)
        ),
        "contract_merge_authorized": _bool(contract_boundary.get("merge_authorized")),
        "contract_semantic_equivalence_claim": _bool(
            contract_boundary.get(SEMANTIC_EQUIVALENCE_CLAIM)
        ),
        PROTECTED_VERIFIER_BENCHMARK_CONTRACT_COLLECTION_STATUS: _string(
            benchmark_contract.get("collection_status")
        )
        or NOT_COLLECTED,
        PROTECTED_VERIFIER_BENCHMARK_CONTRACT_STATUS: _string(benchmark_contract.get("status"))
        or NOT_COLLECTED,
        PROTECTED_VERIFIER_BENCHMARK_CONTRACT_SCENARIO_COUNT: _int(
            benchmark_contract.get("scenario_count")
        ),
        PROTECTED_VERIFIER_BENCHMARK_CONTRACT_RECORD_COUNT: _int(
            benchmark_contract.get("record_count")
        ),
        PROTECTED_VERIFIER_BENCHMARK_CONTRACT_SECURITY_RELEVANCE_COUNT: _int(
            benchmark_contract.get("security_relevance_count")
        ),
        PROTECTED_VERIFIER_BENCHMARK_CONTRACT_AUTHORITY_BOUNDARY_PRESERVED_COUNT: _int(
            benchmark_contract.get("authority_boundary_preserved_count")
        ),
        PROTECTED_VERIFIER_BENCHMARK_CONTRACT_EXPANDED_AUTHORITY_FIELDS: _string_list(
            benchmark_contract.get("expanded_authority_fields")
        ),
        PROTECTED_VERIFIER_BENCHMARK_CONTRACT_PATCH_APPLICATION_ALLOWED: _bool(
            benchmark_contract_boundary.get("patch_application_allowed")
        ),
        PROTECTED_VERIFIER_BENCHMARK_CONTRACT_SECURITY_DISMISSAL_ALLOWED: _bool(
            benchmark_contract_boundary.get(SECURITY_DISMISSAL_ALLOWED)
        ),
        PROTECTED_VERIFIER_BENCHMARK_CONTRACT_MERGE_AUTHORIZED: _bool(
            benchmark_contract_boundary.get("merge_authorized")
        ),
        PROTECTED_VERIFIER_BENCHMARK_CONTRACT_SEMANTIC_EQUIVALENCE_CLAIM: _bool(
            benchmark_contract_boundary.get(SEMANTIC_EQUIVALENCE_CLAIM)
        ),
        "automation_allowed": _bool(decision.get("automation_allowed"))
        or _bool(decision_boundary.get("automation_allowed")),
        "merge_authorized": _bool(decision.get("merge_authorized"))
        or _bool(decision_boundary.get("merge_authorized")),
        "semantic_equivalence_proven": _bool(decision.get("semantic_equivalence_proven"))
        or _bool(decision_boundary.get("semantic_equivalence_proven")),
    }


def _trusted_diagnostic_signal_snapshot_history_summary(
    evidence: Mapping[str, Any],
) -> JsonObject:
    payload = _as_dict(evidence)
    if not payload:
        return {
            "collection_status": NOT_COLLECTED,
            "status": NOT_COLLECTED,
        }

    source = _as_dict(payload.get("source"))
    history = _as_dict(payload.get("history"))
    boundary = _as_dict(payload.get("decision_boundary"))
    return {
        "collection_status": COLLECTED,
        "status": _string(payload.get("status") or "unknown"),
        "source_workflow": _string(source.get("workflow") or "unknown"),
        "latest_accepted_main_head": _string(source.get("head_sha") or "unknown"),
        BASE_ANCESTRY_VERIFIED: _bool(source.get(BASE_ANCESTRY_VERIFIED)),
        "record_count": _int(history.get("record_count")),
        "quiet_green_advisory_baseline_record_count": _int(
            history.get("quiet_green_advisory_baseline_record_count")
        ),
        "review_signal_record_count": _int(history.get("review_signal_record_count")),
        "integration_proof_signal_record_count": _int(
            history.get("integration_proof_signal_record_count")
        ),
        "latest_snapshot_status": _string(history.get("latest_snapshot_status") or "not_collected"),
        "latest_primary_signal_kind": _string(
            history.get("latest_primary_signal_kind") or "unknown"
        ),
        "advisor_false_positive_rate_status": _string(
            history.get("advisor_false_positive_rate_status") or "unknown"
        ),
        "reviewed_false_positive_count": history.get("reviewed_false_positive_count"),
        "reviewed_observation_count": history.get("reviewed_observation_count"),
        PRIOR_HISTORY_READ_ONLY_INPUT: _bool(history.get(PRIOR_HISTORY_READ_ONLY_INPUT)),
        "reporting_only": _bool(boundary.get("reporting_only")),
        "current_pr_decision_input": _bool(boundary.get("current_pr_decision_input")),
        "feeds_repo_memory": _bool(boundary.get("feeds_repo_memory")),
        "proof_commands_executed": _bool(boundary.get("proof_commands_executed")),
        "patch_application_allowed": _bool(boundary.get("patch_application_allowed")),
        "automation_allowed": _bool(boundary.get("automation_allowed")),
        "merge_authorized": _bool(boundary.get("merge_authorized")),
        "semantic_equivalence_proven": _bool(boundary.get("semantic_equivalence_proven")),
        "historical_snapshot_authorizes_current_action": _bool(
            boundary.get("historical_snapshot_authorizes_current_action")
        ),
    }


def _trusted_history_summary(evidence: Mapping[str, Any]) -> JsonObject:
    payload = _as_dict(evidence)
    if not payload:
        return {
            "collection_status": NOT_COLLECTED,
            "status": NOT_COLLECTED,
            FLAKY_TEST_REGISTRY_COLLECTION_STATUS: NOT_COLLECTED,
            FLAKY_TEST_REGISTRY_STATUS: NOT_COLLECTED,
            FLAKY_TEST_REGISTRY_ENTRY_COUNT: 0,
            FLAKY_TEST_REGISTRY_OBSERVATION_STATUS: NOT_COLLECTED,
            FLAKY_TEST_REGISTRY_OBSERVATIONS_COLLECTED: False,
            FLAKY_TEST_REGISTRY_PRODUCER_VETTED: False,
            FLAKY_TEST_REGISTRY_RAW_TEST_IDENTITY_EMITTED: False,
            FLAKY_TEST_REGISTRY_CURRENT_PR_DECISION_INPUT: False,
        }

    source = _as_dict(payload.get("source"))
    history = _as_dict(payload.get("history"))
    boundary = _as_dict(payload.get("decision_boundary"))
    return {
        "collection_status": COLLECTED,
        "status": _string(payload.get("status") or "unknown"),
        "source_workflow": _string(source.get("workflow") or "unknown"),
        "source_run_id": _string(source.get("run_id") or "unknown"),
        "latest_accepted_main_head": _string(history.get("latest_accepted_main_head") or "unknown"),
        BASE_ANCESTRY_VERIFIED: _bool(source.get(BASE_ANCESTRY_VERIFIED)),
        "record_count": _int(history.get("record_count")),
        LIVE_PROVEN_RECORD_COUNT: _int(history.get(LIVE_PROVEN_RECORD_COUNT)),
        PRIOR_HISTORY_READ_ONLY_INPUT: _bool(history.get(PRIOR_HISTORY_READ_ONLY_INPUT)),
        CONTROLLED_VALIDATION_RECORD_COUNT: _int(history.get(CONTROLLED_VALIDATION_RECORD_COUNT)),
        CONTROLLED_VALIDATION_SCENARIO_COUNT: _int(
            history.get(CONTROLLED_VALIDATION_SCENARIO_COUNT)
        ),
        CONTROLLED_STRUCTURALLY_VERIFIED_COUNT: _int(
            history.get(CONTROLLED_STRUCTURALLY_VERIFIED_COUNT)
        ),
        CONTROLLED_REVIEW_FIRST_COUNT: _int(history.get(CONTROLLED_REVIEW_FIRST_COUNT)),
        "latest_controlled_validation_status": _string(
            history.get("latest_controlled_validation_status") or NOT_COLLECTED
        ),
        "controlled_validation_reporting_only": _bool(
            history.get("controlled_validation_reporting_only")
        ),
        FLAKY_TEST_REGISTRY_COLLECTION_STATUS: _string(
            history.get(FLAKY_TEST_REGISTRY_COLLECTION_STATUS) or NOT_COLLECTED
        ),
        FLAKY_TEST_REGISTRY_STATUS: _string(
            history.get(FLAKY_TEST_REGISTRY_STATUS) or NOT_COLLECTED
        ),
        FLAKY_TEST_REGISTRY_ENTRY_COUNT: _int(history.get(FLAKY_TEST_REGISTRY_ENTRY_COUNT)),
        FLAKY_TEST_REGISTRY_OBSERVATION_STATUS: _string(
            history.get(FLAKY_TEST_REGISTRY_OBSERVATION_STATUS) or NOT_COLLECTED
        ),
        FLAKY_TEST_REGISTRY_OBSERVATIONS_COLLECTED: _bool(
            history.get(FLAKY_TEST_REGISTRY_OBSERVATIONS_COLLECTED)
        ),
        FLAKY_TEST_REGISTRY_PRODUCER_VETTED: _bool(
            history.get(FLAKY_TEST_REGISTRY_PRODUCER_VETTED)
        ),
        FLAKY_TEST_REGISTRY_RAW_TEST_IDENTITY_EMITTED: _bool(
            history.get(FLAKY_TEST_REGISTRY_RAW_TEST_IDENTITY_EMITTED)
        ),
        FLAKY_TEST_REGISTRY_CURRENT_PR_DECISION_INPUT: _bool(
            history.get(FLAKY_TEST_REGISTRY_CURRENT_PR_DECISION_INPUT)
        ),
        PROOF_COMMANDS_EXECUTED_BY_READER: _bool(boundary.get(PROOF_COMMANDS_EXECUTED_BY_READER)),
        "controlled_validation_authorizes_current_action": _bool(
            boundary.get("controlled_validation_authorizes_current_action")
        ),
        "flaky_test_registry_is_advisory_only": _bool(
            boundary.get("flaky_test_registry_is_advisory_only")
        ),
        "automation_allowed": _bool(boundary.get("automation_allowed")),
        "merge_authorized": _bool(boundary.get("merge_authorized")),
        "semantic_equivalence_proven": _bool(boundary.get("semantic_equivalence_proven")),
    }


def build_runtime_proof_artifacts(
    *,
    isolated_proof: Mapping[str, Any] | None = None,
    live_benchmark_report: Mapping[str, Any] | None = None,
    repo_memory_profile: Mapping[str, Any] | None = None,
    protected_verifier_result: Mapping[str, Any] | None = None,
    trusted_history_evidence: Mapping[str, Any] | None = None,
    trusted_diagnostic_signal_snapshot_history: Mapping[str, Any] | None = None,
) -> JsonObject:
    isolated = _isolated_proof_summary(isolated_proof or {})
    live_benchmark = _live_benchmark_summary(live_benchmark_report or {})
    repo_memory = _repo_memory_summary(repo_memory_profile or {})
    protected_verifier = _protected_verifier_summary(protected_verifier_result or {})
    trusted_history = _trusted_history_summary(trusted_history_evidence or {})
    trusted_signal_history = _trusted_diagnostic_signal_snapshot_history_summary(
        trusted_diagnostic_signal_snapshot_history or {}
    )

    collected_components = [
        name
        for name, component in (
            ("isolated_proof", isolated),
            ("live_benchmark", live_benchmark),
            ("repo_memory", repo_memory),
            ("protected_verifier", protected_verifier),
            (TRUSTED_HISTORY, trusted_history),
            (TRUSTED_DIAGNOSTIC_SIGNAL_SNAPSHOT_HISTORY, trusted_signal_history),
        )
        if component["collection_status"] == COLLECTED
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "status": COLLECTED if collected_components else NOT_COLLECTED,
        "collected_components": collected_components,
        "isolated_proof": isolated,
        "live_benchmark": live_benchmark,
        "repo_memory": repo_memory,
        "protected_verifier": protected_verifier,
        TRUSTED_HISTORY: trusted_history,
        TRUSTED_DIAGNOSTIC_SIGNAL_SNAPSHOT_HISTORY: trusted_signal_history,
        "decision_boundary": {
            "reporting_only": True,
            "proof_commands_executed_by_renderer": False,
            "automation_allowed": False,
            "patch_application_allowed": False,
            "security_dismissal_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }


def render_markdown(summary: Mapping[str, Any]) -> str:
    isolated = _as_dict(summary.get("isolated_proof"))
    benchmark = _as_dict(summary.get("live_benchmark"))
    memory = _as_dict(summary.get("repo_memory"))
    protected_verifier = _as_dict(summary.get("protected_verifier"))
    trusted_history = _as_dict(summary.get(TRUSTED_HISTORY))
    trusted_signal_history = _as_dict(summary.get(TRUSTED_DIAGNOSTIC_SIGNAL_SNAPSHOT_HISTORY))
    boundary = _as_dict(summary.get("decision_boundary"))

    lines = [
        "# PR Quality runtime proof artifacts",
        "",
        f"- Status: `{_string(summary.get('status'))}`",
        "",
        "## Isolated runtime proof",
        "",
        f"- Collection status: `{_string(isolated.get('collection_status'))}`",
        f"- Status: `{_string(isolated.get('status'))}`",
    ]

    if isolated.get("collection_status") == COLLECTED:
        lines.extend(
            [
                (
                    "- Git inventory verified: "
                    f"`{str(_bool(isolated.get('git_inventory_verified'))).lower()}`"
                ),
                (
                    "- Runtime guard checked: "
                    f"`{str(_bool(isolated.get('runtime_guard_checked'))).lower()}`"
                ),
                (
                    "- Runtime guard passed: "
                    f"`{str(_bool(isolated.get('runtime_guard_passed'))).lower()}`"
                ),
                (
                    "- Runtime guard violations: "
                    f"`{_int(isolated.get('runtime_guard_violation_count'))}`"
                ),
                (
                    "- Network boundary status: "
                    f"`{_string(isolated.get('network_boundary_status'))}`"
                ),
                (
                    "- Network isolation enforced: "
                    f"`{str(_bool(isolated.get('network_isolation_enforced'))).lower()}`"
                ),
                f"- Profiles executed: `{_int(isolated.get('profiles_executed'))}`",
                f"- Profiles blocked: `{_int(isolated.get('profiles_blocked'))}`",
                (
                    "- Profile visibility status: "
                    f"`{_string(isolated.get('profile_visibility_status') or NOT_COLLECTED)}`"
                ),
                (
                    "- Profile review-first results: "
                    f"`{_int(isolated.get('profile_review_first_count'))}`"
                ),
                (
                    "- Profile authority expansion detected: "
                    f"`{str(_bool(isolated.get('profile_authority_expansion_detected'))).lower()}`"
                ),
            ]
        )

        profile_results = [
            _as_dict(item) for item in _as_list(isolated.get("profile_results")) if _as_dict(item)
        ]
        if profile_results:
            lines.append("- Profile results:")
            for profile in profile_results:
                claim_value = profile.get("inventory_claim_match")
                claim_status = (
                    "not_checked" if claim_value is None else str(_bool(claim_value)).lower()
                )
                lines.append(
                    f"  - `{_string(profile.get('profile_id') or 'unknown')}`: "
                    f"command=`{_string(profile.get('command') or 'unknown')}`, "
                    f"status=`{_string(profile.get('status') or 'unknown')}`, "
                    f"exit_code=`{_int(profile.get('exit_code'))}`, "
                    f"timed_out=`{str(_bool(profile.get('timed_out'))).lower()}`, "
                    "workspace_mutated=`"
                    f"{str(_bool(profile.get('workspace_mutated'))).lower()}`, "
                    f"runtime_guard=`{_string(profile.get('runtime_guard_status') or 'unknown')}`, "
                    f"inventory_claim_match=`{claim_status}`, "
                    "git_inventory_verified=`"
                    f"{str(_bool(profile.get('git_inventory_verified'))).lower()}`, "
                    f"network_boundary=`{_string(profile.get('network_boundary_status') or 'unknown')}`, "
                    "network_wrapped=`"
                    f"{str(_bool(profile.get('network_backend_command_wrapped'))).lower()}`, "
                    f"review_first=`{str(_bool(profile.get('review_first'))).lower()}`"
                )
        else:
            lines.append("- Profile results: none")

    lines.extend(
        [
            "",
            "## Live benchmark evidence",
            "",
            f"- Collection status: `{_string(benchmark.get('collection_status'))}`",
            f"- Status: `{_string(benchmark.get('status'))}`",
        ]
    )
    if benchmark.get("collection_status") == COLLECTED:
        lines.extend(
            [
                f"- Report mode: `{_string(benchmark.get('report_mode'))}`",
                f"- Scenarios: `{_int(benchmark.get('scenario_count'))}`",
                f"- Passed: `{_int(benchmark.get('passed_count'))}`",
                (
                    "- Git inventory verified scenarios: "
                    f"`{_int(benchmark.get('git_inventory_verified_count'))}`"
                ),
                (
                    "- Expected failed-evidence scenarios: "
                    f"`{_int(benchmark.get('expected_failed_evidence_count'))}`"
                ),
                (
                    "- Network boundary blocked scenarios: "
                    f"`{_int(benchmark.get('network_boundary_blocked_count'))}`"
                ),
                (
                    "- Anti-cheat rejection scenarios: "
                    f"`{_int(benchmark.get('anti_cheat_rejection_count'))}`"
                ),
                (
                    "- Network isolation enforced scenarios: "
                    f"`{_int(benchmark.get('network_isolation_enforced_count'))}`"
                ),
                (
                    "- Boundary preserved: "
                    f"`{str(_bool(benchmark.get('boundary_preserved'))).lower()}`"
                ),
                f"- Runtime proof contract collection: `{_string(benchmark.get(BENCHMARK_RUNTIME_CONTRACT_COLLECTION_STATUS))}`",
                f"- Runtime proof contract status: `{_string(benchmark.get(BENCHMARK_RUNTIME_CONTRACT_STATUS))}`",
                (
                    "- Runtime proof contract scenarios: "
                    f"`{_int(benchmark.get(BENCHMARK_RUNTIME_CONTRACT_SCENARIO_COUNT))}`"
                ),
                (
                    "- Runtime proof contract records: "
                    f"`{_int(benchmark.get(BENCHMARK_RUNTIME_CONTRACT_RECORD_COUNT))}`"
                ),
                (
                    "- Runtime proof contract security-relevant records: "
                    f"`{_int(benchmark.get(BENCHMARK_RUNTIME_CONTRACT_SECURITY_RELEVANCE_COUNT))}`"
                ),
                (
                    "- Runtime proof contract authority-preserved records: "
                    f"`{_int(benchmark.get(BENCHMARK_RUNTIME_CONTRACT_AUTHORITY_BOUNDARY_PRESERVED_COUNT))}`"
                ),
                (
                    "- Runtime proof contract expanded authority fields: "
                    f"`{', '.join(_string_list(benchmark.get(BENCHMARK_RUNTIME_CONTRACT_EXPANDED_AUTHORITY_FIELDS))) or 'none'}`"
                ),
                (
                    "- Runtime proof contract patch application allowed: "
                    f"`{str(_bool(benchmark.get(BENCHMARK_RUNTIME_CONTRACT_PATCH_APPLICATION_ALLOWED))).lower()}`"
                ),
                (
                    "- Runtime proof contract security dismissal allowed: "
                    f"`{str(_bool(benchmark.get(BENCHMARK_RUNTIME_CONTRACT_SECURITY_DISMISSAL_ALLOWED))).lower()}`"
                ),
                (
                    "- Runtime proof contract merge authorized: "
                    f"`{str(_bool(benchmark.get(BENCHMARK_RUNTIME_CONTRACT_MERGE_AUTHORIZED))).lower()}`"
                ),
                (
                    "- Runtime proof contract semantic equivalence claim: "
                    f"`{str(_bool(benchmark.get(BENCHMARK_RUNTIME_CONTRACT_SEMANTIC_EQUIVALENCE_CLAIM))).lower()}`"
                ),
                (
                    "- Replay manifest present: "
                    f"`{str(_bool(benchmark.get(REPLAY_MANIFEST_PRESENT))).lower()}`"
                ),
                (
                    "- Replay manifest scenarios: "
                    f"`{_int(benchmark.get(REPLAY_MANIFEST_SCENARIO_COUNT))}`"
                ),
                (
                    "- Replay manifest reporting only: "
                    f"`{str(_bool(benchmark.get(REPLAY_MANIFEST_REPORTING_ONLY))).lower()}`"
                ),
                (
                    "- Replay manifest automation allowed: "
                    f"`{str(_bool(benchmark.get(REPLAY_MANIFEST_AUTOMATION_ALLOWED))).lower()}`"
                ),
                (
                    "- Replay manifest merge authorized: "
                    f"`{str(_bool(benchmark.get(REPLAY_MANIFEST_MERGE_AUTHORIZED))).lower()}`"
                ),
                (
                    "- Replay manifest semantic equivalence proven: "
                    f"`{str(_bool(benchmark.get(REPLAY_MANIFEST_SEMANTIC_EQUIVALENCE_PROVEN))).lower()}`"
                ),
            ]
        )

    lines.extend(
        [
            "",
            "## RepoMemory evidence",
            "",
            f"- Collection status: `{_string(memory.get('collection_status'))}`",
            f"- Status: `{_string(memory.get('status'))}`",
        ]
    )
    if memory.get("collection_status") == COLLECTED:
        lines.extend(
            [
                (
                    "- Live contract proven: "
                    f"`{str(_bool(memory.get('live_contract_proven'))).lower()}`"
                ),
                (f"- Known safe candidates: `{_int(memory.get('known_safe_candidate_count'))}`"),
                (f"- Live safe candidates: `{_int(memory.get('live_safe_candidate_count'))}`"),
                (
                    "- Git inventory verified scenarios: "
                    f"`{_int(memory.get('git_verified_scenario_count'))}`"
                ),
                (
                    "- Anti-cheat rejection scenarios: "
                    f"`{_int(memory.get('anti_cheat_rejection_scenario_count'))}`"
                ),
                (f"- RepoMemory SafetyGate status: `{_string(memory.get('safety_gate_status'))}`"),
                (
                    "- RepoMemory SafetyGate records: "
                    f"`{_int(memory.get('safety_gate_record_count'))}`"
                ),
                (
                    "- RepoMemory SafetyGate safe-fix allowed records: "
                    f"`{_int(memory.get('safety_gate_safe_fix_allowed_count'))}`"
                ),
                (
                    "- RepoMemory SafetyGate review-first records: "
                    f"`{_int(memory.get('safety_gate_review_first_count'))}`"
                ),
                (
                    "- RepoMemory SafetyGate automation allowed: "
                    f"`{str(_bool(memory.get('safety_gate_automation_allowed'))).lower()}`"
                ),
                (
                    "- RepoMemory SafetyGate merge authorized: "
                    f"`{str(_bool(memory.get('safety_gate_merge_authorized'))).lower()}`"
                ),
                (
                    "- RepoMemory SafetyGate semantic equivalence proven: "
                    f"`{str(_bool(memory.get('safety_gate_semantic_equivalence_proven'))).lower()}`"
                ),
                (
                    "- RepoMemory trajectory authority status: "
                    f"`{_string(memory.get('trajectory_authority_status'))}`"
                ),
                (
                    "- RepoMemory trajectory authority records: "
                    f"`{_int(memory.get('trajectory_authority_record_count'))}`"
                ),
                (
                    "- RepoMemory trajectory authority review-first records: "
                    f"`{_int(memory.get('trajectory_authority_review_first_count'))}`"
                ),
                (
                    "- RepoMemory trajectory authority auto-fix evidence records: "
                    f"`{_int(memory.get('trajectory_authority_auto_fix_allowed_count'))}`"
                ),
                (
                    "- RepoMemory trajectory authority reporting-only records: "
                    f"`{_int(memory.get('trajectory_authority_reporting_only_count'))}`"
                ),
                (
                    "- RepoMemory trajectory authority patch application allowed: "
                    f"`{str(_bool(memory.get('trajectory_authority_patch_application_allowed'))).lower()}`"
                ),
                (
                    "- RepoMemory trajectory authority security dismissal allowed: "
                    f"`{str(_bool(memory.get('trajectory_authority_security_dismissal_allowed'))).lower()}`"
                ),
                (
                    "- RepoMemory trajectory authority merge authorized: "
                    f"`{str(_bool(memory.get('trajectory_authority_merge_authorized'))).lower()}`"
                ),
                (
                    "- RepoMemory trajectory authority semantic equivalence proven: "
                    f"`{str(_bool(memory.get('trajectory_authority_semantic_equivalence_proven'))).lower()}`"
                ),
            ]
        )

    lines.extend(
        [
            "",
            "## ProtectedVerifier RepoMemory contract evidence",
            "",
            f"- Collection status: `{_string(protected_verifier.get('collection_status'))}`",
            f"- Status: `{_string(protected_verifier.get('status'))}`",
        ]
    )
    if protected_verifier.get("collection_status") == COLLECTED:
        lines.extend(
            [
                f"- Review first: `{str(_bool(protected_verifier.get('review_first'))).lower()}`",
                f"- Contract status: `{_string(protected_verifier.get('contract_status'))}`",
                f"- Contract records: `{_int(protected_verifier.get('contract_record_count'))}`",
                "- Contract security-relevant records: "
                f"`{_int(protected_verifier.get('contract_security_relevance_count'))}`",
                "- Contract authority boundary preserved records: "
                f"`{_int(protected_verifier.get('contract_authority_boundary_preserved_count'))}`",
                "- Contract patch application allowed: "
                f"`{str(_bool(protected_verifier.get('contract_patch_application_allowed'))).lower()}`",
                "- Contract security dismissal allowed: "
                f"`{str(_bool(protected_verifier.get('contract_security_dismissal_allowed'))).lower()}`",
                "- Contract merge authorized: "
                f"`{str(_bool(protected_verifier.get('contract_merge_authorized'))).lower()}`",
                "- Contract semantic equivalence claim: "
                f"`{str(_bool(protected_verifier.get('contract_semantic_equivalence_claim'))).lower()}`",
                "- Benchmark replay contract collection: "
                f"`{_string(protected_verifier.get(PROTECTED_VERIFIER_BENCHMARK_CONTRACT_COLLECTION_STATUS))}`",
                "- Benchmark replay contract status: "
                f"`{_string(protected_verifier.get(PROTECTED_VERIFIER_BENCHMARK_CONTRACT_STATUS))}`",
                "- Benchmark replay contract scenarios: "
                f"`{_int(protected_verifier.get(PROTECTED_VERIFIER_BENCHMARK_CONTRACT_SCENARIO_COUNT))}`",
                "- Benchmark replay contract records: "
                f"`{_int(protected_verifier.get(PROTECTED_VERIFIER_BENCHMARK_CONTRACT_RECORD_COUNT))}`",
                "- Benchmark replay contract security-relevant records: "
                f"`{_int(protected_verifier.get(PROTECTED_VERIFIER_BENCHMARK_CONTRACT_SECURITY_RELEVANCE_COUNT))}`",
                "- Benchmark replay contract authority-preserved records: "
                f"`{_int(protected_verifier.get(PROTECTED_VERIFIER_BENCHMARK_CONTRACT_AUTHORITY_BOUNDARY_PRESERVED_COUNT))}`",
                "- Benchmark replay contract expanded authority fields: "
                f"`{', '.join(_string_list(protected_verifier.get(PROTECTED_VERIFIER_BENCHMARK_CONTRACT_EXPANDED_AUTHORITY_FIELDS))) or 'none'}`",
                "- Benchmark replay contract patch application allowed: "
                f"`{str(_bool(protected_verifier.get(PROTECTED_VERIFIER_BENCHMARK_CONTRACT_PATCH_APPLICATION_ALLOWED))).lower()}`",
                "- Benchmark replay contract security dismissal allowed: "
                f"`{str(_bool(protected_verifier.get(PROTECTED_VERIFIER_BENCHMARK_CONTRACT_SECURITY_DISMISSAL_ALLOWED))).lower()}`",
                "- Benchmark replay contract merge authorized: "
                f"`{str(_bool(protected_verifier.get(PROTECTED_VERIFIER_BENCHMARK_CONTRACT_MERGE_AUTHORIZED))).lower()}`",
                "- Benchmark replay contract semantic equivalence claim: "
                f"`{str(_bool(protected_verifier.get(PROTECTED_VERIFIER_BENCHMARK_CONTRACT_SEMANTIC_EQUIVALENCE_CLAIM))).lower()}`",
                "- ProtectedVerifier automation allowed: "
                f"`{str(_bool(protected_verifier.get('automation_allowed'))).lower()}`",
                "- ProtectedVerifier merge authorized: "
                f"`{str(_bool(protected_verifier.get('merge_authorized'))).lower()}`",
                "- ProtectedVerifier semantic equivalence proven: "
                f"`{str(_bool(protected_verifier.get('semantic_equivalence_proven'))).lower()}`",
            ]
        )

    lines.extend(
        [
            "",
            "## Trusted accepted-main RepoMemory history",
            "",
            (f"- Collection status: `{_string(trusted_history.get('collection_status'))}`"),
            f"- Status: `{_string(trusted_history.get('status'))}`",
        ]
    )
    if trusted_history.get("collection_status") == COLLECTED:
        lines.extend(
            [
                (f"- Source workflow: `{_string(trusted_history.get('source_workflow'))}`"),
                (f"- Source run id: `{_string(trusted_history.get('source_run_id'))}`"),
                (
                    "- Latest accepted main head: "
                    f"`{_string(trusted_history.get('latest_accepted_main_head'))}`"
                ),
                (
                    "- Base ancestry verified: "
                    f"`{str(_bool(trusted_history.get(BASE_ANCESTRY_VERIFIED))).lower()}`"
                ),
                f"- Records: `{_int(trusted_history.get('record_count'))}`",
                (
                    "- Live-contract-proven records: "
                    f"`{_int(trusted_history.get(LIVE_PROVEN_RECORD_COUNT))}`"
                ),
                (
                    "- Prior history is read-only input: "
                    f"`{str(_bool(trusted_history.get(PRIOR_HISTORY_READ_ONLY_INPUT))).lower()}`"
                ),
                (
                    "- Controlled validation records: "
                    f"`{_int(trusted_history.get(CONTROLLED_VALIDATION_RECORD_COUNT))}`"
                ),
                (
                    "- Controlled validation scenario total: "
                    f"`{_int(trusted_history.get(CONTROLLED_VALIDATION_SCENARIO_COUNT))}`"
                ),
                (
                    "- Controlled structurally verified scenario total: "
                    f"`{_int(trusted_history.get(CONTROLLED_STRUCTURALLY_VERIFIED_COUNT))}`"
                ),
                (
                    "- Controlled review-first scenario total: "
                    f"`{_int(trusted_history.get(CONTROLLED_REVIEW_FIRST_COUNT))}`"
                ),
                (
                    "- Latest controlled validation status: "
                    f"`{_string(trusted_history.get('latest_controlled_validation_status'))}`"
                ),
                (
                    "- Controlled validation reporting only: "
                    f"`{str(_bool(trusted_history.get('controlled_validation_reporting_only'))).lower()}`"
                ),
                (
                    "- Controlled validation authorizes current action: "
                    f"`{str(_bool(trusted_history.get('controlled_validation_authorizes_current_action'))).lower()}`"
                ),
                (
                    "- Producer-vetted registry collection status: "
                    f"`{_string(trusted_history.get(FLAKY_TEST_REGISTRY_COLLECTION_STATUS))}`"
                ),
                (
                    "- Producer-vetted registry status: "
                    f"`{_string(trusted_history.get(FLAKY_TEST_REGISTRY_STATUS))}`"
                ),
                (
                    "- Producer-vetted registry aggregate entries: "
                    f"`{_int(trusted_history.get(FLAKY_TEST_REGISTRY_ENTRY_COUNT))}`"
                ),
                (
                    "- Producer-vetted registry observation status: "
                    f"`{_string(trusted_history.get(FLAKY_TEST_REGISTRY_OBSERVATION_STATUS))}`"
                ),
                (
                    "- Producer-vetted registry observations collected: "
                    f"`{str(_bool(trusted_history.get(FLAKY_TEST_REGISTRY_OBSERVATIONS_COLLECTED))).lower()}`"
                ),
                (
                    "- Producer-vetted registry producer vetted: "
                    f"`{str(_bool(trusted_history.get(FLAKY_TEST_REGISTRY_PRODUCER_VETTED))).lower()}`"
                ),
                (
                    "- Producer-vetted registry raw test identity emitted: "
                    f"`{str(_bool(trusted_history.get(FLAKY_TEST_REGISTRY_RAW_TEST_IDENTITY_EMITTED))).lower()}`"
                ),
                (
                    "- Producer-vetted registry current PR decision input: "
                    f"`{str(_bool(trusted_history.get(FLAKY_TEST_REGISTRY_CURRENT_PR_DECISION_INPUT))).lower()}`"
                ),
                (
                    "- Proof commands executed by trusted-history reader: "
                    f"`{str(_bool(trusted_history.get(PROOF_COMMANDS_EXECUTED_BY_READER))).lower()}`"
                ),
                (
                    "- Automation allowed by trusted history: "
                    f"`{str(_bool(trusted_history.get('automation_allowed'))).lower()}`"
                ),
                (
                    "- Merge authorized by trusted history: "
                    f"`{str(_bool(trusted_history.get('merge_authorized'))).lower()}`"
                ),
                (
                    "- Semantic equivalence proven by trusted history: "
                    f"`{str(_bool(trusted_history.get('semantic_equivalence_proven'))).lower()}`"
                ),
            ]
        )

    lines.extend(
        [
            "",
            "## Trusted diagnostic signal snapshot history",
            "",
            (f"- Collection status: `{_string(trusted_signal_history.get('collection_status'))}`"),
            f"- Status: `{_string(trusted_signal_history.get('status'))}`",
        ]
    )
    if trusted_signal_history.get("collection_status") == COLLECTED:
        lines.extend(
            [
                (f"- Source workflow: `{_string(trusted_signal_history.get('source_workflow'))}`"),
                (
                    "- Latest accepted main head: "
                    f"`{_string(trusted_signal_history.get('latest_accepted_main_head'))}`"
                ),
                (
                    "- Base ancestry verified: "
                    f"`{str(_bool(trusted_signal_history.get(BASE_ANCESTRY_VERIFIED))).lower()}`"
                ),
                f"- Records: `{_int(trusted_signal_history.get('record_count'))}`",
                (
                    "- Quiet-green advisory baseline records: "
                    f"`{_int(trusted_signal_history.get('quiet_green_advisory_baseline_record_count'))}`"
                ),
                (
                    "- Review-signal records: "
                    f"`{_int(trusted_signal_history.get('review_signal_record_count'))}`"
                ),
                (
                    "- Integration-proof-signal records: "
                    f"`{_int(trusted_signal_history.get('integration_proof_signal_record_count'))}`"
                ),
                (
                    "- Latest retained snapshot status: "
                    f"`{_string(trusted_signal_history.get('latest_snapshot_status'))}`"
                ),
                (
                    "- Advisor false-positive rate status: "
                    f"`{_string(trusted_signal_history.get('advisor_false_positive_rate_status'))}`"
                ),
                (
                    "- Prior history is read-only input: "
                    f"`{str(_bool(trusted_signal_history.get(PRIOR_HISTORY_READ_ONLY_INPUT))).lower()}`"
                ),
                (
                    "- Current PR decision input: "
                    f"`{str(_bool(trusted_signal_history.get('current_pr_decision_input'))).lower()}`"
                ),
                (
                    "- Feeds RepoMemory: "
                    f"`{str(_bool(trusted_signal_history.get('feeds_repo_memory'))).lower()}`"
                ),
                (
                    "- Proof commands executed: "
                    f"`{str(_bool(trusted_signal_history.get('proof_commands_executed'))).lower()}`"
                ),
                (
                    "- Patch application allowed: "
                    f"`{str(_bool(trusted_signal_history.get('patch_application_allowed'))).lower()}`"
                ),
                (
                    "- Automation allowed by trusted diagnostic signal history: "
                    f"`{str(_bool(trusted_signal_history.get('automation_allowed'))).lower()}`"
                ),
                (
                    "- Merge authorized by trusted diagnostic signal history: "
                    f"`{str(_bool(trusted_signal_history.get('merge_authorized'))).lower()}`"
                ),
                (
                    "- Semantic equivalence proven by trusted diagnostic signal history: "
                    f"`{str(_bool(trusted_signal_history.get('semantic_equivalence_proven'))).lower()}`"
                ),
                (
                    "- Historical snapshot authorizes current action: "
                    f"`{str(_bool(trusted_signal_history.get('historical_snapshot_authorizes_current_action'))).lower()}`"
                ),
            ]
        )

    lines.extend(
        [
            "",
            "## Boundary",
            "",
            (
                "- Proof commands executed by renderer: "
                f"`{str(_bool(boundary.get('proof_commands_executed_by_renderer'))).lower()}`"
            ),
            (f"- Automation allowed: `{str(_bool(boundary.get('automation_allowed'))).lower()}`"),
            (
                "- Patch application allowed: "
                f"`{str(_bool(boundary.get('patch_application_allowed'))).lower()}`"
            ),
            (
                "- Security dismissal allowed: "
                f"`{str(_bool(boundary.get('security_dismissal_allowed'))).lower()}`"
            ),
            (f"- Merge authorized: `{str(_bool(boundary.get('merge_authorized'))).lower()}`"),
            (
                "- Semantic equivalence proven: "
                f"`{str(_bool(boundary.get('semantic_equivalence_proven'))).lower()}`"
            ),
            "",
        ]
    )
    return "\n".join(lines)


def write_summary(summary: Mapping[str, Any], *, out_dir: Path) -> dict[str, str]:
    json_path = out_dir / SUMMARY_JSON
    markdown_path = out_dir / SUMMARY_MD
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(summary), encoding="utf-8")
    return {
        "runtime_proof_artifacts_json": json_path.as_posix(),
        "runtime_proof_artifacts_markdown": markdown_path.as_posix(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.pr_quality_runtime_proof_artifacts")
    parser.add_argument("--isolated-proof", type=Path)
    parser.add_argument("--live-benchmark-report", type=Path)
    parser.add_argument("--repo-memory-profile", type=Path)
    parser.add_argument("--protected-verifier-result", type=Path)
    parser.add_argument("--trusted-history-evidence", type=Path)
    parser.add_argument("--trusted-diagnostic-signal-snapshot-history", type=Path)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = build_runtime_proof_artifacts(
        isolated_proof=_read_json(args.isolated_proof),
        live_benchmark_report=_read_json(args.live_benchmark_report),
        repo_memory_profile=_read_json(args.repo_memory_profile),
        protected_verifier_result=_read_json(args.protected_verifier_result),
        trusted_history_evidence=_read_json(args.trusted_history_evidence),
        trusted_diagnostic_signal_snapshot_history=_read_json(
            args.trusted_diagnostic_signal_snapshot_history
        ),
    )
    write_summary(summary, out_dir=args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
