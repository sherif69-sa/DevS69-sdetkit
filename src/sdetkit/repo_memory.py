from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sdetkit.replayable_benchmark_harness import (
    ANTI_CHEAT_REJECTION_COUNT,
    EVIDENCE_SHADOW_FAIL,
    INVENTORY_CLAIM_MISMATCH_FAIL,
    LIVE_EVIDENCE_SOURCE,
    NETWORK_BOUNDARY_BLOCKED_COUNT,
    NETWORK_BOUNDARY_REQUIRED_FAIL,
    PROOF_MUTATION_FAIL,
    UNCLAIMED_WRITE_FAIL,
    VERIFICATION_EVIDENCE_SOURCE,
)
from sdetkit.trusted_test_observation_classification import (
    SCHEMA_VERSION as TRUSTED_TEST_OBSERVATION_CLASSIFICATION_SCHEMA,
)
from sdetkit.trusted_test_observation_history import ALLOWED_OUTCOMES

SCHEMA_VERSION = "sdetkit.repo_memory.v6"
DEFAULT_OUT_DIR = Path("build") / "repo-memory"
PROFILE_JSON = "repo-memory-profile.json"
PROFILE_MD = "repo-memory-profile.md"

FIXTURE_EVIDENCE_SOURCE = "_".join(("fixture", "declared"))
LIVE_PROFILE_STATUS = "_".join(("live", "proof", "supported", "memory"))
LIVE_PROOF_STATE = "_".join(("live", "proof", "supported", "candidate"))
GIT_INVENTORY_VERIFIED = "_".join(("git", "inventory", "verified"))
EXPECTED_FAILED_EVIDENCE_COUNT = "_".join(("expected", "failed", "evidence", "count"))
CONTROLLED_VALIDATION_SCHEMA = "sdetkit.pr_quality.candidate_validation.v1"
CONTROLLED_VALIDATION_STATUS = "_".join(("controlled", "validation", "passed"))
LEGACY_FLAKY_CLASSIFICATION_SCHEMA = "sdetkit.intelligence.flake.v1"
TRUSTED_FLAKY_IDENTITY_KIND = "fingerprint_only"
NO_TEST_OBSERVATIONS = "_".join(("no", "test", "observations", "available"))
PRODUCER_VETTED_OBSERVATIONS = "_".join(
    ("producer", "vetted", "flaky", "observations", "available")
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


def _read_json(path: Path) -> JsonObject:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"expected JSON object in {path}"
        raise ValueError(msg)
    return payload


def _decision_status(payload: Mapping[str, Any]) -> str:
    return _string(_as_dict(payload.get("decision")).get("status"))


def _benchmark_contract_proven(benchmark_report: Mapping[str, Any]) -> bool:
    required = _as_dict(benchmark_report.get("required_contract"))
    boundary = _as_dict(benchmark_report.get("safety_boundary"))
    return (
        _string(benchmark_report.get("status")) == "passed"
        and _bool(required.get("all_required_present"))
        and _bool(required.get("all_required_passed"))
        and _bool(boundary.get("preserved"))
        and _int(boundary.get("automation_allowed_count")) == 0
        and _int(boundary.get("merge_authorized_count")) == 0
        and _int(boundary.get("semantic_equivalence_claimed_count")) == 0
    )


def _live_contract_proven(live_benchmark_report: Mapping[str, Any]) -> bool:
    return _string(
        live_benchmark_report.get("report_mode")
    ) == LIVE_EVIDENCE_SOURCE and _benchmark_contract_proven(live_benchmark_report)


def _controlled_candidate_validation(evidence: Mapping[str, Any]) -> JsonObject:
    denied = {
        "automation_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }
    payload = _as_dict(evidence)
    if not payload:
        return {
            "collection_status": "not_collected",
            "status": "not_collected",
            "scenario_count": 0,
            "passed_count": 0,
            "structurally_verified_count": 0,
            "review_first_count": 0,
            "current_pr_decision_input": False,
            "decision_boundary": denied,
        }

    if _string(payload.get("schema_version")) != CONTROLLED_VALIDATION_SCHEMA:
        raise ValueError("controlled candidate validation schema is not supported")
    if _string(payload.get("status")) != "passed":
        raise ValueError("controlled candidate validation must have passed before ingestion")

    boundary = _as_dict(payload.get("boundary"))
    if not _bool(boundary.get("controlled_fixture_inputs_only")):
        raise ValueError("controlled candidate validation must use fixture inputs only")
    if _bool(boundary.get("contributes_to_current_pr_decision")):
        raise ValueError(
            "controlled candidate validation cannot contribute to a current PR decision"
        )
    expanded = [key for key in denied if _bool(boundary.get(key))]
    if expanded:
        raise ValueError(
            "controlled candidate validation expands authority: " + ", ".join(expanded)
        )

    scenarios = [_as_dict(item) for item in _as_list(payload.get("scenarios")) if _as_dict(item)]
    scenario_count = _int(payload.get("scenario_count"))
    passed_count = _int(payload.get("passed_count"))
    if scenario_count != len(scenarios) or passed_count != scenario_count or scenario_count < 2:
        raise ValueError("controlled candidate validation scenario totals are inconsistent")

    expected_states = {
        ("candidate_structurally_verified", "structurally_verified_candidate"),
        ("candidate_review_first_after_verification", "blocked_review_first"),
    }
    observed_states: set[tuple[str, str]] = set()
    for scenario in scenarios:
        if not _bool(scenario.get("passed")):
            raise ValueError("controlled candidate validation contains a failing scenario")
        scenario_expanded = [key for key in denied if _bool(scenario.get(key))]
        if scenario_expanded:
            raise ValueError(
                "controlled candidate validation scenario expands authority: "
                + ", ".join(scenario_expanded)
            )
        observed_states.add(
            (
                _string(scenario.get("observed_status")),
                _string(scenario.get("observed_verifier_status")),
            )
        )
    if not expected_states.issubset(observed_states):
        raise ValueError("controlled candidate validation does not prove both boundary states")

    return {
        "collection_status": "collected",
        "status": CONTROLLED_VALIDATION_STATUS,
        "evidence_type": "deterministic_fixture_validation",
        "scenario_count": scenario_count,
        "passed_count": passed_count,
        "structurally_verified_count": sum(
            1
            for state, verifier in observed_states
            if state == "candidate_structurally_verified"
            and verifier == "structurally_verified_candidate"
        ),
        "review_first_count": sum(
            1
            for state, verifier in observed_states
            if state == "candidate_review_first_after_verification"
            and verifier == "blocked_review_first"
        ),
        "current_pr_decision_input": False,
        "decision_boundary": denied,
    }


def _trajectory_authority_evidence(pattern_insights: Mapping[str, Any]) -> JsonObject:
    denied = {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "automatic_security_fix_allowed": False,
        "automatic_dismissal_allowed": False,
    }
    payload = _as_dict(pattern_insights.get("authority_boundary_evidence"))
    if not payload:
        return {
            "collection_status": "not_collected",
            "status": "not_collected",
            "source": "trajectory.authority_boundary",
            "record_count": 0,
            "review_first_count": 0,
            "auto_fix_allowed_count": 0,
            "reporting_only_count": 0,
            "sources": [],
            "decision_boundary": denied,
        }

    boundary = _as_dict(payload.get("decision_boundary"))
    expanded = [key for key in denied if _bool(boundary.get(key))]
    if expanded:
        raise ValueError("trajectory authority evidence expands authority: " + ", ".join(expanded))

    return {
        "collection_status": _string(payload.get("collection_status")) or "collected",
        "status": _string(payload.get("status")) or "authority_boundary_evidence_observed",
        "source": _string(payload.get("source")) or "trajectory.authority_boundary",
        "record_count": _int(payload.get("record_count")),
        "review_first_count": _int(payload.get("review_first_count")),
        "auto_fix_allowed_count": _int(payload.get("auto_fix_allowed_count")),
        "reporting_only_count": _int(payload.get("reporting_only_count")),
        "sources": [_string(item) for item in _as_list(payload.get("sources")) if _string(item)],
        "decision_boundary": denied,
    }


def _safety_gate_evidence(pattern_insights: Mapping[str, Any]) -> JsonObject:
    denied = {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }
    payload = _as_dict(pattern_insights.get("safety_gate_evidence"))
    if not payload:
        return {
            "collection_status": "not_collected",
            "status": "not_collected",
            "source": "trajectory.safety_gate",
            "record_count": 0,
            "review_first_count": 0,
            "safe_fix_allowed_count": 0,
            "reporting_only_count": 0,
            "report_paths": [],
            "decision_boundary": denied,
        }

    boundary = _as_dict(payload.get("decision_boundary"))
    expanded = [key for key in denied if _bool(boundary.get(key))]
    if expanded:
        raise ValueError("SafetyGate evidence expands authority: " + ", ".join(expanded))

    return {
        "collection_status": _string(payload.get("collection_status")) or "collected",
        "status": _string(payload.get("status")) or "safety_gate_evidence_observed",
        "source": _string(payload.get("source")) or "trajectory.safety_gate",
        "record_count": _int(payload.get("record_count")),
        "review_first_count": _int(payload.get("review_first_count")),
        "safe_fix_allowed_count": _int(payload.get("safe_fix_allowed_count")),
        "reporting_only_count": _int(payload.get("reporting_only_count")),
        "report_paths": [
            _string(item) for item in _as_list(payload.get("report_paths")) if _string(item)
        ],
        "decision_boundary": denied,
    }


def _failure_vector_contract_evidence(
    pattern_insights: Mapping[str, Any],
) -> JsonObject:
    denied = {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "security_dismissal_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_claim": False,
    }
    payload = _as_dict(pattern_insights.get("failure_vector_contract_evidence"))
    if not payload:
        return {
            "collection_status": "not_collected",
            "status": "not_collected",
            "source": "trajectory.failure_vector_contract",
            "record_count": 0,
            "security_relevance_count": 0,
            "authority_boundary_preserved_count": 0,
            "failure_kinds": [],
            "affected_surfaces": [],
            "decision_boundary": denied,
        }

    boundary = _as_dict(payload.get("decision_boundary"))
    expanded = [key for key in denied if _bool(boundary.get(key))]
    if expanded:
        raise ValueError(
            "FailureVector contract evidence expands authority: " + ", ".join(expanded)
        )

    return {
        "collection_status": _string(payload.get("collection_status")) or "collected",
        "status": _string(payload.get("status")) or "failure_vector_contract_evidence_observed",
        "source": _string(payload.get("source")) or "trajectory.failure_vector_contract",
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
        "decision_boundary": denied,
    }


def _proof_commands(benchmark_report: Mapping[str, Any]) -> list[str]:
    commands: set[str] = set()
    for scenario in _as_list(benchmark_report.get("scenarios")):
        patch_score = _as_dict(_as_dict(scenario).get("patch_score"))
        for command in _as_list(patch_score.get("proof_requirements")):
            rendered = _string(command)
            if rendered:
                commands.add(rendered)
    return sorted(commands)


def _combined_proof_commands(*reports: Mapping[str, Any]) -> list[str]:
    commands: set[str] = set()
    for report in reports:
        commands.update(_proof_commands(report))
    return sorted(commands)


def _oracle_supports_pattern(
    *,
    benchmark_report: Mapping[str, Any],
    failure_class: str,
    action: str,
) -> bool:
    if not _benchmark_contract_proven(benchmark_report):
        return False

    for scenario in _as_list(benchmark_report.get("scenarios")):
        row = _as_dict(scenario)
        if _string(row.get("scenario_type")) != "oracle_pass" or not _bool(row.get("passed")):
            continue

        patch_score = _as_dict(row.get("patch_score"))
        verifier = _as_dict(row.get("protected_verifier_result"))
        if (
            _string(patch_score.get("classification")) == failure_class
            and _string(patch_score.get("strategy")) == action
            and _decision_status(patch_score) == "candidate_for_protected_verification"
            and _decision_status(verifier) == "structurally_verified_candidate"
        ):
            return True

    return False


def _live_oracle_supports_pattern(
    *,
    live_benchmark_report: Mapping[str, Any],
    failure_class: str,
    action: str,
) -> bool:
    if not _live_contract_proven(live_benchmark_report):
        return False

    for item in _as_list(live_benchmark_report.get("scenarios")):
        scenario = _as_dict(item)
        if (
            _string(scenario.get("scenario_type")) != "oracle_pass"
            or not _bool(scenario.get("passed"))
            or _string(scenario.get(VERIFICATION_EVIDENCE_SOURCE)) != LIVE_EVIDENCE_SOURCE
        ):
            continue

        patch_score = _as_dict(scenario.get("patch_score"))
        verifier = _as_dict(scenario.get("protected_verifier_result"))
        evidence = _as_dict(scenario.get("isolated_proof_evidence"))
        boundary = _as_dict(evidence.get("decision_boundary"))
        if (
            _string(patch_score.get("classification")) == failure_class
            and _string(patch_score.get("strategy")) == action
            and _decision_status(patch_score) == "candidate_for_protected_verification"
            and _decision_status(verifier) == "structurally_verified_candidate"
            and _string(evidence.get("status")) == "passed"
            and _bool(boundary.get(GIT_INVENTORY_VERIFIED))
        ):
            return True

    return False


def _safe_fix_history(
    *,
    pattern_insights: Mapping[str, Any],
    benchmark_report: Mapping[str, Any],
    live_benchmark_report: Mapping[str, Any],
) -> list[JsonObject]:
    records: list[JsonObject] = []
    for item in _as_list(pattern_insights.get("recurring_safe_fix_patterns")):
        pattern = _as_dict(item)
        failure_class = _string(pattern.get("failure_class") or "unknown")
        action = _string(pattern.get("action") or "unknown")
        fixture_supported = _oracle_supports_pattern(
            benchmark_report=benchmark_report,
            failure_class=failure_class,
            action=action,
        )
        live_supported = _live_oracle_supports_pattern(
            live_benchmark_report=live_benchmark_report,
            failure_class=failure_class,
            action=action,
        )
        supported = fixture_supported or live_supported

        if live_supported:
            proof_state = LIVE_PROOF_STATE
            evidence_source = LIVE_EVIDENCE_SOURCE
            reason = (
                "A repeated trajectory pattern has matching Git-grounded "
                "isolated-proof oracle evidence, but automation remains disabled."
            )
        elif fixture_supported:
            proof_state = "benchmark_supported_candidate"
            evidence_source = FIXTURE_EVIDENCE_SOURCE
            reason = (
                "A repeated trajectory pattern has matching fixture benchmark "
                "oracle evidence, but automation remains disabled."
            )
        else:
            proof_state = "trajectory_observed_only"
            evidence_source = "trajectory_only"
            reason = "Trajectory repetition exists without matching benchmark proof."

        records.append(
            {
                "failure_class": failure_class,
                "action": action,
                "trajectory_count": _int(pattern.get("count")),
                "benchmark_supported": supported,
                "fixture_supported": fixture_supported,
                "live_proof_supported": live_supported,
                "evidence_source": evidence_source,
                "proof_state": proof_state,
                "automation_allowed": False,
                "reason": reason,
            }
        )
    return records


def _review_first_patterns(pattern_insights: Mapping[str, Any]) -> list[JsonObject]:
    records: list[JsonObject] = []
    for item in _as_list(pattern_insights.get("recurring_review_first_surfaces")):
        pattern = _as_dict(item)
        records.append(
            {
                "pattern_kind": "review_first_surface",
                "surface": _string(pattern.get("value") or "unknown"),
                "trajectory_count": _int(pattern.get("count")),
                "decision": "review_first",
                "automation_allowed": False,
            }
        )
    return records


def _benchmark_rejections(benchmark_report: Mapping[str, Any]) -> list[JsonObject]:
    records: list[JsonObject] = []
    for item in _as_list(benchmark_report.get("scenarios")):
        scenario = _as_dict(item)
        scenario_type = _string(scenario.get("scenario_type"))
        if scenario_type not in {"nop_fail", "unsafe_patch_fail"}:
            continue
        if not _bool(scenario.get("passed")):
            continue

        records.append(
            {
                "pattern_kind": "benchmark_rejection",
                "scenario_id": _string(scenario.get("scenario_id")),
                "scenario_type": scenario_type,
                "evidence_source": FIXTURE_EVIDENCE_SOURCE,
                "patch_score_status": _decision_status(_as_dict(scenario.get("patch_score"))),
                "verifier_status": _decision_status(
                    _as_dict(scenario.get("protected_verifier_result"))
                ),
                "decision": "blocked_review_first",
                "automation_allowed": False,
            }
        )
    return records


def _live_benchmark_rejections(
    live_benchmark_report: Mapping[str, Any],
) -> list[JsonObject]:
    if not _live_contract_proven(live_benchmark_report):
        return []

    records: list[JsonObject] = []
    for item in _as_list(live_benchmark_report.get("scenarios")):
        scenario = _as_dict(item)
        scenario_type = _string(scenario.get("scenario_type"))
        if scenario_type not in {
            INVENTORY_CLAIM_MISMATCH_FAIL,
            PROOF_MUTATION_FAIL,
            NETWORK_BOUNDARY_REQUIRED_FAIL,
            UNCLAIMED_WRITE_FAIL,
            EVIDENCE_SHADOW_FAIL,
        }:
            continue
        if (
            not _bool(scenario.get("passed"))
            or _string(scenario.get(VERIFICATION_EVIDENCE_SOURCE)) != LIVE_EVIDENCE_SOURCE
        ):
            continue

        evidence = _as_dict(scenario.get("isolated_proof_evidence"))
        boundary = _as_dict(evidence.get("decision_boundary"))
        records.append(
            {
                "pattern_kind": "live_benchmark_rejection",
                "scenario_id": _string(scenario.get("scenario_id")),
                "scenario_type": scenario_type,
                "evidence_source": LIVE_EVIDENCE_SOURCE,
                "proof_evidence_status": _string(evidence.get("status")),
                GIT_INVENTORY_VERIFIED: _bool(boundary.get(GIT_INVENTORY_VERIFIED)),
                "verifier_status": _decision_status(
                    _as_dict(scenario.get("protected_verifier_result"))
                ),
                "decision": "blocked_review_first",
                "automation_allowed": False,
            }
        )
    return records


def _registry_denied(*, trusted_fingerprint: bool = False) -> JsonObject:
    denied: JsonObject = {
        "automatic_quarantine_allowed": False,
        "automatic_rerun_allowed": False,
        "current_failure_suppression_allowed": False,
        "automation_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }
    if trusted_fingerprint:
        denied.update(
            {
                "current_pr_decision_input": False,
                "patch_application_allowed": False,
            }
        )
    return denied


def _assert_registry_authority(
    value: Mapping[str, Any],
    *,
    denied: Mapping[str, Any],
    source: str,
    explicit: bool,
) -> None:
    expanded = [key for key in denied if _bool(value.get(key))]
    if expanded:
        raise ValueError(f"{source} expands authority: " + ", ".join(expanded))
    if explicit:
        omitted = [key for key in denied if value.get(key) is not False]
        if omitted:
            raise ValueError(f"{source} must explicitly deny authority: " + ", ".join(omitted))


def _lower_hex(value: Any, *, length: int, source: str) -> str:
    rendered = _string(value)
    if (
        len(rendered) != length
        or rendered != rendered.lower()
        or any(char not in "0123456789abcdef" for char in rendered)
    ):
        raise ValueError(f"{source} must be {length}-character lower-case hexadecimal")
    return rendered


def _trusted_registry_provenance(value: Any) -> list[JsonObject]:
    if not isinstance(value, list):
        raise ValueError(
            "producer-vetted flaky-test registry entry requires observation provenance"
        )

    normalized: list[JsonObject] = []
    seen: set[tuple[str, str, str]] = set()
    for raw_item in value:
        if not isinstance(raw_item, dict):
            raise ValueError("producer-vetted flaky-test registry provenance contains a non-object")
        if set(raw_item) != {"source_run_id", "source_head_sha", "outcome"}:
            raise ValueError(
                "producer-vetted flaky-test registry provenance fields are not supported"
            )

        source_run_id = _string(raw_item.get("source_run_id"))
        source_head_sha = _string(raw_item.get("source_head_sha"))
        outcome = _string(raw_item.get("outcome"))
        if not source_run_id or not source_head_sha:
            raise ValueError("producer-vetted flaky-test registry provenance is incomplete")
        if outcome not in ALLOWED_OUTCOMES:
            raise ValueError(
                "producer-vetted flaky-test registry provenance outcome is not supported"
            )

        provenance_tuple = (source_run_id, source_head_sha, outcome)
        if provenance_tuple in seen:
            raise ValueError(
                "producer-vetted flaky-test registry contains duplicate provenance tuples"
            )
        seen.add(provenance_tuple)
        normalized.append(
            {
                "source_run_id": source_run_id,
                "source_head_sha": source_head_sha,
                "outcome": outcome,
            }
        )

    if not normalized:
        raise ValueError(
            "producer-vetted flaky-test registry entry requires observation provenance"
        )
    return normalized


def _legacy_registry_entry(
    raw_item: Mapping[str, Any],
    *,
    denied: Mapping[str, Any],
) -> JsonObject:
    _assert_registry_authority(
        raw_item,
        denied=denied,
        source="flaky-test registry entry",
        explicit=False,
    )

    test_id = _string(raw_item.get("test_id"))
    fingerprint = _string(raw_item.get("fingerprint"))
    runs = _int(raw_item.get("observed_runs"))
    failures = _int(raw_item.get("observed_failures"))
    passes = _int(raw_item.get("observed_passes"))

    if _string(raw_item.get("classification")) != "flaky":
        raise ValueError("flaky-test registry entry must classify a flaky test")
    if not test_id or not fingerprint:
        raise ValueError("flaky-test registry entry requires test_id and fingerprint")
    if runs < 2 or failures < 1 or passes < 1:
        raise ValueError("flaky-test registry entry lacks mixed pass/fail observations")
    if _string(raw_item.get("decision")) != "instability_context_only":
        raise ValueError("flaky-test registry entry decision is not supported")
    if not _bool(raw_item.get("review_first")):
        raise ValueError("flaky-test registry entry must remain review-first")

    return {
        "test_id": test_id,
        "fingerprint": fingerprint,
        "classification": "flaky",
        "observed_runs": runs,
        "observed_failures": failures,
        "observed_passes": passes,
        "decision": "instability_context_only",
        "review_first": True,
        **denied,
    }


def _trusted_registry_entry(
    raw_item: Mapping[str, Any],
    *,
    denied: Mapping[str, Any],
    seen_fingerprints: set[str],
) -> JsonObject:
    _assert_registry_authority(
        raw_item,
        denied=denied,
        source="producer-vetted flaky-test registry entry",
        explicit=True,
    )

    forbidden_identity_fields = {
        "test_id",
        "classname",
        "name",
        "nodeid",
        "fingerprint",
    }
    present_forbidden = sorted(forbidden_identity_fields.intersection(raw_item))
    if present_forbidden:
        raise ValueError(
            "raw test identity cannot enter producer-vetted RepoMemory registry: "
            + ", ".join(present_forbidden)
        )

    fingerprint = _lower_hex(
        raw_item.get("test_fingerprint"),
        length=64,
        source="producer-vetted test fingerprint",
    )
    if fingerprint in seen_fingerprints:
        raise ValueError("producer-vetted flaky-test registry contains duplicate fingerprints")
    seen_fingerprints.add(fingerprint)

    if _string(raw_item.get("classification")) != "flaky":
        raise ValueError("producer-vetted flaky-test registry entry must classify a flaky test")
    if _string(raw_item.get("decision")) != "instability_context_only":
        raise ValueError("producer-vetted flaky-test registry entry decision is not supported")
    if raw_item.get("review_first") is not True:
        raise ValueError("producer-vetted flaky-test registry entry must remain review-first")

    provenance = _trusted_registry_provenance(raw_item.get("observation_provenance"))
    outcomes = [_string(item.get("outcome")) for item in provenance]
    expected = {
        "observed_runs": len(provenance),
        "decisive_observation_count": (
            outcomes.count("passed") + outcomes.count("failed") + outcomes.count("error")
        ),
        "observed_passes": outcomes.count("passed"),
        "observed_failures": outcomes.count("failed") + outcomes.count("error"),
        "observed_errors": outcomes.count("error"),
        "observed_skipped": outcomes.count("skipped"),
    }
    declared = {key: _int(raw_item.get(key)) for key in expected}
    if declared != expected:
        raise ValueError("producer-vetted flaky-test registry entry counts are inconsistent")
    if expected["observed_passes"] < 1 or expected["observed_failures"] < 1:
        raise ValueError(
            "producer-vetted flaky-test registry entry lacks mixed pass/fail observations"
        )

    return {
        "test_fingerprint": fingerprint,
        "classification": "flaky",
        **declared,
        "observation_provenance": provenance,
        "decision": "instability_context_only",
        "review_first": True,
        **denied,
    }


def _flaky_test_registry(evidence: Mapping[str, Any]) -> JsonObject:
    payload = _as_dict(evidence)
    if not payload:
        denied = _registry_denied()
        return {
            "collection_status": "not_collected",
            "status": "not_collected",
            "entries": [],
            "entry_count": 0,
            "note": "No flaky-test evidence source is connected to RepoMemory yet.",
            "decision_boundary": denied,
        }

    if _string(payload.get("schema_version")) != "sdetkit.flaky_test_registry_evidence.v1":
        raise ValueError("flaky-test registry evidence schema is not supported")
    if _string(payload.get("collection_status")) != "collected":
        raise ValueError("flaky-test registry evidence must be collected before ingestion")
    if _string(payload.get("status")) != "advisory_registry_collected":
        raise ValueError("flaky-test registry evidence status is not supported")

    source = _as_dict(payload.get("source"))
    source_kind = _string(source.get("kind"))
    source_reference = _string(source.get("reference"))
    classification_schema = _string(source.get("classification_schema"))
    if source_kind not in {"operator_review_input", "trusted_main_artifact"}:
        raise ValueError("flaky-test registry evidence source kind is not supported")
    if not source_reference:
        raise ValueError("flaky-test registry evidence source reference is required")

    trusted_fingerprint = (
        source_kind == "trusted_main_artifact"
        and classification_schema == TRUSTED_TEST_OBSERVATION_CLASSIFICATION_SCHEMA
    )
    legacy_classification = classification_schema == LEGACY_FLAKY_CLASSIFICATION_SCHEMA
    if not trusted_fingerprint and not legacy_classification:
        raise ValueError("flaky-test registry classification schema is not supported")
    if source_kind == "operator_review_input" and not legacy_classification:
        raise ValueError("producer-vetted flaky-test registry requires trusted-main provenance")

    if trusted_fingerprint:
        if source.get("input_read_only") is not True:
            raise ValueError("flaky-test registry evidence input must be read-only")
        if source.get("commands_executed_by_reader") is not False:
            raise ValueError("flaky-test registry evidence reader cannot execute commands")
    else:
        if not _bool(source.get("input_read_only")):
            raise ValueError("flaky-test registry evidence input must be read-only")
        if _bool(source.get("commands_executed_by_reader")):
            raise ValueError("flaky-test registry evidence reader cannot execute commands")

    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list):
        raise ValueError("flaky-test registry evidence must contain an entries array")

    observation_status = _string(source.get("observation_status"))
    if source_kind == "trusted_main_artifact":
        if _string(source.get("workflow")) != "RepoMemory Profile History":
            raise ValueError("trusted-main flaky-test registry workflow is not supported")
        run_id = _string(source.get("run_id"))
        head_sha = _string(source.get("head_sha"))
        if not run_id or not head_sha:
            raise ValueError("trusted-main flaky-test registry provenance is incomplete")

        if trusted_fingerprint:
            _lower_hex(
                head_sha,
                length=40,
                source="producer-vetted registry source head SHA",
            )
            if _string(source.get("identity_kind")) != TRUSTED_FLAKY_IDENTITY_KIND:
                raise ValueError(
                    "producer-vetted flaky-test registry identity kind is not supported"
                )
            if source.get("producer_vetted") is not True:
                raise ValueError("producer-vetted flaky-test registry must be producer-vetted")
            if source.get("raw_test_identity_emitted") is not False:
                raise ValueError(
                    "producer-vetted flaky-test registry cannot emit raw test identity"
                )
            if observation_status not in {
                NO_TEST_OBSERVATIONS,
                PRODUCER_VETTED_OBSERVATIONS,
            }:
                raise ValueError(
                    "producer-vetted flaky-test registry observation status is not supported"
                )
            observations_collected = source.get("observations_collected")
            if observation_status == NO_TEST_OBSERVATIONS:
                if raw_entries or observations_collected is not False:
                    raise ValueError(
                        "producer-vetted no-observation registry cannot contain entries"
                    )
            elif not raw_entries or observations_collected is not True:
                raise ValueError("producer-vetted populated registry must claim observations")
        else:
            if observation_status != NO_TEST_OBSERVATIONS:
                raise ValueError(
                    "trusted-main flaky-test registry observation status is not supported"
                )
            if _bool(source.get("observations_collected")):
                raise ValueError("trusted-main no-observation registry cannot claim observations")

    denied = _registry_denied(trusted_fingerprint=trusted_fingerprint)
    boundary = _as_dict(payload.get("decision_boundary"))
    _assert_registry_authority(
        boundary,
        denied=denied,
        source="flaky-test registry evidence",
        explicit=trusted_fingerprint,
    )

    entries: list[JsonObject] = []
    seen_fingerprints: set[str] = set()
    for raw_item in raw_entries:
        if not isinstance(raw_item, dict):
            raise ValueError("flaky-test registry evidence contains a non-object entry")
        if trusted_fingerprint:
            entries.append(
                _trusted_registry_entry(
                    raw_item,
                    denied=denied,
                    seen_fingerprints=seen_fingerprints,
                )
            )
        else:
            entries.append(
                _legacy_registry_entry(
                    raw_item,
                    denied=denied,
                )
            )

    if trusted_fingerprint:
        entries.sort(key=lambda item: str(item["test_fingerprint"]))
    else:
        entries.sort(key=lambda item: (item["test_id"], item["fingerprint"]))

    summary = _as_dict(payload.get("summary"))
    if _int(summary.get("entry_count")) != len(entries):
        raise ValueError("flaky-test registry evidence summary entry count is inconsistent")
    if _int(summary.get("flaky_test_count")) != len(entries):
        raise ValueError("flaky-test registry evidence summary flaky count is inconsistent")
    if source_kind == "trusted_main_artifact" and not trusted_fingerprint and entries:
        raise ValueError("trusted-main no-observation registry cannot contain entries")

    normalized_source: JsonObject = {
        "kind": source_kind,
        "reference": source_reference,
        "classification_schema": classification_schema,
        "input_read_only": True,
        "commands_executed_by_reader": False,
    }
    if source_kind == "trusted_main_artifact":
        normalized_source.update(
            {
                "workflow": _string(source.get("workflow")),
                "run_id": _string(source.get("run_id")),
                "head_sha": _string(source.get("head_sha")),
                "observation_status": observation_status,
                "observations_collected": bool(source.get("observations_collected")),
            }
        )
    if trusted_fingerprint:
        normalized_source.update(
            {
                "identity_kind": TRUSTED_FLAKY_IDENTITY_KIND,
                "producer_vetted": True,
                "raw_test_identity_emitted": False,
            }
        )

    return {
        "collection_status": "collected",
        "status": "advisory_registry_collected",
        "source": normalized_source,
        "entries": entries,
        "entry_count": len(entries),
        "note": _string(payload.get("note"))
        or (
            "Flaky-test evidence is advisory context only and cannot suppress "
            "a current failing contract."
        ),
        "decision_boundary": denied,
    }


def _escalation_rules() -> list[JsonObject]:
    return [
        {
            "rule_id": "current_security_evidence_review_first",
            "when": "a current security review or code-scanning finding exists",
            "decision": "review_first",
            "automation_allowed": False,
        },
        {
            "rule_id": "unsupported_safe_pattern_advisory_only",
            "when": "a repeated safe-fix pattern lacks passing oracle benchmark evidence",
            "decision": "keep_advisory",
            "automation_allowed": False,
        },
        {
            "rule_id": "structural_proof_not_semantic_equivalence",
            "when": "protected structural verification passes without isolated runtime proof",
            "decision": "do_not_authorize_automation",
            "automation_allowed": False,
        },
        {
            "rule_id": "live_proof_support_remains_advisory",
            "when": "a Git-grounded isolated-proof oracle scenario passes",
            "decision": "keep_advisory",
            "automation_allowed": False,
        },
        {
            "rule_id": "flaky_history_never_suppresses_current_failure",
            "when": "read-only flaky-test instability evidence is collected",
            "decision": "review_first",
            "automation_allowed": False,
        },
    ]


def build_repo_memory_profile(
    *,
    pattern_insights: Mapping[str, Any],
    benchmark_report: Mapping[str, Any],
    live_benchmark_report: Mapping[str, Any] | None = None,
    flaky_test_registry_evidence: Mapping[str, Any] | None = None,
    controlled_candidate_validation_evidence: Mapping[str, Any] | None = None,
) -> JsonObject:
    live_report = dict(live_benchmark_report or {})
    flaky_registry = _flaky_test_registry(flaky_test_registry_evidence or {})
    controlled_validation = _controlled_candidate_validation(
        controlled_candidate_validation_evidence or {}
    )
    safety_gate_evidence = _safety_gate_evidence(pattern_insights)
    trajectory_authority_evidence = _trajectory_authority_evidence(pattern_insights)
    failure_vector_contract_evidence = _failure_vector_contract_evidence(pattern_insights)
    benchmark_proven = _benchmark_contract_proven(benchmark_report)
    live_proven = _live_contract_proven(live_report)
    safe_fix_history = _safe_fix_history(
        pattern_insights=pattern_insights,
        benchmark_report=benchmark_report,
        live_benchmark_report=live_report,
    )
    review_first = _review_first_patterns(pattern_insights)
    benchmark_rejections = _benchmark_rejections(benchmark_report)
    live_rejections = _live_benchmark_rejections(live_report)
    supported_candidates = [
        item for item in safe_fix_history if _bool(item.get("benchmark_supported"))
    ]
    live_supported_candidates = [
        item for item in safe_fix_history if _bool(item.get("live_proof_supported"))
    ]
    live_evidence = _as_dict(live_report.get("live_evidence"))

    if live_proven:
        profile_status = LIVE_PROFILE_STATUS
    elif benchmark_proven:
        profile_status = "benchmark_supported_memory"
    else:
        profile_status = "observation_only"

    evidence_modes = []
    if benchmark_proven:
        evidence_modes.append(FIXTURE_EVIDENCE_SOURCE)
    if live_proven:
        evidence_modes.append(LIVE_EVIDENCE_SOURCE)

    unproven_boundaries = [
        "semantic equivalence",
        "external filesystem and process escape prevention",
        "network-isolated proof execution",
        "broader remediation classes beyond formatting-only candidates",
    ]
    if not live_proven:
        unproven_boundaries.insert(1, "isolated proof-command execution")

    return {
        "schema_version": SCHEMA_VERSION,
        "profile_status": profile_status,
        "memory_mode": "read_only_profile",
        "inputs": {
            "trajectory_pattern_schema": _string(pattern_insights.get("schema_version")),
            "trajectory_record_count": _int(pattern_insights.get("record_count")),
            "benchmark_schema": _string(benchmark_report.get("schema_version")),
            "benchmark_status": _string(benchmark_report.get("status")),
            "benchmark_contract_proven": benchmark_proven,
            "fixture_contract_proven": benchmark_proven,
            "live_benchmark_schema": _string(live_report.get("schema_version")),
            "live_benchmark_status": _string(live_report.get("status")),
            "live_report_mode": _string(live_report.get("report_mode")),
            "live_contract_proven": live_proven,
            "safety_gate_evidence_record_count": _int(safety_gate_evidence.get("record_count")),
            "trajectory_authority_record_count": _int(
                trajectory_authority_evidence.get("record_count")
            ),
            "failure_vector_contract_evidence_record_count": _int(
                failure_vector_contract_evidence.get("record_count")
            ),
        },
        "command_profile": {
            "source": "replayable_benchmark_harness",
            "evidence_modes": evidence_modes,
            "observed_proof_commands": _combined_proof_commands(
                benchmark_report,
                live_report,
            ),
            "commands_executed_by_repo_memory": False,
            "note": (
                "Commands are stored from benchmark evidence only; "
                "RepoMemory does not execute proof commands."
            ),
        },
        "proof_provenance": {
            "fixture_contract_proven": benchmark_proven,
            "live_contract_proven": live_proven,
            "live_evidence_source": LIVE_EVIDENCE_SOURCE if live_proven else "",
            "git_verified_scenario_count": _int(live_evidence.get("git_inventory_verified_count")),
            "expected_failed_scenario_count": _int(
                live_evidence.get(EXPECTED_FAILED_EVIDENCE_COUNT)
            ),
            "network_boundary_blocked_scenario_count": _int(
                live_evidence.get(NETWORK_BOUNDARY_BLOCKED_COUNT)
            ),
            "anti_cheat_rejection_scenario_count": _int(
                live_evidence.get(ANTI_CHEAT_REJECTION_COUNT)
            ),
        },
        "failure_patterns": {
            "review_first": review_first,
            "benchmark_rejections": benchmark_rejections,
            "live_rejections": live_rejections,
        },
        "safe_fix_history": safe_fix_history,
        "known_safe_candidate_count": len(supported_candidates),
        "live_safe_candidate_count": len(live_supported_candidates),
        "controlled_candidate_validation": controlled_validation,
        "safety_gate_evidence": safety_gate_evidence,
        "trajectory_authority_evidence": trajectory_authority_evidence,
        "failure_vector_contract_evidence": failure_vector_contract_evidence,
        "flaky_test_registry": flaky_registry,
        "escalation_rules": _escalation_rules(),
        "unproven_boundaries": unproven_boundaries,
        "decision_boundary": {
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
            "reason": (
                "RepoMemory records observed, fixture-supported, and "
                "Git-grounded live-proof-supported patterns; it does not "
                "authorize remediation."
            ),
        },
        "recommended_next_action": (
            "Keep trusted accepted-main observation history advisory-only and wire "
            "producer-vetted fingerprint registry population through the trusted-main "
            "workflow before PR Quality visibility."
        ),
    }


def render_markdown(profile: Mapping[str, Any]) -> str:
    inputs = _as_dict(profile.get("inputs"))
    commands = _as_dict(profile.get("command_profile"))
    provenance = _as_dict(profile.get("proof_provenance"))
    failure_patterns = _as_dict(profile.get("failure_patterns"))
    controlled = _as_dict(profile.get("controlled_candidate_validation"))
    safety_gate = _as_dict(profile.get("safety_gate_evidence"))
    safety_boundary = _as_dict(safety_gate.get("decision_boundary"))
    trajectory_authority = _as_dict(profile.get("trajectory_authority_evidence"))
    trajectory_authority_boundary = _as_dict(trajectory_authority.get("decision_boundary"))
    vector_contract = _as_dict(profile.get("failure_vector_contract_evidence"))
    vector_contract_boundary = _as_dict(vector_contract.get("decision_boundary"))
    flaky = _as_dict(profile.get("flaky_test_registry"))
    flaky_source = _as_dict(flaky.get("source"))
    boundary = _as_dict(profile.get("decision_boundary"))

    lines = [
        "# RepoMemory profile",
        "",
        f"- Schema: `{_string(profile.get('schema_version'))}`",
        f"- Status: `{_string(profile.get('profile_status'))}`",
        f"- Mode: `{_string(profile.get('memory_mode'))}`",
        f"- Trajectory records observed: `{_int(inputs.get('trajectory_record_count'))}`",
        (
            "- Benchmark contract proven: "
            f"`{str(_bool(inputs.get('benchmark_contract_proven'))).lower()}`"
        ),
        (
            "- Live Git-grounded contract proven: "
            f"`{str(_bool(inputs.get('live_contract_proven'))).lower()}`"
        ),
        f"- Known safe candidates: `{_int(profile.get('known_safe_candidate_count'))}`",
        f"- Live safe candidates: `{_int(profile.get('live_safe_candidate_count'))}`",
        "",
        "## Proof provenance",
        "",
        (
            "- Fixture-declared contract proven: "
            f"`{str(_bool(provenance.get('fixture_contract_proven'))).lower()}`"
        ),
        (
            "- Live Git-grounded contract proven: "
            f"`{str(_bool(provenance.get('live_contract_proven'))).lower()}`"
        ),
        f"- Live evidence source: `{_string(provenance.get('live_evidence_source'))}`",
        (
            "- Git inventory verified scenarios: "
            f"`{_int(provenance.get('git_verified_scenario_count'))}`"
        ),
        (
            "- Expected failed-evidence scenarios: "
            f"`{_int(provenance.get('expected_failed_scenario_count'))}`"
        ),
        (
            "- Network boundary blocked scenarios: "
            f"`{_int(provenance.get('network_boundary_blocked_scenario_count'))}`"
        ),
        (
            "- Anti-cheat rejection scenarios: "
            f"`{_int(provenance.get('anti_cheat_rejection_scenario_count'))}`"
        ),
        "",
        "## Command profile",
        "",
    ]

    proof_commands = [_string(item) for item in _as_list(commands.get("observed_proof_commands"))]
    if proof_commands:
        lines.extend(f"- `{command}`" for command in proof_commands)
    else:
        lines.append("- none observed")
    lines.append("- RepoMemory executes commands: `false`")

    lines.extend(["", "## Safe-fix history", ""])
    safe_history = [_as_dict(item) for item in _as_list(profile.get("safe_fix_history"))]
    if safe_history:
        for item in safe_history:
            lines.append(
                f"- class=`{_string(item.get('failure_class'))}`, "
                f"action=`{_string(item.get('action'))}`, "
                f"trajectory_count=`{_int(item.get('trajectory_count'))}`, "
                f"proof_state=`{_string(item.get('proof_state'))}`, "
                f"evidence=`{_string(item.get('evidence_source'))}`, "
                "automation_allowed=`false`"
            )
    else:
        lines.append("- none observed")

    lines.extend(["", "## Review-first failure patterns", ""])
    review_first = [_as_dict(item) for item in _as_list(failure_patterns.get("review_first"))]
    rejections = [_as_dict(item) for item in _as_list(failure_patterns.get("benchmark_rejections"))]
    live_rejections = [_as_dict(item) for item in _as_list(failure_patterns.get("live_rejections"))]

    if review_first:
        for item in review_first:
            lines.append(
                f"- recurring surface=`{_string(item.get('surface'))}`, "
                f"trajectory_count=`{_int(item.get('trajectory_count'))}`"
            )
    if rejections:
        for item in rejections:
            lines.append(
                f"- benchmark scenario=`{_string(item.get('scenario_id'))}`, "
                f"type=`{_string(item.get('scenario_type'))}`, "
                "decision=`blocked_review_first`"
            )
    if live_rejections:
        for item in live_rejections:
            lines.append(
                f"- live benchmark scenario=`{_string(item.get('scenario_id'))}`, "
                f"type=`{_string(item.get('scenario_type'))}`, "
                f"evidence=`{_string(item.get('evidence_source'))}`, "
                "decision=`blocked_review_first`"
            )
    if not review_first and not rejections and not live_rejections:
        lines.append("- none observed")

    lines.extend(
        [
            "",
            "## Controlled candidate validation evidence",
            "",
            f"- Collection status: `{_string(controlled.get('collection_status'))}`",
            f"- Status: `{_string(controlled.get('status'))}`",
            f"- Scenarios passed: `{_int(controlled.get('passed_count'))}/{_int(controlled.get('scenario_count'))}`",
            (
                "- Structurally verified scenarios: "
                f"`{_int(controlled.get('structurally_verified_count'))}`"
            ),
            f"- Review-first scenarios: `{_int(controlled.get('review_first_count'))}`",
            (
                "- Current PR decision input: "
                f"`{str(_bool(controlled.get('current_pr_decision_input'))).lower()}`"
            ),
            (
                "- Automation allowed by controlled validation: "
                f"`{str(_bool(_as_dict(controlled.get('decision_boundary')).get('automation_allowed'))).lower()}`"
            ),
            (
                "- Merge authorized by controlled validation: "
                f"`{str(_bool(_as_dict(controlled.get('decision_boundary')).get('merge_authorized'))).lower()}`"
            ),
        ]
    )

    lines.extend(
        [
            "",
            "## SafetyGate trajectory evidence",
            "",
            f"- Collection status: `{_string(safety_gate.get('collection_status'))}`",
            f"- Status: `{_string(safety_gate.get('status'))}`",
            f"- Records: `{_int(safety_gate.get('record_count'))}`",
            f"- Safe-fix allowed records: `{_int(safety_gate.get('safe_fix_allowed_count'))}`",
            f"- Review-first records: `{_int(safety_gate.get('review_first_count'))}`",
            f"- Reporting-only records: `{_int(safety_gate.get('reporting_only_count'))}`",
            (
                "- Automation allowed by SafetyGate evidence: "
                f"`{str(_bool(safety_boundary.get('automation_allowed'))).lower()}`"
            ),
            (
                "- Patch application allowed by SafetyGate evidence: "
                f"`{str(_bool(safety_boundary.get('patch_application_allowed'))).lower()}`"
            ),
            (
                "- Merge authorized by SafetyGate evidence: "
                f"`{str(_bool(safety_boundary.get('merge_authorized'))).lower()}`"
            ),
            (
                "- Semantic equivalence proven by SafetyGate evidence: "
                f"`{str(_bool(safety_boundary.get('semantic_equivalence_proven'))).lower()}`"
            ),
        ]
    )

    lines.extend(
        [
            "",
            "## FailureVector contract trajectory evidence",
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
                "- Patch application allowed by FailureVector contract evidence: "
                f"`{str(_bool(vector_contract_boundary.get('patch_application_allowed'))).lower()}`"
            ),
            (
                "- Security dismissal allowed by FailureVector contract evidence: "
                f"`{str(_bool(vector_contract_boundary.get('security_dismissal_allowed'))).lower()}`"
            ),
            (
                "- Merge authorized by FailureVector contract evidence: "
                f"`{str(_bool(vector_contract_boundary.get('merge_authorized'))).lower()}`"
            ),
            (
                "- Semantic equivalence claimed by FailureVector contract evidence: "
                f"`{str(_bool(vector_contract_boundary.get('semantic_equivalence_claim'))).lower()}`"
            ),
            "",
            "## Trajectory authority boundary evidence",
            "",
            f"- Collection status: `{_string(trajectory_authority.get('collection_status'))}`",
            f"- Status: `{_string(trajectory_authority.get('status'))}`",
            f"- Records: `{_int(trajectory_authority.get('record_count'))}`",
            f"- Review-first records: `{_int(trajectory_authority.get('review_first_count'))}`",
            (
                "- Auto-fix evidence records: "
                f"`{_int(trajectory_authority.get('auto_fix_allowed_count'))}`"
            ),
            (
                "- Reporting-only records: "
                f"`{_int(trajectory_authority.get('reporting_only_count'))}`"
            ),
            (
                "- Patch automation allowed by trajectory authority: "
                f"`{str(_bool(trajectory_authority_boundary.get('patch_application_allowed'))).lower()}`"
            ),
            (
                "- Security dismissal allowed by trajectory authority: "
                f"`{str(_bool(trajectory_authority_boundary.get('automatic_dismissal_allowed'))).lower()}`"
            ),
            (
                "- Merge authorized by trajectory authority: "
                f"`{str(_bool(trajectory_authority_boundary.get('merge_authorized'))).lower()}`"
            ),
            "",
            "## Flaky test registry",
            "",
            f"- Collection status: `{_string(flaky.get('collection_status'))}`",
            f"- Status: `{_string(flaky.get('status'))}`",
            f"- Source kind: `{_string(flaky_source.get('kind')) or 'not_reported'}`",
            (
                "- Observation status: "
                f"`{_string(flaky_source.get('observation_status')) or 'not_reported'}`"
            ),
            f"- Entries: `{len(_as_list(flaky.get('entries')))}`",
            (
                "- Automatic quarantine allowed: "
                f"`{str(_bool(_as_dict(flaky.get('decision_boundary')).get('automatic_quarantine_allowed'))).lower()}`"
            ),
            (
                "- Current failure suppression allowed: "
                f"`{str(_bool(_as_dict(flaky.get('decision_boundary')).get('current_failure_suppression_allowed'))).lower()}`"
            ),
            (
                "- Automation allowed by flaky-test history: "
                f"`{str(_bool(_as_dict(flaky.get('decision_boundary')).get('automation_allowed'))).lower()}`"
            ),
            "",
            "## Escalation rules",
            "",
        ]
    )
    for rule in _as_list(profile.get("escalation_rules")):
        item = _as_dict(rule)
        lines.append(
            f"- `{_string(item.get('rule_id'))}`: "
            f"decision=`{_string(item.get('decision'))}`, automation_allowed=`false`"
        )

    lines.extend(["", "## Unproven boundaries", ""])
    for item in _as_list(profile.get("unproven_boundaries")):
        lines.append(f"- {_string(item)}")

    lines.extend(
        [
            "",
            "## Boundary",
            "",
            f"- Automation allowed: `{str(_bool(boundary.get('automation_allowed'))).lower()}`",
            f"- Merge authorized: `{str(_bool(boundary.get('merge_authorized'))).lower()}`",
            (
                "- Semantic equivalence proven: "
                f"`{str(_bool(boundary.get('semantic_equivalence_proven'))).lower()}`"
            ),
            f"- Next: {_string(profile.get('recommended_next_action'))}",
            "",
        ]
    )
    return "\n".join(lines)


def write_profile(profile: Mapping[str, Any], *, out_dir: Path) -> dict[str, str]:
    json_path = out_dir / PROFILE_JSON
    markdown_path = out_dir / PROFILE_MD
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(profile), encoding="utf-8")
    return {
        "repo_memory_profile_json": json_path.as_posix(),
        "repo_memory_profile_markdown": markdown_path.as_posix(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.repo_memory")
    parser.add_argument("--pattern-insights", type=Path, required=True)
    parser.add_argument("--benchmark-report", type=Path, required=True)
    parser.add_argument("--live-benchmark-report", type=Path)
    parser.add_argument("--flaky-test-registry-evidence", type=Path)
    parser.add_argument("--controlled-candidate-validation-evidence", type=Path)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        profile = build_repo_memory_profile(
            pattern_insights=_read_json(args.pattern_insights),
            benchmark_report=_read_json(args.benchmark_report),
            live_benchmark_report=(
                _read_json(args.live_benchmark_report) if args.live_benchmark_report else None
            ),
            flaky_test_registry_evidence=(
                _read_json(args.flaky_test_registry_evidence)
                if args.flaky_test_registry_evidence
                else None
            ),
            controlled_candidate_validation_evidence=(
                _read_json(args.controlled_candidate_validation_evidence)
                if args.controlled_candidate_validation_evidence
                else None
            ),
        )
        write_profile(profile, out_dir=args.out_dir)
    except json.JSONDecodeError:
        print("error=invalid_json")
        return 2
    except OSError:
        print("error=input_io_failure")
        return 2
    except ValueError:
        print("error=input_validation_failed")
        return 2

    if args.format == "json":
        print(
            json.dumps(
                {
                    "artifacts": {
                        "repo_memory_profile_json": PROFILE_JSON,
                        "repo_memory_profile_markdown": PROFILE_MD,
                    },
                    "status": "repo_memory_profile_written",
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(f"repo_memory_profile_json: {PROFILE_JSON}")
        print(f"repo_memory_profile_markdown: {PROFILE_MD}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
