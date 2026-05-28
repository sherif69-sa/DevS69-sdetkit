from __future__ import annotations

import argparse
import json
import tempfile
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sdetkit.diagnostic_job import build_diagnostic_job, run_diagnostic_worker
from sdetkit.diagnostic_worker_trajectory import build_worker_trajectory_records
from sdetkit.git_inventory_collector import STAGED_WORKTREE
from sdetkit.isolated_proof_runner import INVENTORY_CLAIM_MATCH, run_isolated_proof
from sdetkit.network_boundary import NETWORK_ISOLATION_ENFORCED, NETWORK_ISOLATION_REQUIRED
from sdetkit.patch_scorer import score_patch
from sdetkit.protected_verifier import verify_candidate

SCHEMA_VERSION = "sdetkit.replayable_benchmark_harness.v1"
ISOLATED_EVIDENCE_SCHEMA_VERSION = "sdetkit.replayable_benchmark_harness.isolated_evidence.v3"
DEFAULT_OUT_DIR = Path("build") / "replayable-benchmark-harness"
REPORT_JSON = "benchmark-report.json"
REPORT_MD = "benchmark-report.md"

INVENTORY_CLAIM_MISMATCH_FAIL = "_".join(("inventory", "claim", "mismatch", "fail"))
PROOF_MUTATION_FAIL = "_".join(("proof", "mutation", "fail"))
NETWORK_BOUNDARY_REQUIRED_FAIL = "_".join(("network", "boundary", "required", "fail"))
NETWORK_BOUNDARY_BLOCKED_COUNT = "_".join(("network", "boundary", "blocked", "count"))
UNCLAIMED_WRITE_FAIL = "_".join(("unclaimed", "write", "fail"))
EVIDENCE_SHADOW_FAIL = "_".join(("evidence", "shadow", "fail"))
ANTI_CHEAT_REJECTION_COUNT = "_".join(("anti", "cheat", "rejection", "count"))
LIVE_EVIDENCE_SOURCE = "_".join(("git", "grounded", "isolated", "proof"))
LIVE_EXECUTION_MODEL = "_".join(("git", "derived", "isolated", "proof", "evaluation"))
VERIFICATION_EVIDENCE_SOURCE = "_".join(("verification", "evidence", "source"))
DIAGNOSTIC_WORKER_REPORT_SCHEMA_VERSION = (
    "sdetkit.replayable_benchmark_harness.diagnostic_worker.v1"
)
DIAGNOSTIC_WORKER_REPORT_MODE = "diagnostic_worker_runtime_guard_fixture"
RUNTIME_GUARD_WORKER_ORACLE_PASS = "runtime_guard_worker_oracle_pass"
RUNTIME_GUARD_WORKER_NOP_PASS = "runtime_guard_worker_nop_pass"
RUNTIME_GUARD_WORKER_AUTHORITY_FAIL = "runtime_guard_worker_authority_fail"
DIAGNOSTIC_WORKER_SCENARIO_TYPES = {
    RUNTIME_GUARD_WORKER_ORACLE_PASS,
    RUNTIME_GUARD_WORKER_NOP_PASS,
    RUNTIME_GUARD_WORKER_AUTHORITY_FAIL,
}
DIAGNOSTIC_WORKER_REQUIRED_SCENARIO_TYPES = (
    RUNTIME_GUARD_WORKER_ORACLE_PASS,
    RUNTIME_GUARD_WORKER_NOP_PASS,
    RUNTIME_GUARD_WORKER_AUTHORITY_FAIL,
)
SECURITY_FRESHNESS_REPORT_SCHEMA_VERSION = (
    "sdetkit.replayable_benchmark_harness.security_freshness.v1"
)
SECURITY_FRESHNESS_REPORT_MODE = "_".join(
    ("diagnostic", "worker", "security", "freshness", "fixture")
)
SECURITY_FRESHNESS_STALE_RUNTIME_PASS = "_".join(
    ("security", "freshness", "stale", "runtime", "pass")
)
SECURITY_FRESHNESS_CURRENT_PRIMARY_PASS = "_".join(
    ("security", "freshness", "current", "primary", "pass")
)
SECURITY_FRESHNESS_AUTHORITY_FAIL = "_".join(("security", "freshness", "authority", "fail"))
SECURITY_FRESHNESS_SCENARIO_TYPES = {
    SECURITY_FRESHNESS_STALE_RUNTIME_PASS,
    SECURITY_FRESHNESS_CURRENT_PRIMARY_PASS,
    SECURITY_FRESHNESS_AUTHORITY_FAIL,
}
SECURITY_FRESHNESS_REQUIRED_SCENARIO_TYPES = (
    SECURITY_FRESHNESS_STALE_RUNTIME_PASS,
    SECURITY_FRESHNESS_CURRENT_PRIMARY_PASS,
    SECURITY_FRESHNESS_AUTHORITY_FAIL,
)

SCENARIO_TYPES = {
    "nop_fail",
    "oracle_pass",
    "unsafe_patch_fail",
    INVENTORY_CLAIM_MISMATCH_FAIL,
    PROOF_MUTATION_FAIL,
    NETWORK_BOUNDARY_REQUIRED_FAIL,
    UNCLAIMED_WRITE_FAIL,
    EVIDENCE_SHADOW_FAIL,
}
REQUIRED_SCENARIO_TYPES = (
    "nop_fail",
    "oracle_pass",
    "unsafe_patch_fail",
)
ISOLATED_EVIDENCE_REQUIRED_TYPES = (
    "oracle_pass",
    INVENTORY_CLAIM_MISMATCH_FAIL,
    PROOF_MUTATION_FAIL,
    NETWORK_BOUNDARY_REQUIRED_FAIL,
    UNCLAIMED_WRITE_FAIL,
    EVIDENCE_SHADOW_FAIL,
)

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


def _int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _string_list(value: Any) -> list[str]:
    return sorted({_string(item) for item in _as_list(value) if _string(item)})


def _read_json_object(path: Path) -> JsonObject:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"expected JSON object in {path}"
        raise ValueError(msg)
    return payload


def load_scenarios(paths: list[Path]) -> list[JsonObject]:
    scenarios: list[JsonObject] = []
    identifiers: set[str] = set()

    for path in paths:
        scenario = _read_json_object(path)
        scenario_id = _string(scenario.get("scenario_id"))
        if not scenario_id:
            msg = f"scenario_id is required in {path}"
            raise ValueError(msg)
        if scenario_id in identifiers:
            msg = f"duplicate scenario_id: {scenario_id}"
            raise ValueError(msg)

        scenario_type = _string(scenario.get("scenario_type"))
        if scenario_type not in SCENARIO_TYPES:
            msg = f"unsupported scenario_type for {scenario_id}: {scenario_type}"
            raise ValueError(msg)

        identifiers.add(scenario_id)
        scenarios.append(scenario)

    return scenarios


def load_diagnostic_worker_scenarios(paths: list[Path]) -> list[JsonObject]:
    scenarios: list[JsonObject] = []
    identifiers: set[str] = set()

    for path in paths:
        scenario = _read_json_object(path)
        scenario_id = _string(scenario.get("scenario_id"))
        scenario_type = _string(scenario.get("scenario_type"))
        if not scenario_id:
            raise ValueError(f"scenario_id is required in {path}")
        if scenario_id in identifiers:
            raise ValueError(f"duplicate scenario_id: {scenario_id}")
        if scenario_type not in DIAGNOSTIC_WORKER_SCENARIO_TYPES:
            raise ValueError(
                f"unsupported diagnostic worker scenario_type for {scenario_id}: {scenario_type}"
            )
        if not _as_dict(scenario.get("runtime_proof_artifacts")):
            raise ValueError(f"runtime_proof_artifacts is required in {path}")
        identifiers.add(scenario_id)
        scenarios.append(scenario)

    return scenarios


