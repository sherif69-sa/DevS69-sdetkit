from __future__ import annotations

import json
from pathlib import Path

from sdetkit import (
    adoption_surface,
    automation_health,
    candidate_collision_checklist,
    candidate_evidence_checklist,
    candidate_freeze_readiness,
    check_intelligence,
    diagnostic_signal_snapshot,
    diagnostic_signal_snapshot_history,
    doctor,
    issue_queue_classifier,
    maintenance_queue_rollup,
    pr_quality_runtime_proof_artifacts,
    protected_verifier,
    replayable_benchmark_harness,
    repo_fit_screen,
    repo_memory,
    review,
    safe_fix_history_memory,
    security_finding_disposition_matrix,
    security_findings_inventory,
    security_followup_disposition,
    trajectory_store,
)
from sdetkit.artifact_contract_index import INDEX_SCHEMA_VERSION, build_index, write_index
from sdetkit.checks import artifacts as check_artifacts


def test_artifact_contract_index_schema_versions_are_in_sync() -> None:
    payload = build_index()
    assert payload["schema_version"] == INDEX_SCHEMA_VERSION

    entries = {item["id"]: item for item in payload["artifacts"]}
    assert (
        entries["diagnostic-signal-snapshot-json"]["schema_version"]
        == diagnostic_signal_snapshot.SCHEMA_VERSION
    )
    assert (
        entries["diagnostic-signal-snapshot-history-summary-json"]["schema_version"]
        == diagnostic_signal_snapshot_history.SCHEMA_VERSION
    )
    assert {
        "schema_version",
        "measurements",
        "decision_boundary",
    }.issubset(set(entries["diagnostic-signal-snapshot-json"]["required_fields"]))
    assert {
        "schema_version",
        "latest_record",
        "decision_boundary",
    }.issubset(set(entries["diagnostic-signal-snapshot-history-summary-json"]["required_fields"]))
    assert (
        entries["pr-quality-runtime-proof-artifacts-json"]["schema_version"]
        == pr_quality_runtime_proof_artifacts.SCHEMA_VERSION
    )
    assert {
        "schema_version",
        "collected_components",
        "decision_boundary",
    }.issubset(set(entries["pr-quality-runtime-proof-artifacts-json"]["required_fields"]))
    assert (
        entries["protected-verifier-result-json"]["schema_version"]
        == protected_verifier.SCHEMA_VERSION
    )
    assert (
        entries["replayable-benchmark-report-json"]["schema_version"]
        == replayable_benchmark_harness.SCHEMA_VERSION
    )
    assert {
        "schema_version",
        "decision",
        "findings",
    }.issubset(set(entries["protected-verifier-result-json"]["required_fields"]))
    assert {
        "schema_version",
        "required_contract",
        "safety_boundary",
    }.issubset(set(entries["replayable-benchmark-report-json"]["required_fields"]))
    assert entries["trajectory-jsonl"]["schema_version"] == trajectory_store.SCHEMA_VERSION
    assert entries["repo-memory-profile-json"]["schema_version"] == repo_memory.SCHEMA_VERSION
    assert (
        entries["safe-fix-history-json"]["schema_version"] == safe_fix_history_memory.SCHEMA_VERSION
    )
    assert (
        entries["safe-fix-trends-json"]["schema_version"]
        == safe_fix_history_memory.TRENDS_SCHEMA_VERSION
    )
    assert {
        "schema_version",
        "decision",
        "final_result",
    }.issubset(set(entries["trajectory-jsonl"]["required_fields"]))
    assert {
        "schema_version",
        "profile_status",
        "memory_mode",
    }.issubset(set(entries["repo-memory-profile-json"]["required_fields"]))
    assert (
        entries["check-intelligence-json"]["schema_version"]
        == check_intelligence.CHECK_INTELLIGENCE_SCHEMA_VERSION
    )
    assert (
        entries["check-intelligence-action-report-json"]["schema_version"]
        == check_intelligence.ACTION_REPORT_SCHEMA_VERSION
    )
    assert {
        "schema_version",
        "failed_checks",
        "real_evidence_quality",
    }.issubset(set(entries["check-intelligence-json"]["required_fields"]))
    assert {
        "schema_version",
        "automation",
        "evidence",
    }.issubset(set(entries["check-intelligence-action-report-json"]["required_fields"]))
    assert (
        entries["candidate-collision-checklist-json"]["schema_version"]
        == candidate_collision_checklist.SCHEMA_VERSION
    )
    assert {
        "schema_version",
        "collision_checks",
        "freeze_ready",
        "candidate_frozen",
        "automation_allowed",
    }.issubset(set(entries["candidate-collision-checklist-json"]["required_fields"]))
    assert (
        entries["candidate-evidence-checklist-json"]["schema_version"]
        == candidate_evidence_checklist.SCHEMA_VERSION
    )
    assert {
        "schema_version",
        "checklist_items",
        "freeze_ready",
        "candidate_frozen",
        "automation_allowed",
    }.issubset(set(entries["candidate-evidence-checklist-json"]["required_fields"]))
    assert (
        entries["candidate-freeze-readiness-json"]["schema_version"]
        == candidate_freeze_readiness.SCHEMA_VERSION
    )
    assert {
        "schema_version",
        "freeze_ready",
        "candidate_frozen",
        "automation_allowed",
    }.issubset(set(entries["candidate-freeze-readiness-json"]["required_fields"]))
    assert entries["repo-fit-screen-json"]["schema_version"] == repo_fit_screen.SCHEMA_VERSION
    assert {
        "schema_version",
        "candidate_frozen",
        "automation_allowed",
    }.issubset(set(entries["repo-fit-screen-json"]["required_fields"]))
    assert (
        entries["maintenance-queue-rollup-json"]["schema_version"]
        == maintenance_queue_rollup.SCHEMA_VERSION
    )
    assert {
        "schema_version",
        "queue_items",
        "automation_allowed",
    }.issubset(set(entries["maintenance-queue-rollup-json"]["required_fields"]))
    assert (
        entries["security-finding-disposition-matrix-json"]["schema_version"]
        == security_finding_disposition_matrix.SCHEMA_VERSION
    )
    assert {
        "schema_version",
        "matrix_rows",
        "dismiss_allowed",
        "suppress_allowed",
        "fix_allowed",
        "automation_allowed",
    }.issubset(set(entries["security-finding-disposition-matrix-json"]["required_fields"]))
    assert (
        entries["security-findings-inventory-json"]["schema_version"]
        == security_findings_inventory.SCHEMA_VERSION
    )
    assert {
        "schema_version",
        "items",
        "dismiss_allowed",
        "fix_allowed",
        "automation_allowed",
    }.issubset(set(entries["security-findings-inventory-json"]["required_fields"]))
    assert (
        entries["security-followup-disposition-json"]["schema_version"]
        == security_followup_disposition.SCHEMA_VERSION
    )
    assert {
        "schema_version",
        "dispositions",
        "automation_allowed",
    }.issubset(set(entries["security-followup-disposition-json"]["required_fields"]))
    assert entries["automation-health-json"]["schema_version"] == automation_health.SCHEMA_VERSION
    assert {
        "schema_version",
        "automation_signals",
        "automation_allowed",
    }.issubset(set(entries["automation-health-json"]["required_fields"]))
    assert (
        entries["issue-queue-classifier-json"]["schema_version"]
        == issue_queue_classifier.SCHEMA_VERSION
    )
    assert {
        "schema_version",
        "issues",
        "classification_counts",
        "automation_allowed",
    }.issubset(set(entries["issue-queue-classifier-json"]["required_fields"]))
    assert entries["adoption-surface-json"]["schema_version"] == adoption_surface.SCHEMA_VERSION
    assert {
        "schema_version",
        "automation_allowed",
        "merge_authorized",
        "semantic_equivalence_proven",
    }.issubset(set(entries["adoption-surface-json"]["required_fields"]))
    assert entries["doctor-json"]["schema_version"] == doctor.SCHEMA_VERSION
    assert entries["doctor-evidence-json"]["schema_version"] == doctor.EVIDENCE_SCHEMA_VERSION
    assert (
        entries["doctor-evidence-manifest-json"]["schema_version"]
        == doctor.EVIDENCE_MANIFEST_SCHEMA_VERSION
    )
    assert entries["review-json"]["schema_version"] == review.SCHEMA_VERSION
    assert (
        entries["checks-verdict-json"]["schema_version"] == check_artifacts.VERDICT_SCHEMA_VERSION
    )
    assert (
        entries["checks-fix-plan-json"]["schema_version"] == check_artifacts.FIX_PLAN_SCHEMA_VERSION
    )
    assert (
        entries["checks-risk-summary-json"]["schema_version"]
        == check_artifacts.RISK_SUMMARY_SCHEMA_VERSION
    )
    assert (
        entries["checks-evidence-zip"]["schema_version"] == check_artifacts.EVIDENCE_SCHEMA_VERSION
    )


def test_artifact_contract_index_includes_canonical_gate_artifacts() -> None:
    payload = build_index()
    entries = {item["id"]: item for item in payload["artifacts"]}

    for artifact_id in ("gate-fast-json", "release-preflight-json"):
        assert artifact_id in entries
        required = set(entries[artifact_id]["required_fields"])
        assert {"ok", "failed_steps", "profile"}.issubset(required)


def test_artifact_contract_index_docs_json_matches_generator_payload() -> None:
    docs_payload = json.loads(Path("docs/artifact-contract-index.json").read_text(encoding="utf-8"))
    assert docs_payload == build_index()


def test_artifact_contract_index_write_index_roundtrip(tmp_path: Path) -> None:
    out = tmp_path / "artifact-contract-index.json"
    write_index(out)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload == build_index()
