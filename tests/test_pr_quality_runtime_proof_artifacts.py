from __future__ import annotations

import json
from pathlib import Path

from sdetkit.pr_quality_runtime_proof_artifacts import (
    BASE_ANCESTRY_VERIFIED,
    COLLECTED,
    CONTROLLED_REVIEW_FIRST_COUNT,
    CONTROLLED_STRUCTURALLY_VERIFIED_COUNT,
    CONTROLLED_VALIDATION_RECORD_COUNT,
    CONTROLLED_VALIDATION_SCENARIO_COUNT,
    LIVE_PROVEN_RECORD_COUNT,
    NOT_COLLECTED,
    PRIOR_HISTORY_READ_ONLY_INPUT,
    PROOF_COMMANDS_EXECUTED_BY_READER,
    REPLAY_MANIFEST,
    REPLAY_MANIFEST_AUTOMATION_ALLOWED,
    REPLAY_MANIFEST_MERGE_AUTHORIZED,
    REPLAY_MANIFEST_PRESENT,
    REPLAY_MANIFEST_REPORTING_ONLY,
    REPLAY_MANIFEST_SCENARIO_COUNT,
    REPLAY_MANIFEST_SEMANTIC_EQUIVALENCE_PROVEN,
    TRUSTED_DIAGNOSTIC_SIGNAL_SNAPSHOT_HISTORY,
    TRUSTED_HISTORY,
    build_runtime_proof_artifacts,
    main,
    render_markdown,
)