def load_security_freshness_scenarios(paths: list[Path]) -> list[JsonObject]:
    scenarios: list[JsonObject] = []
    identifiers: set[str] = set()

    for path in paths:
        scenario = _read_json_object(path)
        scenario_id = _string(scenario.get("scenario_id"))
        scenario_type = _string(scenario.get("scenario_type"))
        if not scenario_id:
            raise ValueError(f"scenario_id is required in {path}")
        if scenario_id in identifiers:
            raise ValueError(f"duplicate scenario_id: {scenario_id}")
        if scenario_type not in SECURITY_FRESHNESS_SCENARIO_TYPES:
            raise ValueError(
                f"unsupported security freshness scenario_type for {scenario_id}: {scenario_type}"
            )
        if not _as_dict(scenario.get("security_review")):
            raise ValueError(f"security_review is required in {path}")
        if not _as_dict(scenario.get("runtime_proof_artifacts")):
            raise ValueError(f"runtime_proof_artifacts is required in {path}")
        identifiers.add(scenario_id)
        scenarios.append(scenario)

    return scenarios


def _decision_status(payload: Mapping[str, Any]) -> str:
    return _string(_as_dict(payload.get("decision")).get("status"))


def _check(
    *,
    name: str,
    passed: bool,
    expected: Any,
    actual: Any,
) -> JsonObject:
    return {
        "name": name,
        "passed": passed,
        "expected": expected,
        "actual": actual,
    }


def evaluate_scenario(
    scenario: Mapping[str, Any],
    *,
    verification_evidence_override: Mapping[str, Any] | None = None,
) -> JsonObject:
    scenario_id = _string(scenario.get("scenario_id"))
    scenario_type = _string(scenario.get("scenario_type"))
    if not scenario_id:
        raise ValueError("scenario_id is required")
    if scenario_type not in SCENARIO_TYPES:
        msg = f"unsupported scenario_type for {scenario_id}: {scenario_type}"
        raise ValueError(msg)

    remediation_plan = _as_dict(scenario.get("remediation_plan"))
    proposed_patch = _as_dict(scenario.get("proposed_patch"))
    pattern_insights = _as_dict(scenario.get("pattern_insights"))
    declared_verification_evidence = _as_dict(scenario.get("verification_evidence"))
    verification_evidence = (
        dict(verification_evidence_override)
        if verification_evidence_override is not None
        else declared_verification_evidence
    )
    evidence_source = (
        LIVE_EVIDENCE_SOURCE if verification_evidence_override is not None else "fixture_declared"
    )
    expected = _as_dict(scenario.get("expected"))

    if not remediation_plan or not proposed_patch or not verification_evidence:
        msg = (
            f"scenario {scenario_id} must provide remediation_plan, "
            "proposed_patch, and verification_evidence"
        )
        raise ValueError(msg)

    patch_score = score_patch(
        remediation_plan=remediation_plan,
        proposed_patch=proposed_patch,
        pattern_insights=pattern_insights,
        diagnosis_id=_string(scenario.get("diagnosis_id")),
        minimum_score=_int(scenario.get("minimum_score"), default=80),
    )
    verifier_result = verify_candidate(
        patch_score=patch_score,
        verification_evidence=verification_evidence,
    )

    patch_status = _decision_status(patch_score)
    verifier_status = _decision_status(verifier_result)
    scorer_decision = _as_dict(patch_score.get("decision"))
    verifier_decision = _as_dict(verifier_result.get("decision"))

    expected_patch_status = _string(expected.get("patch_score_status"))
    expected_verifier_status = _string(expected.get("verifier_status"))
    if not expected_patch_status or not expected_verifier_status:
        msg = f"scenario {scenario_id} must declare expected decision statuses"
        raise ValueError(msg)

    checks = [
        _check(
            name="patch_score_status",
            passed=patch_status == expected_patch_status,
            expected=expected_patch_status,
            actual=patch_status,
        ),
        _check(
            name="protected_verifier_status",
            passed=verifier_status == expected_verifier_status,
            expected=expected_verifier_status,
            actual=verifier_status,
        ),
        _check(
            name="patch_score_automation_boundary",
            passed=not _bool(scorer_decision.get("automation_allowed")),
            expected=False,
            actual=_bool(scorer_decision.get("automation_allowed")),
        ),
        _check(
            name="protected_verifier_automation_boundary",
            passed=not _bool(verifier_decision.get("automation_allowed")),
            expected=False,
            actual=_bool(verifier_decision.get("automation_allowed")),
        ),
        _check(
            name="protected_verifier_merge_boundary",
            passed=not _bool(verifier_decision.get("merge_authorized")),
            expected=False,
            actual=_bool(verifier_decision.get("merge_authorized")),
        ),
        _check(
            name="semantic_equivalence_boundary",
            passed=not _bool(verifier_decision.get("semantic_equivalence_proven")),
            expected=False,
            actual=_bool(verifier_decision.get("semantic_equivalence_proven")),
        ),
    ]

    if scenario_type == "oracle_pass":
        checks.extend(
            [
                _check(
                    name="oracle_patch_candidate",
                    passed=patch_status == "candidate_for_protected_verification",
                    expected="candidate_for_protected_verification",
                    actual=patch_status,
                ),
                _check(
                    name="oracle_structural_verification",
                    passed=verifier_status == "structurally_verified_candidate"
                    and _bool(verifier_decision.get("structural_verification_passed")),
                    expected=True,
                    actual=_bool(verifier_decision.get("structural_verification_passed")),
                ),
            ]
        )
    elif scenario_type in {"nop_fail", "unsafe_patch_fail"}:
        checks.extend(
            [
                _check(
                    name="unsafe_or_nop_patch_rejected",
                    passed=patch_status == "blocked_review_first",
                    expected="blocked_review_first",
                    actual=patch_status,
                ),
                _check(
                    name="unsafe_or_nop_verification_rejected",
                    passed=verifier_status == "blocked_review_first",
                    expected="blocked_review_first",
                    actual=verifier_status,
                ),
            ]
        )
    else:
        checks.extend(
            [
                _check(
                    name="live_failure_patch_remains_candidate",
                    passed=patch_status == "candidate_for_protected_verification",
                    expected="candidate_for_protected_verification",
                    actual=patch_status,
                ),
                _check(
                    name="live_failure_verification_rejected",
                    passed=verifier_status == "blocked_review_first",
                    expected="blocked_review_first",
                    actual=verifier_status,
                ),
            ]
        )

    passed = all(_bool(item.get("passed")) for item in checks)
    return {
        "scenario_id": scenario_id,
        "scenario_type": scenario_type,
        "description": _string(scenario.get("description")),
        "status": "passed" if passed else "failed",
        "passed": passed,
        "attempt_scored": True,
        "attempt_score": _int(patch_score.get("score")),
        VERIFICATION_EVIDENCE_SOURCE: evidence_source,
        "checks": checks,
        "patch_score": patch_score,
        "protected_verifier_result": verifier_result,
    }


