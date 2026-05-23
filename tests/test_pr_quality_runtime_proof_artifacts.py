from __future__ import annotations

import json
from pathlib import Path

from sdetkit.pr_quality_runtime_proof_artifacts import (
    BASE_ANCESTRY_VERIFIED,
    COLLECTED,
    LIVE_PROVEN_RECORD_COUNT,
    NOT_COLLECTED,
    PRIOR_HISTORY_READ_ONLY_INPUT,
    PROOF_COMMANDS_EXECUTED_BY_READER,
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
    assert summary["live_benchmark"]["anti_cheat_rejection_count"] == 2
    assert summary["repo_memory"]["live_safe_candidate_count"] == 1
    assert summary["decision_boundary"]["automation_allowed"] is False


def test_runtime_proof_markdown_reports_unwired_artifacts_honestly() -> None:
    markdown = render_markdown(build_runtime_proof_artifacts(isolated_proof=_isolated_proof()))

    assert "# PR Quality runtime proof artifacts" in markdown
    assert "Git inventory verified: `true`" in markdown
    assert "Runtime guard passed: `true`" in markdown
    assert "Runtime guard violations: `0`" in markdown
    assert "Network isolation enforced: `false`" in markdown
    assert markdown.count("Collection status: `not_collected`") == 3
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
    printed = json.loads(capsys.readouterr().out)
    saved = json.loads((out_dir / "runtime-proof-artifacts.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "runtime-proof-artifacts.md").read_text(encoding="utf-8")

    assert printed["status"] == COLLECTED
    assert printed["collected_components"] == ["isolated_proof"]
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
    assert "Status: `live_proof_supported_memory`" in markdown
    assert "Live contract proven: `true`" in markdown


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
        },
        "decision_boundary": {
            PROOF_COMMANDS_EXECUTED_BY_READER: False,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
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
    printed = json.loads(capsys.readouterr().out)
    saved = json.loads((out_dir / "runtime-proof-artifacts.json").read_text(encoding="utf-8"))

    assert printed["trusted_history_status"] == "trusted_history_verified"
    assert saved[TRUSTED_HISTORY]["record_count"] == 1
    assert saved[TRUSTED_HISTORY][BASE_ANCESTRY_VERIFIED] is True
