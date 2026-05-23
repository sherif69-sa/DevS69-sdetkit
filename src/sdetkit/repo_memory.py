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

SCHEMA_VERSION = "sdetkit.repo_memory.v5"
DEFAULT_OUT_DIR = Path("build") / "repo-memory"
PROFILE_JSON = "repo-memory-profile.json"
PROFILE_MD = "repo-memory-profile.md"

FIXTURE_EVIDENCE_SOURCE = "_".join(("fixture", "declared"))
LIVE_PROFILE_STATUS = "_".join(("live", "proof", "supported", "memory"))
LIVE_PROOF_STATE = "_".join(("live", "proof", "supported", "candidate"))
GIT_INVENTORY_VERIFIED = "_".join(("git", "inventory", "verified"))
EXPECTED_FAILED_EVIDENCE_COUNT = "_".join(("expected", "failed", "evidence", "count"))

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


def _flaky_test_registry(evidence: Mapping[str, Any]) -> JsonObject:
    denied = {
        "automatic_quarantine_allowed": False,
        "automatic_rerun_allowed": False,
        "current_failure_suppression_allowed": False,
        "automation_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }
    payload = _as_dict(evidence)
    if not payload:
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
    if source_kind not in {"operator_review_input", "trusted_main_artifact"}:
        raise ValueError("flaky-test registry evidence source kind is not supported")
    if not source_reference:
        raise ValueError("flaky-test registry evidence source reference is required")
    if not _bool(source.get("input_read_only")):
        raise ValueError("flaky-test registry evidence input must be read-only")
    if _bool(source.get("commands_executed_by_reader")):
        raise ValueError("flaky-test registry evidence reader cannot execute commands")

    boundary = _as_dict(payload.get("decision_boundary"))
    expanded = [key for key in denied if _bool(boundary.get(key))]
    if expanded:
        raise ValueError("flaky-test registry evidence expands authority: " + ", ".join(expanded))

    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list):
        raise ValueError("flaky-test registry evidence must contain an entries array")

    entries: list[JsonObject] = []
    for raw_item in raw_entries:
        if not isinstance(raw_item, dict):
            raise ValueError("flaky-test registry evidence contains a non-object entry")

        item_expanded = [key for key in denied if _bool(raw_item.get(key))]
        if item_expanded:
            raise ValueError(
                "flaky-test registry entry expands authority: " + ", ".join(item_expanded)
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

        entries.append(
            {
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
        )

    entries.sort(key=lambda item: (item["test_id"], item["fingerprint"]))
    summary = _as_dict(payload.get("summary"))
    if _int(summary.get("entry_count")) != len(entries):
        raise ValueError("flaky-test registry evidence summary entry count is inconsistent")
    if _int(summary.get("flaky_test_count")) != len(entries):
        raise ValueError("flaky-test registry evidence summary flaky count is inconsistent")

    return {
        "collection_status": "collected",
        "status": "advisory_registry_collected",
        "source": {
            "kind": source_kind,
            "reference": source_reference,
            "classification_schema": _string(source.get("classification_schema")),
            "input_read_only": True,
            "commands_executed_by_reader": False,
        },
        "entries": entries,
        "entry_count": len(entries),
        "note": (
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
) -> JsonObject:
    live_report = dict(live_benchmark_report or {})
    flaky_registry = _flaky_test_registry(flaky_test_registry_evidence or {})
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
            "Surface runtime-proof and anti-cheat artifacts in PR Quality before any automation wiring."
        ),
    }


def render_markdown(profile: Mapping[str, Any]) -> str:
    inputs = _as_dict(profile.get("inputs"))
    commands = _as_dict(profile.get("command_profile"))
    provenance = _as_dict(profile.get("proof_provenance"))
    failure_patterns = _as_dict(profile.get("failure_patterns"))
    flaky = _as_dict(profile.get("flaky_test_registry"))
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
            "## Flaky test registry",
            "",
            f"- Collection status: `{_string(flaky.get('collection_status'))}`",
            f"- Status: `{_string(flaky.get('status'))}`",
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
        )
        artifacts = write_profile(profile, out_dir=args.out_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(
            json.dumps(
                {
                    "profile_status": profile["profile_status"],
                    "artifacts": artifacts,
                    "known_safe_candidate_count": profile["known_safe_candidate_count"],
                    "live_safe_candidate_count": profile["live_safe_candidate_count"],
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