def evaluate_isolated_evidence_scenario(
    scenario: Mapping[str, Any],
    *,
    repo_root: Path,
) -> JsonObject:
    scenario_type = _string(scenario.get("scenario_type"))
    if scenario_type not in ISOLATED_EVIDENCE_REQUIRED_TYPES:
        raise ValueError(f"unsupported isolated-evidence scenario type: {scenario_type}")

    runtime = _as_dict(scenario.get("isolated_proof"))
    profiles = _string_list(runtime.get("profiles"))
    if not profiles:
        raise ValueError("isolated_proof profiles are required")

    proposed_patch = _as_dict(scenario.get("proposed_patch"))
    claimed_files = _string_list(proposed_patch.get("changed_files"))
    expected_runtime = _as_dict(_as_dict(scenario.get("expected")).get("isolated_proof"))
    required_expectations = {
        "status",
        "git_inventory_verified",
        "inventory_claim_match",
    }
    if not required_expectations.issubset(expected_runtime):
        raise ValueError(
            "isolated proof expectations must include status, "
            "git_inventory_verified, and inventory_claim_match"
        )

    evidence = run_isolated_proof(
        repo_root=repo_root,
        changed_files=claimed_files,
        profile_ids=profiles,
        timeout_seconds=_int(runtime.get("timeout_seconds"), default=60),
        inventory_mode=_string(runtime.get("inventory_mode") or STAGED_WORKTREE),
        base_ref=_string(runtime.get("base_ref")),
        head_ref=_string(runtime.get("head_ref") or "HEAD"),
        require_network_isolation=_bool(runtime.get("require_network_isolation")),
    )
    result = evaluate_scenario(
        scenario,
        verification_evidence_override=evidence,
    )

    boundary = _as_dict(evidence.get("decision_boundary"))
    expected_status = _string(expected_runtime.get("status"))
    expected_git_verified = _bool(expected_runtime.get("git_inventory_verified"))
    expected_claim_match = _bool(expected_runtime.get("inventory_claim_match"))
    expected_network_required = _bool(expected_runtime.get(NETWORK_ISOLATION_REQUIRED))
    expected_network_enforced = _bool(expected_runtime.get(NETWORK_ISOLATION_ENFORCED))
    expected_execution_blocked = _bool(expected_runtime.get("proof_execution_blocked"))
    expected_runtime_guard_status = _string(expected_runtime.get("runtime_guard_status"))
    isolation = _as_dict(evidence.get("isolation"))

    result["checks"].extend(
        [
            _check(
                name="isolated_evidence_status",
                passed=_string(evidence.get("status")) == expected_status,
                expected=expected_status,
                actual=_string(evidence.get("status")),
            ),
            _check(
                name="isolated_git_inventory_verified",
                passed=_bool(boundary.get("git_inventory_verified")) == expected_git_verified,
                expected=expected_git_verified,
                actual=_bool(boundary.get("git_inventory_verified")),
            ),
            _check(
                name="isolated_inventory_claim_match",
                passed=_bool(evidence.get(INVENTORY_CLAIM_MATCH)) == expected_claim_match,
                expected=expected_claim_match,
                actual=_bool(evidence.get(INVENTORY_CLAIM_MATCH)),
            ),
            _check(
                name="isolated_network_requirement",
                passed=_bool(isolation.get(NETWORK_ISOLATION_REQUIRED))
                == expected_network_required,
                expected=expected_network_required,
                actual=_bool(isolation.get(NETWORK_ISOLATION_REQUIRED)),
            ),
            _check(
                name="isolated_network_enforcement",
                passed=_bool(isolation.get(NETWORK_ISOLATION_ENFORCED))
                == expected_network_enforced,
                expected=expected_network_enforced,
                actual=_bool(isolation.get(NETWORK_ISOLATION_ENFORCED)),
            ),
            _check(
                name="isolated_proof_execution_blocked",
                passed=_bool(isolation.get("proof_execution_blocked"))
                == expected_execution_blocked,
                expected=expected_execution_blocked,
                actual=_bool(isolation.get("proof_execution_blocked")),
            ),
            _check(
                name="isolated_runner_automation_boundary",
                passed=not _bool(boundary.get("automation_allowed")),
                expected=False,
                actual=_bool(boundary.get("automation_allowed")),
            ),
            _check(
                name="isolated_runner_merge_boundary",
                passed=not _bool(boundary.get("merge_authorized")),
                expected=False,
                actual=_bool(boundary.get("merge_authorized")),
            ),
            _check(
                name="isolated_runner_semantic_boundary",
                passed=not _bool(boundary.get("semantic_equivalence_proven")),
                expected=False,
                actual=_bool(boundary.get("semantic_equivalence_proven")),
            ),
        ]
    )

    if expected_runtime_guard_status:
        proof_results = [_as_dict(item) for item in _as_list(evidence.get("proof_results"))]
        actual_guard_status = (
            _string(_as_dict(proof_results[0].get("runtime_guard")).get("status"))
            if proof_results
            else ""
        )
        result["checks"].append(
            _check(
                name="isolated_runtime_guard_status",
                passed=actual_guard_status == expected_runtime_guard_status,
                expected=expected_runtime_guard_status,
                actual=actual_guard_status,
            )
        )

    result["isolated_proof_evidence"] = evidence
    result["live_evidence_exercised"] = True
    result["passed"] = all(_bool(item.get("passed")) for item in result["checks"])
    result["status"] = "passed" if result["passed"] else "failed"
    return result


def _type_rate(results: list[JsonObject], scenario_type: str) -> float:
    matching = [item for item in results if item.get("scenario_type") == scenario_type]
    if not matching:
        return 0.0
    passing = sum(1 for item in matching if item.get("passed") is True)
    return round(passing / len(matching), 4)


def build_benchmark_report(scenarios: list[Mapping[str, Any]]) -> JsonObject:
    results = [evaluate_scenario(scenario) for scenario in scenarios]
    type_counts = Counter(_string(item.get("scenario_type")) for item in results)
    required_present = all(type_counts.get(item, 0) >= 1 for item in REQUIRED_SCENARIO_TYPES)
    required_passed = all(
        any(
            result.get("scenario_type") == scenario_type and result.get("passed") is True
            for result in results
        )
        for scenario_type in REQUIRED_SCENARIO_TYPES
    )

    automation_allowed_count = sum(
        1
        for result in results
        if _bool(
            _as_dict(_as_dict(result.get("patch_score")).get("decision")).get("automation_allowed")
        )
        or _bool(
            _as_dict(_as_dict(result.get("protected_verifier_result")).get("decision")).get(
                "automation_allowed"
            )
        )
    )
    merge_authorized_count = sum(
        1
        for result in results
        if _bool(
            _as_dict(_as_dict(result.get("protected_verifier_result")).get("decision")).get(
                "merge_authorized"
            )
        )
    )
    semantic_equivalence_claimed_count = sum(
        1
        for result in results
        if _bool(
            _as_dict(_as_dict(result.get("protected_verifier_result")).get("decision")).get(
                "semantic_equivalence_proven"
            )
        )
    )

    passed_count = sum(1 for item in results if item.get("passed") is True)
    boundary_preserved = (
        automation_allowed_count == 0
        and merge_authorized_count == 0
        and semantic_equivalence_claimed_count == 0
    )
    passed = (
        bool(results)
        and passed_count == len(results)
        and required_present
        and required_passed
        and boundary_preserved
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "passed" if passed else "failed",
        "scenario_count": len(results),
        "passed_count": passed_count,
        "failed_count": len(results) - passed_count,
        "scenario_type_counts": dict(sorted(type_counts.items())),
        "required_contract": {
            "required_scenario_types": list(REQUIRED_SCENARIO_TYPES),
            "all_required_present": required_present,
            "all_required_passed": required_passed,
            "nop_fail_rate": _type_rate(results, "nop_fail"),
            "oracle_pass_rate": _type_rate(results, "oracle_pass"),
            "unsafe_patch_rejection_rate": _type_rate(results, "unsafe_patch_fail"),
        },
        "safety_boundary": {
            "execution_model": "read_only_in_process_fixture_evaluation",
            "automation_allowed_count": automation_allowed_count,
            "merge_authorized_count": merge_authorized_count,
            "semantic_equivalence_claimed_count": semantic_equivalence_claimed_count,
            "preserved": boundary_preserved,
        },
        "attempt_scored_count": sum(1 for item in results if item.get("attempt_scored") is True),
        "scenarios": results,
        "next_boundary": (
            "Add isolated execution and anti-cheat runtime checks before any automation wiring."
        ),
    }