def _isolated_proof() -> dict:
    return {
        "status": "passed",
        "proof_summary": {
            "requested_count": 1,
            "executed_count": 1,
            "blocked_count": 0,
            "passed_count": 1,
            "failed_count": 0,
        },
        "runtime_guard": {
            "checked": True,
            "passed": True,
            "violation_count": 0,
            "status_counts": {"clean": 1},
        },
        "network_boundary": {"status": "not_requested"},
        "isolation": {
            "network_isolation_required": False,
            "network_isolation_enforced": False,
            "proof_execution_blocked": False,
        },
        "decision_boundary": {
            "git_inventory_verified": True,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }


def test_runtime_proof_summary_records_actual_isolated_proof_only() -> None:
    summary = build_runtime_proof_artifacts(isolated_proof=_isolated_proof())

    assert summary["status"] == COLLECTED
    assert summary["collected_components"] == ["isolated_proof"]

    isolated = summary["isolated_proof"]
    assert isolated["collection_status"] == COLLECTED
    assert isolated["status"] == "passed"
    assert isolated["git_inventory_verified"] is True
    assert isolated["runtime_guard_checked"] is True
    assert isolated["runtime_guard_passed"] is True
    assert isolated["runtime_guard_violation_count"] == 0
    assert isolated["network_boundary_status"] == "not_requested"
    assert isolated["network_isolation_enforced"] is False
    assert isolated["profiles_executed"] == 1
    assert isolated["profiles_blocked"] == 0

    assert summary["live_benchmark"]["collection_status"] == NOT_COLLECTED
    assert summary["repo_memory"]["collection_status"] == NOT_COLLECTED
    assert summary[TRUSTED_HISTORY]["collection_status"] == NOT_COLLECTED
    assert summary[TRUSTED_DIAGNOSTIC_SIGNAL_SNAPSHOT_HISTORY]["collection_status"] == NOT_COLLECTED

    boundary = summary["decision_boundary"]
    assert boundary["proof_commands_executed_by_renderer"] is False
    assert boundary["automation_allowed"] is False
    assert boundary["merge_authorized"] is False
    assert boundary["semantic_equivalence_proven"] is False


def test_runtime_proof_summary_accepts_future_live_inputs_without_authority() -> None:
    summary = build_runtime_proof_artifacts(
        isolated_proof=_isolated_proof(),
        live_benchmark_report={
            "status": "passed",
            "report_mode": "git_grounded_isolated_proof",
            "scenario_count": 6,
            "passed_count": 6,
            "live_evidence": {
                "git_inventory_verified_count": 5,
                "expected_failed_evidence_count": 5,
                "network_boundary_blocked_count": 1,
                "anti_cheat_rejection_count": 2,
                "network_isolation_enforced_count": 0,
            },
            REPLAY_MANIFEST: {
                "scenario_count": 6,
                "reporting_only": True,
                "automation_allowed": False,
                "merge_authorized": False,
                "semantic_equivalence_proven": False,
            },
        },
        repo_memory_profile={
            "profile_status": "live_proof_supported_memory",
            "known_safe_candidate_count": 1,
            "live_safe_candidate_count": 1,
            "proof_provenance": {
                "live_contract_proven": True,
                "anti_cheat_rejection_scenario_count": 2,
            },
        },
    )

    assert summary["collected_components"] == [
        "isolated_proof",
        "live_benchmark",
        "repo_memory",
    ]
    benchmark = summary["live_benchmark"]
    assert benchmark["anti_cheat_rejection_count"] == 2
    assert benchmark[REPLAY_MANIFEST_PRESENT] is True
    assert benchmark[REPLAY_MANIFEST_SCENARIO_COUNT] == 6
    assert benchmark[REPLAY_MANIFEST_REPORTING_ONLY] is True
    assert benchmark[REPLAY_MANIFEST_AUTOMATION_ALLOWED] is False
    assert benchmark[REPLAY_MANIFEST_MERGE_AUTHORIZED] is False
    assert benchmark[REPLAY_MANIFEST_SEMANTIC_EQUIVALENCE_PROVEN] is False
    assert summary["repo_memory"]["live_safe_candidate_count"] == 1
    assert summary["decision_boundary"]["automation_allowed"] is False


def test_runtime_proof_markdown_reports_unwired_artifacts_honestly() -> None:
    markdown = render_markdown(build_runtime_proof_artifacts(isolated_proof=_isolated_proof()))

    assert "# PR Quality runtime proof artifacts" in markdown
    assert "Git inventory verified: `true`" in markdown
    assert "Runtime guard passed: `true`" in markdown
    assert "Runtime guard violations: `0`" in markdown
    assert "Network isolation enforced: `false`" in markdown
    assert markdown.count("Collection status: `not_collected`") == 4
    assert "Proof commands executed by renderer: `false`" in markdown
    assert "Automation allowed: `false`" in markdown
    assert "Merge authorized: `false`" in markdown


def test_runtime_proof_cli_writes_summary_artifacts(tmp_path: Path, capsys) -> None:
    proof = tmp_path / "verification-evidence.json"
    proof.write_text(json.dumps(_isolated_proof()), encoding="utf-8")
    out_dir = tmp_path / "runtime-proof"

    rc = main(
        [
            "--isolated-proof",
            str(proof),
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    captured = capsys.readouterr()
    saved = json.loads((out_dir / "runtime-proof-artifacts.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "runtime-proof-artifacts.md").read_text(encoding="utf-8")

    assert captured.out == ""
    assert captured.err == ""
    assert saved["status"] == COLLECTED
    assert saved["collected_components"] == ["isolated_proof"]
    assert saved["isolated_proof"]["runtime_guard_passed"] is True
    assert "Live benchmark evidence" in markdown
    assert "RepoMemory evidence" in markdown


def test_runtime_proof_markdown_renders_collected_live_benchmark_and_memory() -> None:
    summary = build_runtime_proof_artifacts(
        isolated_proof=_isolated_proof(),
        live_benchmark_report={
            "status": "passed",
            "report_mode": "git_grounded_isolated_proof",
            "scenario_count": 6,
            "passed_count": 6,
            "failed_count": 0,
            "live_evidence": {
                "git_inventory_verified_count": 5,
                "expected_failed_evidence_count": 5,
                "network_boundary_blocked_count": 1,
                "anti_cheat_rejection_count": 2,
                "network_isolation_enforced_count": 0,
            },
            "safety_boundary": {
                "automation_allowed_count": 0,
                "merge_authorized_count": 0,
                "semantic_equivalence_claimed_count": 0,
                "preserved": True,
            },
            REPLAY_MANIFEST: {
                "scenario_count": 6,
                "reporting_only": True,
                "automation_allowed": False,
                "merge_authorized": False,
                "semantic_equivalence_proven": False,
            },
        },
        repo_memory_profile={
            "profile_status": "live_proof_supported_memory",
            "known_safe_candidate_count": 0,
            "live_safe_candidate_count": 0,
            "proof_provenance": {
                "live_contract_proven": True,
                "git_verified_scenario_count": 5,
                "expected_failed_scenario_count": 5,
                "network_boundary_blocked_scenario_count": 1,
                "anti_cheat_rejection_scenario_count": 2,
            },
            "safety_gate_evidence": {
                "status": "safety_gate_evidence_observed",
                "record_count": 3,
                "safe_fix_allowed_count": 1,
                "review_first_count": 2,
                "decision_boundary": {
                    "automation_allowed": False,
                    "merge_authorized": False,
                    "semantic_equivalence_proven": False,
                },
            },
            "trajectory_authority_evidence": {
                "status": "authority_boundary_evidence_observed",
                "record_count": 2,
                "review_first_count": 1,
                "auto_fix_allowed_count": 1,
                "reporting_only_count": 2,
                "decision_boundary": {
                    "automation_allowed": False,
                    "patch_application_allowed": False,
                    "merge_authorized": False,
                    "semantic_equivalence_proven": False,
                    "automatic_security_fix_allowed": False,
                    "automatic_dismissal_allowed": False,
                },
            },
            "decision_boundary": {
                "automation_allowed": False,
                "merge_authorized": False,
                "semantic_equivalence_proven": False,
            },
        },
    )

    markdown = render_markdown(summary)

    assert "Scenarios: `6`" in markdown
    assert "Passed: `6`" in markdown
    assert "Anti-cheat rejection scenarios: `2`" in markdown
    assert "Boundary preserved: `true`" in markdown
    assert "Replay manifest present: `true`" in markdown
    assert "Replay manifest scenarios: `6`" in markdown
    assert "Replay manifest reporting only: `true`" in markdown
    assert "Replay manifest automation allowed: `false`" in markdown
    assert "Replay manifest merge authorized: `false`" in markdown
    assert "Replay manifest semantic equivalence proven: `false`" in markdown
    assert "Status: `live_proof_supported_memory`" in markdown
    assert "Live contract proven: `true`" in markdown
    assert summary["repo_memory"]["safety_gate_record_count"] == 3
    assert summary["repo_memory"]["safety_gate_safe_fix_allowed_count"] == 1
    assert summary["repo_memory"]["safety_gate_review_first_count"] == 2
    assert summary["repo_memory"]["safety_gate_automation_allowed"] is False
    assert (
        summary["repo_memory"]["trajectory_authority_status"]
        == "authority_boundary_evidence_observed"
    )
    assert summary["repo_memory"]["trajectory_authority_record_count"] == 2
    assert summary["repo_memory"]["trajectory_authority_review_first_count"] == 1
    assert summary["repo_memory"]["trajectory_authority_auto_fix_allowed_count"] == 1
    assert summary["repo_memory"]["trajectory_authority_reporting_only_count"] == 2
    assert summary["repo_memory"]["trajectory_authority_patch_application_allowed"] is False
    assert summary["repo_memory"]["trajectory_authority_security_dismissal_allowed"] is False
    assert summary["repo_memory"]["trajectory_authority_merge_authorized"] is False
    assert summary["repo_memory"]["trajectory_authority_semantic_equivalence_proven"] is False
    assert "RepoMemory SafetyGate status: `safety_gate_evidence_observed`" in markdown
    assert "RepoMemory SafetyGate records: `3`" in markdown
    assert "RepoMemory SafetyGate safe-fix allowed records: `1`" in markdown
    assert "RepoMemory SafetyGate review-first records: `2`" in markdown
    assert "RepoMemory SafetyGate automation allowed: `false`" in markdown
    assert "RepoMemory SafetyGate merge authorized: `false`" in markdown
    assert "RepoMemory SafetyGate semantic equivalence proven: `false`" in markdown
    assert (
        "RepoMemory trajectory authority status: `authority_boundary_evidence_observed`"
    ) in markdown
    assert "RepoMemory trajectory authority records: `2`" in markdown
    assert ("RepoMemory trajectory authority patch application allowed: `false`") in markdown
    assert ("RepoMemory trajectory authority security dismissal allowed: `false`") in markdown
    assert "RepoMemory trajectory authority merge authorized: `false`" in markdown
    assert ("RepoMemory trajectory authority semantic equivalence proven: `false`") in markdown


def _trusted_diagnostic_signal_snapshot_history() -> dict:
    return {
        "collection_status": COLLECTED,
        "status": "trusted_diagnostic_signal_snapshot_history_verified",
        "source": {
            "workflow": "RepoMemory Profile History",
            "run_id": "snapshot-run-1",
            "head_sha": "accepted-main-head",
            "base_sha": "pr-base-head",
            BASE_ANCESTRY_VERIFIED: True,
        },
        "history": {
            "record_count": 3,
            "quiet_green_advisory_baseline_record_count": 1,
            "review_signal_record_count": 3,
            "integration_proof_signal_record_count": 2,
            "latest_snapshot_status": "diagnostic_signal_observed",
            "latest_primary_signal_kind": "review_signal",
            "advisor_false_positive_rate_status": "requires_reviewed_history",
            "reviewed_false_positive_count": None,
            "reviewed_observation_count": None,
            PRIOR_HISTORY_READ_ONLY_INPUT: True,
        },
        "decision_boundary": {
            "reporting_only": True,
            "current_pr_decision_input": False,
            "feeds_repo_memory": False,
            "proof_commands_executed": False,
            "patch_application_allowed": False,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
            "historical_snapshot_authorizes_current_action": False,
        },
    }


def test_runtime_proof_summary_renders_trusted_diagnostic_signal_snapshot_history() -> None:
    summary = build_runtime_proof_artifacts(
        isolated_proof=_isolated_proof(),
        trusted_diagnostic_signal_snapshot_history=(_trusted_diagnostic_signal_snapshot_history()),
    )

    trusted = summary[TRUSTED_DIAGNOSTIC_SIGNAL_SNAPSHOT_HISTORY]
    assert summary["collected_components"] == [
        "isolated_proof",
        TRUSTED_DIAGNOSTIC_SIGNAL_SNAPSHOT_HISTORY,
    ]
    assert trusted["collection_status"] == COLLECTED
    assert trusted["status"] == "trusted_diagnostic_signal_snapshot_history_verified"
    assert trusted[BASE_ANCESTRY_VERIFIED] is True
    assert trusted["record_count"] == 3
    assert trusted["quiet_green_advisory_baseline_record_count"] == 1
    assert trusted["review_signal_record_count"] == 3
    assert trusted["integration_proof_signal_record_count"] == 2
    assert trusted["latest_snapshot_status"] == "diagnostic_signal_observed"
    assert trusted["advisor_false_positive_rate_status"] == "requires_reviewed_history"
    assert trusted["reviewed_false_positive_count"] is None
    assert trusted["reviewed_observation_count"] is None
    assert trusted[PRIOR_HISTORY_READ_ONLY_INPUT] is True
    assert trusted["current_pr_decision_input"] is False
    assert trusted["feeds_repo_memory"] is False
    assert trusted["proof_commands_executed"] is False
    assert trusted["patch_application_allowed"] is False
    assert trusted["automation_allowed"] is False
    assert trusted["merge_authorized"] is False
    assert trusted["semantic_equivalence_proven"] is False
    assert trusted["historical_snapshot_authorizes_current_action"] is False

    markdown = render_markdown(summary)
    assert "Trusted diagnostic signal snapshot history" in markdown
    assert "Review-signal records: `3`" in markdown
    assert "Integration-proof-signal records: `2`" in markdown
    assert "Latest retained snapshot status: `diagnostic_signal_observed`" in markdown
    assert "Advisor false-positive rate status: `requires_reviewed_history`" in markdown
    assert "Prior history is read-only input: `true`" in markdown
    assert "Current PR decision input: `false`" in markdown
    assert "Feeds RepoMemory: `false`" in markdown
    assert "Patch application allowed: `false`" in markdown
    assert "Automation allowed by trusted diagnostic signal history: `false`" in markdown
    assert "Merge authorized by trusted diagnostic signal history: `false`" in markdown
    assert "Historical snapshot authorizes current action: `false`" in markdown


def _trusted_history_evidence() -> dict:
    return {
        "collection_status": COLLECTED,
        "status": "trusted_history_verified",
        "source": {
            "workflow": "RepoMemory Profile History",
            "run_id": "trusted-run-1",
            "head_sha": "accepted-main-head",
            "base_sha": "pr-base-head",
            BASE_ANCESTRY_VERIFIED: True,
        },
        "history": {
            "record_count": 1,
            LIVE_PROVEN_RECORD_COUNT: 1,
            "latest_accepted_main_head": "accepted-main-head",
            PRIOR_HISTORY_READ_ONLY_INPUT: True,
            CONTROLLED_VALIDATION_RECORD_COUNT: 1,
            CONTROLLED_VALIDATION_SCENARIO_COUNT: 2,
            CONTROLLED_STRUCTURALLY_VERIFIED_COUNT: 1,
            CONTROLLED_REVIEW_FIRST_COUNT: 1,
            "latest_controlled_validation_status": "controlled_validation_passed",
            "controlled_validation_reporting_only": True,
        },
        "decision_boundary": {
            PROOF_COMMANDS_EXECUTED_BY_READER: False,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
            "controlled_validation_authorizes_current_action": False,
        },
    }


def test_runtime_proof_summary_renders_validated_trusted_main_history() -> None:
    summary = build_runtime_proof_artifacts(
        isolated_proof=_isolated_proof(),
        trusted_history_evidence=_trusted_history_evidence(),
    )

    trusted = summary[TRUSTED_HISTORY]
    assert summary["collected_components"] == ["isolated_proof", TRUSTED_HISTORY]
    assert trusted["collection_status"] == COLLECTED
    assert trusted["status"] == "trusted_history_verified"
    assert trusted[BASE_ANCESTRY_VERIFIED] is True
    assert trusted["record_count"] == 1
    assert trusted[LIVE_PROVEN_RECORD_COUNT] == 1
    assert trusted[PRIOR_HISTORY_READ_ONLY_INPUT] is True
    assert trusted[CONTROLLED_VALIDATION_RECORD_COUNT] == 1
    assert trusted[CONTROLLED_VALIDATION_SCENARIO_COUNT] == 2
    assert trusted[CONTROLLED_STRUCTURALLY_VERIFIED_COUNT] == 1
    assert trusted[CONTROLLED_REVIEW_FIRST_COUNT] == 1
    assert trusted["controlled_validation_reporting_only"] is True
    assert trusted["controlled_validation_authorizes_current_action"] is False
    assert trusted[PROOF_COMMANDS_EXECUTED_BY_READER] is False
    assert trusted["automation_allowed"] is False
    assert trusted["merge_authorized"] is False
    assert trusted["semantic_equivalence_proven"] is False

    markdown = render_markdown(summary)
    assert "Trusted accepted-main RepoMemory history" in markdown
    assert "Source workflow: `RepoMemory Profile History`" in markdown
    assert "Base ancestry verified: `true`" in markdown
    assert "Records: `1`" in markdown
    assert "Live-contract-proven records: `1`" in markdown
    assert "Prior history is read-only input: `true`" in markdown
    assert "Controlled validation records: `1`" in markdown
    assert "Controlled validation reporting only: `true`" in markdown
    assert "Controlled validation authorizes current action: `false`" in markdown
    assert "Automation allowed by trusted history: `false`" in markdown
    assert "Merge authorized by trusted history: `false`" in markdown


def test_runtime_proof_cli_accepts_validated_trusted_history_input(
    tmp_path: Path,
    capsys,
) -> None:
    trusted_path = tmp_path / "trusted-history-evidence.json"
    trusted_path.write_text(json.dumps(_trusted_history_evidence()), encoding="utf-8")
    out_dir = tmp_path / "runtime-proof"

    rc = main(
        [
            "--trusted-history-evidence",
            str(trusted_path),
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    captured = capsys.readouterr()
    saved = json.loads((out_dir / "runtime-proof-artifacts.json").read_text(encoding="utf-8"))

    assert captured.out == ""
    assert captured.err == ""
    assert saved[TRUSTED_HISTORY]["status"] == "trusted_history_verified"
    assert saved[TRUSTED_HISTORY]["record_count"] == 1
    assert saved[TRUSTED_HISTORY][BASE_ANCESTRY_VERIFIED] is True


def test_runtime_proof_cli_accepts_trusted_diagnostic_signal_snapshot_history(
    tmp_path: Path,
    capsys,
) -> None:
    trusted_path = tmp_path / "trusted-diagnostic-signal-snapshot-history.json"
    trusted_path.write_text(
        json.dumps(_trusted_diagnostic_signal_snapshot_history()),
        encoding="utf-8",
    )
    out_dir = tmp_path / "runtime-proof"

    rc = main(
        [
            "--trusted-diagnostic-signal-snapshot-history",
            str(trusted_path),
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    captured = capsys.readouterr()
    saved = json.loads((out_dir / "runtime-proof-artifacts.json").read_text(encoding="utf-8"))

    assert captured.out == ""
    assert captured.err == ""
    trusted = saved[TRUSTED_DIAGNOSTIC_SIGNAL_SNAPSHOT_HISTORY]
    assert trusted["status"] == "trusted_diagnostic_signal_snapshot_history_verified"
    assert trusted["record_count"] == 3
    assert trusted["automation_allowed"] is False
    assert trusted["merge_authorized"] is False
