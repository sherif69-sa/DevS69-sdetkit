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
TRUSTED_HISTORY = "_".join(("trusted", "history"))
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


def _isolated_proof_summary(evidence: Mapping[str, Any]) -> JsonObject:
    payload = _as_dict(evidence)
    if not payload:
        return {
            "collection_status": NOT_COLLECTED,
            "status": NOT_COLLECTED,
        }

    proof_summary = _as_dict(payload.get("proof_summary"))
    runtime_guard = _as_dict(payload.get("runtime_guard"))
    network_boundary = _as_dict(payload.get("network_boundary"))
    isolation = _as_dict(payload.get("isolation"))
    decision_boundary = _as_dict(payload.get("decision_boundary"))

    return {
        "collection_status": COLLECTED,
        "status": _string(payload.get("status") or "unknown"),
        "git_inventory_verified": _bool(decision_boundary.get("git_inventory_verified")),
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
        "profiles_executed": _int(proof_summary.get("executed_count")),
        "profiles_blocked": _int(proof_summary.get("blocked_count")),
        "profiles_passed": _int(proof_summary.get("passed_count")),
        "profiles_failed": _int(proof_summary.get("failed_count")),
    }


def _live_benchmark_summary(report: Mapping[str, Any]) -> JsonObject:
    payload = _as_dict(report)
    if not payload:
        return {
            "collection_status": NOT_COLLECTED,
            "status": NOT_COLLECTED,
        }

    live = _as_dict(payload.get("live_evidence"))
    boundary = _as_dict(payload.get("safety_boundary"))
    replay = _as_dict(payload.get("replay_manifest"))
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
        "replay_manifest_present": bool(replay),
        "replay_manifest_scenario_count": _int(replay.get("scenario_count")),
        "replay_manifest_reporting_only": _bool(replay.get("reporting_only")),
        "replay_manifest_automation_allowed": _bool(replay.get("automation_allowed")),
        "replay_manifest_merge_authorized": _bool(replay.get("merge_authorized")),
        "replay_manifest_semantic_equivalence_proven": _bool(
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
        "automation_allowed": _bool(boundary.get("automation_allowed")),
        "merge_authorized": _bool(boundary.get("merge_authorized")),
        "semantic_equivalence_proven": _bool(boundary.get("semantic_equivalence_proven")),
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
            history.get("latest_controlled_validation_status") or "not_collected"
        ),
        "controlled_validation_reporting_only": _bool(
            history.get("controlled_validation_reporting_only")
        ),
        PROOF_COMMANDS_EXECUTED_BY_READER: _bool(boundary.get(PROOF_COMMANDS_EXECUTED_BY_READER)),
        "controlled_validation_authorizes_current_action": _bool(
            boundary.get("controlled_validation_authorizes_current_action")
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
    trusted_history_evidence: Mapping[str, Any] | None = None,
    trusted_diagnostic_signal_snapshot_history: Mapping[str, Any] | None = None,
) -> JsonObject:
    isolated = _isolated_proof_summary(isolated_proof or {})
    live_benchmark = _live_benchmark_summary(live_benchmark_report or {})
    repo_memory = _repo_memory_summary(repo_memory_profile or {})
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
        TRUSTED_HISTORY: trusted_history,
        TRUSTED_DIAGNOSTIC_SIGNAL_SNAPSHOT_HISTORY: trusted_signal_history,
        "decision_boundary": {
            "reporting_only": True,
            "proof_commands_executed_by_renderer": False,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }


def render_markdown(summary: Mapping[str, Any]) -> str:
    isolated = _as_dict(summary.get("isolated_proof"))
    benchmark = _as_dict(summary.get("live_benchmark"))
    memory = _as_dict(summary.get("repo_memory"))
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
            ]
        )

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
                (
                    "- Replay manifest present: "
                    f"`{str(_bool(benchmark.get('replay_manifest_present'))).lower()}`"
                ),
                (
                    "- Replay manifest scenarios: "
                    f"`{_int(benchmark.get('replay_manifest_scenario_count'))}`"
                ),
                (
                    "- Replay manifest reporting only: "
                    f"`{str(_bool(benchmark.get('replay_manifest_reporting_only'))).lower()}`"
                ),
                (
                    "- Replay manifest automation allowed: "
                    f"`{str(_bool(benchmark.get('replay_manifest_automation_allowed'))).lower()}`"
                ),
                (
                    "- Replay manifest merge authorized: "
                    f"`{str(_bool(benchmark.get('replay_manifest_merge_authorized'))).lower()}`"
                ),
                (
                    "- Replay manifest semantic equivalence proven: "
                    f"`{str(_bool(benchmark.get('replay_manifest_semantic_equivalence_proven'))).lower()}`"
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
        trusted_history_evidence=_read_json(args.trusted_history_evidence),
        trusted_diagnostic_signal_snapshot_history=_read_json(
            args.trusted_diagnostic_signal_snapshot_history
        ),
    )
    write_summary(summary, out_dir=args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