def build_isolated_evidence_report(
    scenario_runs: list[tuple[Mapping[str, Any], Path]],
) -> JsonObject:
    results = [
        evaluate_isolated_evidence_scenario(scenario, repo_root=repo_root)
        for scenario, repo_root in scenario_runs
    ]
    type_counts = Counter(_string(item.get("scenario_type")) for item in results)
    required_present = all(
        type_counts.get(item, 0) >= 1 for item in ISOLATED_EVIDENCE_REQUIRED_TYPES
    )
    required_passed = all(
        any(
            result.get("scenario_type") == scenario_type and result.get("passed") is True
            for result in results
        )
        for scenario_type in ISOLATED_EVIDENCE_REQUIRED_TYPES
    )

    verifier_decisions = [
        _as_dict(_as_dict(result.get("protected_verifier_result")).get("decision"))
        for result in results
    ]
    evidence_boundaries = [
        _as_dict(_as_dict(result.get("isolated_proof_evidence")).get("decision_boundary"))
        for result in results
    ]

    automation_allowed_count = sum(
        1
        for decision, boundary in zip(verifier_decisions, evidence_boundaries, strict=True)
        if _bool(decision.get("automation_allowed")) or _bool(boundary.get("automation_allowed"))
    )
    merge_authorized_count = sum(
        1
        for decision, boundary in zip(verifier_decisions, evidence_boundaries, strict=True)
        if _bool(decision.get("merge_authorized")) or _bool(boundary.get("merge_authorized"))
    )
    semantic_equivalence_claimed_count = sum(
        1
        for decision, boundary in zip(verifier_decisions, evidence_boundaries, strict=True)
        if _bool(decision.get("semantic_equivalence_proven"))
        or _bool(boundary.get("semantic_equivalence_proven"))
    )
    boundary_preserved = (
        automation_allowed_count == 0
        and merge_authorized_count == 0
        and semantic_equivalence_claimed_count == 0
    )
    passed_count = sum(1 for item in results if item.get("passed") is True)
    passed = (
        bool(results)
        and passed_count == len(results)
        and required_present
        and required_passed
        and boundary_preserved
    )

    return {
        "schema_version": ISOLATED_EVIDENCE_SCHEMA_VERSION,
        "report_mode": LIVE_EVIDENCE_SOURCE,
        "status": "passed" if passed else "failed",
        "scenario_count": len(results),
        "passed_count": passed_count,
        "failed_count": len(results) - passed_count,
        "scenario_type_counts": dict(sorted(type_counts.items())),
        "required_contract": {
            "required_scenario_types": list(ISOLATED_EVIDENCE_REQUIRED_TYPES),
            "all_required_present": required_present,
            "all_required_passed": required_passed,
            "oracle_pass_rate": _type_rate(results, "oracle_pass"),
            "claim_mismatch_rejection_rate": _type_rate(
                results,
                INVENTORY_CLAIM_MISMATCH_FAIL,
            ),
            "proof_mutation_rejection_rate": _type_rate(results, PROOF_MUTATION_FAIL),
            "network_boundary_rejection_rate": _type_rate(
                results,
                NETWORK_BOUNDARY_REQUIRED_FAIL,
            ),
            "unclaimed_write_rejection_rate": _type_rate(
                results,
                UNCLAIMED_WRITE_FAIL,
            ),
            "evidence_shadow_rejection_rate": _type_rate(
                results,
                EVIDENCE_SHADOW_FAIL,
            ),
        },
        "live_evidence": {
            "scenario_count": len(results),
            "git_inventory_verified_count": sum(
                1
                for boundary in evidence_boundaries
                if _bool(boundary.get("git_inventory_verified"))
            ),
            "expected_failed_evidence_count": sum(
                1
                for result in results
                if _string(_as_dict(result.get("isolated_proof_evidence")).get("status"))
                == "failed"
                and result.get("passed") is True
            ),
            NETWORK_BOUNDARY_BLOCKED_COUNT: sum(
                1
                for result in results
                if result.get("scenario_type") == NETWORK_BOUNDARY_REQUIRED_FAIL
                and result.get("passed") is True
            ),
            "network_isolation_enforced_count": sum(
                1
                for result in results
                if _bool(
                    _as_dict(_as_dict(result.get("isolated_proof_evidence")).get("isolation")).get(
                        NETWORK_ISOLATION_ENFORCED
                    )
                )
            ),
            ANTI_CHEAT_REJECTION_COUNT: sum(
                1
                for result in results
                if result.get("scenario_type") in {UNCLAIMED_WRITE_FAIL, EVIDENCE_SHADOW_FAIL}
                and result.get("passed") is True
            ),
        },
        "safety_boundary": {
            "execution_model": LIVE_EXECUTION_MODEL,
            "automation_allowed_count": automation_allowed_count,
            "merge_authorized_count": merge_authorized_count,
            "semantic_equivalence_claimed_count": semantic_equivalence_claimed_count,
            "preserved": boundary_preserved,
        },
        "attempt_scored_count": sum(1 for item in results if item.get("attempt_scored") is True),
        "scenarios": results,
        "next_boundary": (
            "Surface captured runtime-proof artifacts in PR Quality before any automation wiring."
        ),
    }


def _run_diagnostic_worker_fixture(
    scenario: Mapping[str, Any],
) -> tuple[JsonObject, JsonObject, JsonObject]:
    scenario_id = _string(scenario.get("scenario_id"))
    job = build_diagnostic_job(
        repo="controlled-fixture/replayable-benchmark",
        base_sha="fixture-base",
        head_sha=f"fixture-head-{scenario_id}",
        event_name="replayable_benchmark",
        pr_number=0,
        input_artifacts={"runtime_proof_artifacts": f"fixture:{scenario_id}"},
    )
    with tempfile.TemporaryDirectory(prefix="sdetkit-runtime-worker-benchmark-") as temp_dir:
        worker_dir = Path(temp_dir) / "worker"
        result = run_diagnostic_worker(
            job,
            runtime_proof_artifacts=_as_dict(scenario.get("runtime_proof_artifacts")),
            out_dir=worker_dir,
        )
        vector = _read_json_object(worker_dir / "vector" / "diagnostic-vector.json")
    return job, result, vector


def evaluate_diagnostic_worker_scenario(scenario: Mapping[str, Any]) -> JsonObject:
    scenario_id = _string(scenario.get("scenario_id"))
    scenario_type = _string(scenario.get("scenario_type"))
    if scenario_type not in DIAGNOSTIC_WORKER_SCENARIO_TYPES:
        raise ValueError(f"unsupported diagnostic worker scenario_type: {scenario_type}")

    job, worker_result, diagnostic_vector = _run_diagnostic_worker_fixture(scenario)
    result_summary = _as_dict(worker_result.get("summary"))
    primary = _as_dict(worker_result.get("primary_diagnosis"))
    boundary = _as_dict(worker_result.get("decision_boundary"))
    expected = _as_dict(scenario.get("expected"))
    diagnoses = [_as_dict(item) for item in _as_list(diagnostic_vector.get("diagnoses"))]
    failure_vector = _as_dict(diagnoses[0].get("failure_vector")) if diagnoses else {}
    checks: list[JsonObject] = [
        _check(
            name="worker_automation_boundary",
            passed=not _bool(boundary.get("automation_allowed")),
            expected=False,
            actual=_bool(boundary.get("automation_allowed")),
        ),
        _check(
            name="worker_merge_boundary",
            passed=not _bool(boundary.get("merge_authorized")),
            expected=False,
            actual=_bool(boundary.get("merge_authorized")),
        ),
        _check(
            name="worker_semantic_boundary",
            passed=not _bool(boundary.get("semantic_equivalence_proven")),
            expected=False,
            actual=_bool(boundary.get("semantic_equivalence_proven")),
        ),
    ]
    trajectory_records: list[JsonObject] = []
    observed_error = ""

    if scenario_type == RUNTIME_GUARD_WORKER_ORACLE_PASS:
        trajectory_records = build_worker_trajectory_records(
            job=job,
            worker_result=worker_result,
            diagnostic_vector=diagnostic_vector,
            repo="controlled-fixture/replayable-benchmark",
            branch="fixture",
            commit_sha="fixture-runtime-worker-oracle",
        )
        record = _as_dict(trajectory_records[0]) if trajectory_records else {}
        decision = _as_dict(record.get("decision"))
        proof = _as_dict(record.get("proof"))
        worker_evidence = _as_dict(record.get("worker_evidence"))
        checks.extend(
            [
                _check(
                    name="runtime_guard_failure_class",
                    passed=_string(failure_vector.get("failure_class"))
                    == _string(expected.get("failure_class")),
                    expected=_string(expected.get("failure_class")),
                    actual=_string(failure_vector.get("failure_class")),
                ),
                _check(
                    name="runtime_guard_surface",
                    passed=_string(primary.get("failure_surface"))
                    == _string(expected.get("primary_surface")),
                    expected=_string(expected.get("primary_surface")),
                    actual=_string(primary.get("failure_surface")),
                ),
                _check(
                    name="runtime_guard_action",
                    passed=_string(result_summary.get("primary_action"))
                    == _string(expected.get("primary_action")),
                    expected=_string(expected.get("primary_action")),
                    actual=_string(result_summary.get("primary_action")),
                ),
                _check(
                    name="runtime_guard_review_first",
                    passed=_bool(primary.get("review_first"))
                    and not _bool(primary.get("safe_fix_candidate")),
                    expected=True,
                    actual=_bool(primary.get("review_first"))
                    and not _bool(primary.get("safe_fix_candidate")),
                ),
                _check(
                    name="runtime_guard_advisory_trajectory",
                    passed=len(trajectory_records) == 1
                    and _bool(decision.get("review_first"))
                    and not _bool(decision.get("auto_fix_allowed"))
                    and _as_list(proof.get("commands")) == []
                    and _bool(worker_evidence.get("reporting_only")),
                    expected=True,
                    actual=len(trajectory_records) == 1
                    and _bool(decision.get("review_first"))
                    and not _bool(decision.get("auto_fix_allowed"))
                    and _as_list(proof.get("commands")) == []
                    and _bool(worker_evidence.get("reporting_only")),
                ),
            ]
        )
    elif scenario_type == RUNTIME_GUARD_WORKER_NOP_PASS:
        trajectory_records = build_worker_trajectory_records(
            job=job,
            worker_result=worker_result,
            diagnostic_vector=diagnostic_vector,
            repo="controlled-fixture/replayable-benchmark",
            branch="fixture",
            commit_sha="fixture-runtime-worker-nop",
        )
        checks.extend(
            [
                _check(
                    name="passing_guard_emits_no_diagnosis",
                    passed=_int(result_summary.get("diagnosis_count")) == 0 and not diagnoses,
                    expected=True,
                    actual=_int(result_summary.get("diagnosis_count")) == 0 and not diagnoses,
                ),
                _check(
                    name="passing_guard_emits_no_trajectory",
                    passed=trajectory_records == [],
                    expected=[],
                    actual=trajectory_records,
                ),
            ]
        )
    else:
        forged = json.loads(json.dumps(worker_result))
        forged_boundary = _as_dict(scenario.get("forged_worker_boundary"))
        _as_dict(forged.get("decision_boundary")).update(forged_boundary)
        expected_error = _string(scenario.get("expected_error"))
        rejected = False
        try:
            build_worker_trajectory_records(
                job=job,
                worker_result=forged,
                diagnostic_vector=diagnostic_vector,
                repo="controlled-fixture/replayable-benchmark",
                branch="fixture",
                commit_sha="fixture-runtime-worker-unsafe",
            )
        except ValueError as exc:
            observed_error = str(exc)
            rejected = expected_error in observed_error
        checks.extend(
            [
                _check(
                    name="forged_worker_authority_rejected",
                    passed=rejected,
                    expected=expected_error,
                    actual=observed_error,
                ),
                _check(
                    name="forged_worker_emits_no_trajectory",
                    passed=trajectory_records == [],
                    expected=[],
                    actual=trajectory_records,
                ),
            ]
        )

    passed = all(_bool(item.get("passed")) for item in checks)
    return {
        "scenario_id": scenario_id,
        "scenario_type": scenario_type,
        "status": "passed" if passed else "failed",
        "passed": passed,
        "attempt_scored": False,
        "attempt_score": 0,
        "checks": checks,
        "diagnosis_count": _int(result_summary.get("diagnosis_count")),
        "trajectory_record_count": len(trajectory_records),
        "observed_error": observed_error,
    }


def build_diagnostic_worker_benchmark_report(scenarios: list[Mapping[str, Any]]) -> JsonObject:
    results = [evaluate_diagnostic_worker_scenario(scenario) for scenario in scenarios]
    type_counts = Counter(_string(item.get("scenario_type")) for item in results)
    required_present = all(
        type_counts.get(item, 0) >= 1 for item in DIAGNOSTIC_WORKER_REQUIRED_SCENARIO_TYPES
    )
    required_passed = all(
        any(
            result.get("scenario_type") == scenario_type and result.get("passed") is True
            for result in results
        )
        for scenario_type in DIAGNOSTIC_WORKER_REQUIRED_SCENARIO_TYPES
    )
    passed_count = sum(1 for item in results if item.get("passed") is True)
    boundary = {
        "execution_model": "_".join(
            ("read", "only", "diagnostic", "worker", "fixture", "evaluation")
        ),
        "automation_allowed_count": 0,
        "merge_authorized_count": 0,
        "semantic_equivalence_claimed_count": 0,
        "preserved": True,
        "contributes_to_current_pr_decision": False,
        "feeds_repo_memory": False,
        "executes_patch": False,
        "protected_verifier_semantics_expanded": False,
    }
    passed = bool(results) and passed_count == len(results) and required_present and required_passed
    return {
        "schema_version": DIAGNOSTIC_WORKER_REPORT_SCHEMA_VERSION,
        "report_mode": DIAGNOSTIC_WORKER_REPORT_MODE,
        "status": "passed" if passed else "failed",
        "scenario_count": len(results),
        "passed_count": passed_count,
        "failed_count": len(results) - passed_count,
        "scenario_type_counts": dict(sorted(type_counts.items())),
        "required_contract": {
            "required_scenario_types": list(DIAGNOSTIC_WORKER_REQUIRED_SCENARIO_TYPES),
            "all_required_present": required_present,
            "all_required_passed": required_passed,
            "oracle_pass_rate": _type_rate(results, RUNTIME_GUARD_WORKER_ORACLE_PASS),
            "nop_pass_rate": _type_rate(results, RUNTIME_GUARD_WORKER_NOP_PASS),
            "unsafe_authority_rejection_rate": _type_rate(
                results, RUNTIME_GUARD_WORKER_AUTHORITY_FAIL
            ),
        },
        "safety_boundary": boundary,
        "attempt_scored_count": 0,
        "scenarios": results,
        "next_boundary": (
            "Keep runtime-guard worker benchmark evidence non-authorizing; "
            "do not add remediation authority."
        ),
    }


def _run_security_freshness_worker_fixture(
    scenario: Mapping[str, Any],
) -> tuple[JsonObject, JsonObject, JsonObject]:
    scenario_id = _string(scenario.get("scenario_id"))
    job = build_diagnostic_job(
        repo="controlled-fixture/replayable-benchmark",
        base_sha="fixture-base",
        head_sha=f"fixture-head-{scenario_id}",
        event_name="replayable_benchmark",
        pr_number=0,
        input_artifacts={
            "security_review": f"fixture:{scenario_id}",
            "runtime_proof_artifacts": f"fixture:{scenario_id}",
        },
    )
    with tempfile.TemporaryDirectory(prefix="sdetkit-security-freshness-benchmark-") as temp_dir:
        worker_dir = Path(temp_dir) / "worker"
        result = run_diagnostic_worker(
            job,
            security_review=_as_dict(scenario.get("security_review")),
            runtime_proof_artifacts=_as_dict(scenario.get("runtime_proof_artifacts")),
            out_dir=worker_dir,
        )
        vector = _read_json_object(worker_dir / "vector" / "diagnostic-vector.json")
    return job, result, vector


def evaluate_security_freshness_scenario(scenario: Mapping[str, Any]) -> JsonObject:
    scenario_id = _string(scenario.get("scenario_id"))
    scenario_type = _string(scenario.get("scenario_type"))
    if scenario_type not in SECURITY_FRESHNESS_SCENARIO_TYPES:
        raise ValueError(f"unsupported security freshness scenario_type: {scenario_type}")

    job, worker_result, diagnostic_vector = _run_security_freshness_worker_fixture(scenario)
    result_summary = _as_dict(worker_result.get("summary"))
    primary = _as_dict(worker_result.get("primary_diagnosis"))
    boundary = _as_dict(worker_result.get("decision_boundary"))
    expected = _as_dict(scenario.get("expected"))
    diagnoses = [_as_dict(item) for item in _as_list(diagnostic_vector.get("diagnoses"))]
    primary_vector = _as_dict(diagnoses[0].get("failure_vector")) if diagnoses else {}
    checks: list[JsonObject] = [
        _check(
            name="worker_automation_boundary",
            passed=not _bool(boundary.get("automation_allowed")),
            expected=False,
            actual=_bool(boundary.get("automation_allowed")),
        ),
        _check(
            name="worker_merge_boundary",
            passed=not _bool(boundary.get("merge_authorized")),
            expected=False,
            actual=_bool(boundary.get("merge_authorized")),
        ),
        _check(
            name="worker_semantic_boundary",
            passed=not _bool(boundary.get("semantic_equivalence_proven")),
            expected=False,
            actual=_bool(boundary.get("semantic_equivalence_proven")),
        ),
    ]
    trajectory_records: list[JsonObject] = []
    observed_error = ""

    if scenario_type == SECURITY_FRESHNESS_STALE_RUNTIME_PASS:
        trajectory_records = build_worker_trajectory_records(
            job=job,
            worker_result=worker_result,
            diagnostic_vector=diagnostic_vector,
            repo="controlled-fixture/replayable-benchmark",
            branch="fixture",
            commit_sha="fixture-security-freshness-stale-runtime",
        )
        checks.extend(
            [
                _check(
                    name="stale_security_is_not_worker_vector",
                    passed=all(
                        _string(row.get("failure_surface")) != "security" for row in diagnoses
                    ),
                    expected=True,
                    actual=all(
                        _string(row.get("failure_surface")) != "security" for row in diagnoses
                    ),
                ),
                _check(
                    name="runtime_remains_primary_when_security_is_stale",
                    passed=_string(primary.get("failure_surface"))
                    == _string(expected.get("primary_surface"))
                    and _string(result_summary.get("primary_action"))
                    == _string(expected.get("primary_action"))
                    and _int(result_summary.get("diagnosis_count"))
                    == _int(expected.get("diagnosis_count")),
                    expected=True,
                    actual=_string(primary.get("failure_surface"))
                    == _string(expected.get("primary_surface"))
                    and _string(result_summary.get("primary_action"))
                    == _string(expected.get("primary_action"))
                    and _int(result_summary.get("diagnosis_count"))
                    == _int(expected.get("diagnosis_count")),
                ),
                _check(
                    name="stale_security_runtime_trajectory_is_advisory",
                    passed=len(trajectory_records) == 1
                    and all(
                        not _bool(_as_dict(row.get("decision")).get("auto_fix_allowed"))
                        for row in trajectory_records
                    ),
                    expected=True,
                    actual=len(trajectory_records) == 1
                    and all(
                        not _bool(_as_dict(row.get("decision")).get("auto_fix_allowed"))
                        for row in trajectory_records
                    ),
                ),
            ]
        )
    elif scenario_type == SECURITY_FRESHNESS_CURRENT_PRIMARY_PASS:
        trajectory_records = build_worker_trajectory_records(
            job=job,
            worker_result=worker_result,
            diagnostic_vector=diagnostic_vector,
            repo="controlled-fixture/replayable-benchmark",
            branch="fixture",
            commit_sha="fixture-security-freshness-current-primary",
        )
        checks.extend(
            [
                _check(
                    name="current_security_is_primary",
                    passed=_string(primary.get("failure_surface"))
                    == _string(expected.get("primary_surface"))
                    and _string(result_summary.get("primary_action"))
                    == _string(expected.get("primary_action"))
                    and _int(result_summary.get("diagnosis_count"))
                    == _int(expected.get("diagnosis_count")),
                    expected=True,
                    actual=_string(primary.get("failure_surface"))
                    == _string(expected.get("primary_surface"))
                    and _string(result_summary.get("primary_action"))
                    == _string(expected.get("primary_action"))
                    and _int(result_summary.get("diagnosis_count"))
                    == _int(expected.get("diagnosis_count")),
                ),
                _check(
                    name="current_security_vector_is_review_first",
                    passed=_string(primary_vector.get("source")) == "security_review"
                    and _string(primary_vector.get("failure_class")) == "security"
                    and _string(diagnoses[0].get("stale_or_current_signal")) == "current"
                    and _bool(diagnoses[0].get("review_first"))
                    and not _bool(diagnoses[0].get("safe_fix_candidate")),
                    expected=True,
                    actual=_string(primary_vector.get("source")) == "security_review"
                    and _string(primary_vector.get("failure_class")) == "security"
                    and _string(diagnoses[0].get("stale_or_current_signal")) == "current"
                    and _bool(diagnoses[0].get("review_first"))
                    and not _bool(diagnoses[0].get("safe_fix_candidate")),
                ),
                _check(
                    name="current_security_trajectory_has_no_fix_authority",
                    passed=len(trajectory_records) == 2
                    and all(
                        not _bool(_as_dict(row.get("decision")).get("auto_fix_allowed"))
                        for row in trajectory_records
                    ),
                    expected=True,
                    actual=len(trajectory_records) == 2
                    and all(
                        not _bool(_as_dict(row.get("decision")).get("auto_fix_allowed"))
                        for row in trajectory_records
                    ),
                ),
            ]
        )
    else:
        forged = json.loads(json.dumps(worker_result))
        _as_dict(forged.get("decision_boundary")).update(
            _as_dict(scenario.get("forged_worker_boundary"))
        )
        expected_error = _string(scenario.get("expected_error"))
        rejected = False
        try:
            build_worker_trajectory_records(
                job=job,
                worker_result=forged,
                diagnostic_vector=diagnostic_vector,
                repo="controlled-fixture/replayable-benchmark",
                branch="fixture",
                commit_sha="fixture-security-freshness-authority-unsafe",
            )
        except ValueError as exc:
            observed_error = str(exc)
            rejected = expected_error in observed_error
        checks.extend(
            [
                _check(
                    name="current_security_before_forgery_is_review_first",
                    passed=_string(primary.get("failure_surface")) == "security"
                    and not _bool(primary.get("safe_fix_candidate")),
                    expected=True,
                    actual=_string(primary.get("failure_surface")) == "security"
                    and not _bool(primary.get("safe_fix_candidate")),
                ),
                _check(
                    name="forged_security_worker_authority_rejected",
                    passed=rejected,
                    expected=expected_error,
                    actual=observed_error,
                ),
                _check(
                    name="forged_security_worker_emits_no_trajectory",
                    passed=trajectory_records == [],
                    expected=[],
                    actual=trajectory_records,
                ),
            ]
        )

    passed = all(_bool(item.get("passed")) for item in checks)
    return {
        "scenario_id": scenario_id,
        "scenario_type": scenario_type,
        "status": "passed" if passed else "failed",
        "passed": passed,
        "attempt_scored": False,
        "attempt_score": 0,
        "checks": checks,
        "diagnosis_count": _int(result_summary.get("diagnosis_count")),
        "trajectory_record_count": len(trajectory_records),
        "observed_error": observed_error,
    }


def build_security_freshness_benchmark_report(scenarios: list[Mapping[str, Any]]) -> JsonObject:
    results = [evaluate_security_freshness_scenario(scenario) for scenario in scenarios]
    type_counts = Counter(_string(item.get("scenario_type")) for item in results)
    required_present = all(
        type_counts.get(item, 0) >= 1 for item in SECURITY_FRESHNESS_REQUIRED_SCENARIO_TYPES
    )
    required_passed = all(
        any(
            result.get("scenario_type") == scenario_type and result.get("passed") is True
            for result in results
        )
        for scenario_type in SECURITY_FRESHNESS_REQUIRED_SCENARIO_TYPES
    )
    passed_count = sum(1 for item in results if item.get("passed") is True)
    boundary = {
        "execution_model": "_".join(
            ("read", "only", "security", "freshness", "fixture", "evaluation")
        ),
        "automation_allowed_count": 0,
        "merge_authorized_count": 0,
        "semantic_equivalence_claimed_count": 0,
        "preserved": True,
        "contributes_to_current_pr_decision": False,
        "feeds_repo_memory": False,
        "executes_patch": False,
        "protected_verifier_semantics_expanded": False,
    }
    passed = bool(results) and passed_count == len(results) and required_present and required_passed
    return {
        "schema_version": SECURITY_FRESHNESS_REPORT_SCHEMA_VERSION,
        "report_mode": SECURITY_FRESHNESS_REPORT_MODE,
        "status": "passed" if passed else "failed",
        "scenario_count": len(results),
        "passed_count": passed_count,
        "failed_count": len(results) - passed_count,
        "scenario_type_counts": dict(sorted(type_counts.items())),
        "required_contract": {
            "required_scenario_types": list(SECURITY_FRESHNESS_REQUIRED_SCENARIO_TYPES),
            "all_required_present": required_present,
            "all_required_passed": required_passed,
            "stale_exclusion_pass_rate": _type_rate(results, SECURITY_FRESHNESS_STALE_RUNTIME_PASS),
            "current_primary_pass_rate": _type_rate(
                results, SECURITY_FRESHNESS_CURRENT_PRIMARY_PASS
            ),
            "unsafe_authority_rejection_rate": _type_rate(
                results, SECURITY_FRESHNESS_AUTHORITY_FAIL
            ),
        },
        "safety_boundary": boundary,
        "attempt_scored_count": 0,
        "scenarios": results,
        "next_boundary": (
            "Keep security-freshness worker evidence review-first and non-authorizing; "
            "do not add security dismissal or remediation authority."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    required = _as_dict(report.get("required_contract"))
    boundary = _as_dict(report.get("safety_boundary"))
    live_evidence = _as_dict(report.get("live_evidence"))
    scenarios = [_as_dict(item) for item in _as_list(report.get("scenarios"))]
    report_mode = _string(report.get("report_mode") or "fixture_declared")
    is_live = report_mode == LIVE_EVIDENCE_SOURCE
    is_diagnostic_worker = report_mode == DIAGNOSTIC_WORKER_REPORT_MODE
    is_security_freshness = report_mode == SECURITY_FRESHNESS_REPORT_MODE

    lines = [
        "# Replayable Benchmark Harness report",
        "",
        f"- Status: `{_string(report.get('status'))}`",
        f"- Mode: `{report_mode}`",
        f"- Scenarios: `{_int(report.get('scenario_count'))}`",
        f"- Passed: `{_int(report.get('passed_count'))}`",
        f"- Failed: `{_int(report.get('failed_count'))}`",
        f"- Attempts scored: `{_int(report.get('attempt_scored_count'))}`",
        "",
    ]

    if is_security_freshness:
        lines.extend(
            [
                "## Required security-freshness worker replay contract",
                "",
                (
                    "- All required scenarios present: "
                    f"`{str(_bool(required.get('all_required_present'))).lower()}`"
                ),
                (
                    "- All required scenarios passed: "
                    f"`{str(_bool(required.get('all_required_passed'))).lower()}`"
                ),
                (
                    "- Stale exclusion pass rate: "
                    f"`{float(required.get('stale_exclusion_pass_rate', 0.0) or 0.0):.4f}`"
                ),
                (
                    "- Current security primary pass rate: "
                    f"`{float(required.get('current_primary_pass_rate', 0.0) or 0.0):.4f}`"
                ),
                (
                    "- Unsafe authority rejection rate: "
                    f"`{float(required.get('unsafe_authority_rejection_rate', 0.0) or 0.0):.4f}`"
                ),
                (
                    "- Current PR decision input: "
                    f"`{str(_bool(boundary.get('contributes_to_current_pr_decision'))).lower()}`"
                ),
                f"- Feeds RepoMemory: `{str(_bool(boundary.get('feeds_repo_memory'))).lower()}`",
                (
                    "- ProtectedVerifier semantics expanded: "
                    f"`{str(_bool(boundary.get('protected_verifier_semantics_expanded'))).lower()}`"
                ),
                "",
            ]
        )
    elif is_diagnostic_worker:
        lines.extend(
            [
                "## Required runtime-guard worker replay contract",
                "",
                (
                    "- All required scenarios present: "
                    f"`{str(_bool(required.get('all_required_present'))).lower()}`"
                ),
                (
                    "- All required scenarios passed: "
                    f"`{str(_bool(required.get('all_required_passed'))).lower()}`"
                ),
                (
                    "- Oracle pass rate: "
                    f"`{float(required.get('oracle_pass_rate', 0.0) or 0.0):.4f}`"
                ),
                (f"- NOP pass rate: `{float(required.get('nop_pass_rate', 0.0) or 0.0):.4f}`"),
                (
                    "- Unsafe authority rejection rate: "
                    f"`{float(required.get('unsafe_authority_rejection_rate', 0.0) or 0.0):.4f}`"
                ),
                (
                    "- Current PR decision input: "
                    f"`{str(_bool(boundary.get('contributes_to_current_pr_decision'))).lower()}`"
                ),
                f"- Feeds RepoMemory: `{str(_bool(boundary.get('feeds_repo_memory'))).lower()}`",
                (
                    "- ProtectedVerifier semantics expanded: "
                    f"`{str(_bool(boundary.get('protected_verifier_semantics_expanded'))).lower()}`"
                ),
                "",
            ]
        )
    elif is_live:
        lines.extend(
            [
                "## Required Git-grounded live-evidence contract",
                "",
                (
                    "- All required scenarios present: "
                    f"`{str(_bool(required.get('all_required_present'))).lower()}`"
                ),
                (
                    "- All required scenarios passed: "
                    f"`{str(_bool(required.get('all_required_passed'))).lower()}`"
                ),
                (
                    "- Oracle pass rate: "
                    f"`{float(required.get('oracle_pass_rate', 0.0) or 0.0):.4f}`"
                ),
                (
                    "- Inventory claim mismatch rejection rate: "
                    f"`{float(required.get('claim_mismatch_rejection_rate', 0.0) or 0.0):.4f}`"
                ),
                (
                    "- Proof mutation rejection rate: "
                    f"`{float(required.get('proof_mutation_rejection_rate', 0.0) or 0.0):.4f}`"
                ),
                (
                    "- Network boundary rejection rate: "
                    f"`{float(required.get('network_boundary_rejection_rate', 0.0) or 0.0):.4f}`"
                ),
                (
                    "- Unclaimed write rejection rate: "
                    f"`{float(required.get('unclaimed_write_rejection_rate', 0.0) or 0.0):.4f}`"
                ),
                (
                    "- Evidence shadow rejection rate: "
                    f"`{float(required.get('evidence_shadow_rejection_rate', 0.0) or 0.0):.4f}`"
                ),
                "",
                "## Live execution evidence",
                "",
                f"- Scenarios executed: `{_int(live_evidence.get('scenario_count'))}`",
                (
                    "- Git inventory verified scenarios: "
                    f"`{_int(live_evidence.get('git_inventory_verified_count'))}`"
                ),
                (
                    "- Expected failed-evidence scenarios: "
                    f"`{_int(live_evidence.get('expected_failed_evidence_count'))}`"
                ),
                (
                    "- Network boundary blocked scenarios: "
                    f"`{_int(live_evidence.get(NETWORK_BOUNDARY_BLOCKED_COUNT))}`"
                ),
                (
                    "- Network isolation enforced scenarios: "
                    f"`{_int(live_evidence.get('network_isolation_enforced_count'))}`"
                ),
                (
                    "- Anti-cheat rejection scenarios: "
                    f"`{_int(live_evidence.get(ANTI_CHEAT_REJECTION_COUNT))}`"
                ),
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## Required benchmark contract",
                "",
                (
                    "- All required scenarios present: "
                    f"`{str(_bool(required.get('all_required_present'))).lower()}`"
                ),
                (
                    "- All required scenarios passed: "
                    f"`{str(_bool(required.get('all_required_passed'))).lower()}`"
                ),
                (f"- NOP fail rate: `{float(required.get('nop_fail_rate', 0.0) or 0.0):.4f}`"),
                (
                    "- Oracle pass rate: "
                    f"`{float(required.get('oracle_pass_rate', 0.0) or 0.0):.4f}`"
                ),
                (
                    "- Unsafe patch rejection rate: "
                    f"`{float(required.get('unsafe_patch_rejection_rate', 0.0) or 0.0):.4f}`"
                ),
                "",
            ]
        )

    lines.extend(
        [
            "## Safety boundary",
            "",
            f"- Execution model: `{_string(boundary.get('execution_model'))}`",
            f"- Automation allowed count: `{_int(boundary.get('automation_allowed_count'))}`",
            f"- Merge authorized count: `{_int(boundary.get('merge_authorized_count'))}`",
            (
                "- Semantic equivalence claimed count: "
                f"`{_int(boundary.get('semantic_equivalence_claimed_count'))}`"
            ),
            f"- Boundary preserved: `{str(_bool(boundary.get('preserved'))).lower()}`",
            "",
            "## Scenario results",
            "",
        ]
    )

    for scenario in scenarios:
        source = _string(scenario.get(VERIFICATION_EVIDENCE_SOURCE))
        source_suffix = f", evidence=`{source}`" if source else ""
        lines.append(
            f"- `{_string(scenario.get('scenario_id'))}` "
            f"({_string(scenario.get('scenario_type'))}): "
            f"`{_string(scenario.get('status'))}`, "
            f"attempt_score=`{_int(scenario.get('attempt_score'))}`"
            f"{source_suffix}"
        )

    lines.extend(["", "## Boundary", ""])
    if is_security_freshness:
        lines.extend(
            [
                "- This harness replays security-freshness DiagnosticWorker behavior through controlled fixture inputs.",
                "- It proves stale security does not displace current runtime diagnosis.",
                "- It proves current security remains review-first and rejects forged worker authority.",
                "- It does not feed current PR decisions or RepoMemory.",
                "- It does not authorize security dismissal, remediation, or merge.",
            ]
        )
    elif is_diagnostic_worker:
        lines.extend(
            [
                "- This harness replays runtime-guard DiagnosticWorker behavior through controlled fixture inputs.",
                "- It records oracle, NOP, and unsafe-authority outcomes without applying patches.",
                "- It does not feed current PR decisions or RepoMemory.",
                "- It does not expand ProtectedVerifier semantic claims or authorize automation.",
            ]
        )
    elif is_live:
        lines.extend(
            [
                "- This harness executes allowlisted proof profiles in disposable workspace copies.",
                "- Git-derived inventory grounds each live scenario before verification.",
                "- It does not apply patches, authorize automation, or authorize merge.",
                "- Required network isolation fails closed without a verified backend.",
                "- Successful network isolation and semantic equivalence remain unproven.",
            ]
        )
    else:
        lines.extend(
            [
                "- This harness replays deterministic fixture evidence through PatchScorer and ProtectedVerifier.",
                "- It does not apply patches or execute proof commands.",
                "- It does not authorize automation or merge.",
            ]
        )
    lines.extend([f"- Next: {_string(report.get('next_boundary'))}", ""])
    return "\n".join(lines)


def write_report(report: Mapping[str, Any], *, out_dir: Path) -> dict[str, str]:
    json_path = out_dir / REPORT_JSON
    markdown_path = out_dir / REPORT_MD
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return {
        "benchmark_report_json": json_path.as_posix(),
        "benchmark_report_markdown": markdown_path.as_posix(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.replayable_benchmark_harness")
    parser.add_argument(
        "--scenario",
        type=Path,
        action="append",
        default=[],
        help="Fixture-backed benchmark scenario JSON. May be supplied more than once.",
    )
    parser.add_argument(
        "--security-freshness-scenario",
        type=Path,
        action="append",
        default=[],
        help="Controlled DiagnosticWorker security-freshness scenario JSON.",
    )
    parser.add_argument(
        "--diagnostic-worker-scenario",
        type=Path,
        action="append",
        default=[],
        help="Controlled DiagnosticWorker runtime-guard scenario JSON.",
    )
    parser.add_argument(
        "--isolated-scenario",
        type=Path,
        action="append",
        default=[],
        help="Git-grounded isolated-proof benchmark scenario JSON.",
    )
    parser.add_argument(
        "--isolated-repo-root",
        type=Path,
        action="append",
        default=[],
        help="Repository root paired by position with --isolated-scenario.",
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        if args.security_freshness_scenario:
            if (
                args.diagnostic_worker_scenario
                or args.scenario
                or args.isolated_scenario
                or args.isolated_repo_root
            ):
                raise ValueError(
                    "security-freshness scenarios cannot be combined with other benchmark modes"
                )
            report = build_security_freshness_benchmark_report(
                load_security_freshness_scenarios(args.security_freshness_scenario)
            )
        elif args.diagnostic_worker_scenario:
            if args.scenario or args.isolated_scenario or args.isolated_repo_root:
                raise ValueError(
                    "diagnostic-worker scenarios cannot be combined with other benchmark modes"
                )
            report = build_diagnostic_worker_benchmark_report(
                load_diagnostic_worker_scenarios(args.diagnostic_worker_scenario)
            )
        elif args.isolated_scenario:
            if args.scenario:
                raise ValueError(
                    "fixture --scenario and --isolated-scenario modes cannot be combined"
                )
            if len(args.isolated_scenario) != len(args.isolated_repo_root):
                raise ValueError("each --isolated-scenario requires one --isolated-repo-root")
            scenarios = load_scenarios(args.isolated_scenario)
            report = build_isolated_evidence_report(
                list(zip(scenarios, args.isolated_repo_root, strict=True))
            )
        else:
            if not args.scenario:
                raise ValueError("at least one --scenario is required")
            report = build_benchmark_report(load_scenarios(args.scenario))
        artifacts = write_report(report, out_dir=args.out_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "artifacts": artifacts,
                    "scenario_count": report["scenario_count"],
                    "passed_count": report["passed_count"],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        for key, value in artifacts.items():
            print(f"{key}: {value}")

    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
