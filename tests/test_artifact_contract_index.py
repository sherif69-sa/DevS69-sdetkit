from __future__ import annotations

import json
from pathlib import Path

from sdetkit import (
    adoption_learning_report,
    adoption_learning_report_dashboard,
    adoption_public_repo_trial_matrix_report,
    adoption_surface,
    automation_health,
    candidate_collision_checklist,
    candidate_evidence_checklist,
    candidate_freeze_readiness,
    check_intelligence,
    ci_failure_extractor,
    diagnostic_execution_plan,
    diagnostic_job,
    diagnostic_signal_snapshot,
    diagnostic_signal_snapshot_history,
    diagnostic_worker_trajectory,
    doctor,
    issue_queue_classifier,
    job_queue,
    local_diagnostic_queue_dashboard,
    maintenance_queue_rollup,
    maintenance_queue_rollup_dashboard,
    post_merge_verification,
    pr_quality_runtime_proof_artifacts,
    professional_naming_cleanup_plan,
    professional_naming_inventory,
    protected_verifier,
    replayable_benchmark_harness,
    repo_fit_screen,
    repo_memory,
    review,
    safe_fix_history_memory,
    security_finding_disposition_matrix,
    security_findings_inventory,
    security_followup_disposition,
    security_review_packet,
    trajectory_store,
)
from sdetkit.artifact_contract_index import INDEX_SCHEMA_VERSION, build_index, write_index
from sdetkit.checks import artifacts as check_artifacts


def test_artifact_contract_index_schema_versions_are_in_sync() -> None:
    payload = build_index()
    assert payload["schema_version"] == INDEX_SCHEMA_VERSION

    entries = {item["id"]: item for item in payload["artifacts"]}
    assert (
        entries["diagnostic-execution-plan-json"]["schema_version"]
        == diagnostic_execution_plan.SCHEMA_VERSION
    )
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
        "replay_manifest",
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
        "proof",
        "final_result",
        "learned_pattern",
    }.issubset(set(entries["trajectory-jsonl"]["required_fields"]))
    assert {
        "schema_version",
        "profile_status",
        "memory_mode",
        "proof_provenance",
        "safety_gate_evidence",
        "decision_boundary",
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
        entries["professional-naming-cleanup-plan-json"]["schema_version"]
        == professional_naming_cleanup_plan.SCHEMA_VERSION
    )
    assert {
        "schema_version",
        "cleanup_slices",
        "rename_allowed",
        "compatibility_migration_allowed",
        "public_surface_changes_allowed",
        "automation_allowed",
    }.issubset(set(entries["professional-naming-cleanup-plan-json"]["required_fields"]))
    assert (
        entries["professional-naming-inventory-json"]["schema_version"]
        == professional_naming_inventory.SCHEMA_VERSION
    )
    assert {
        "schema_version",
        "items",
        "rename_allowed",
        "compatibility_required",
        "automation_allowed",
    }.issubset(set(entries["professional-naming-inventory-json"]["required_fields"]))
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
        entries["security-review-packet-json"]["schema_version"]
        == security_review_packet.SCHEMA_VERSION
    )
    assert {
        "schema_version",
        "decision_required",
        "dismiss_allowed",
        "suppress_allowed",
        "fix_allowed",
        "issue_mutation_allowed",
        "automation_allowed",
    }.issubset(set(entries["security-review-packet-json"]["required_fields"]))
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


def test_artifact_contract_index_includes_local_diagnostic_queue_artifacts() -> None:
    payload = build_index()
    entries = {item["id"]: item for item in payload["artifacts"]}

    artifact_ids = {
        "local-diagnostic-queue-json",
        "diagnostic-worker-result-json",
        "diagnostic-worker-trajectory-jsonl",
        "diagnostic-worker-trajectory-summary-json",
    }

    assert artifact_ids.issubset(entries)

    queue_entry = entries["local-diagnostic-queue-json"]
    worker_entry = entries["diagnostic-worker-result-json"]
    trajectory_entry = entries["diagnostic-worker-trajectory-jsonl"]
    summary_entry = entries["diagnostic-worker-trajectory-summary-json"]

    assert queue_entry["schema_version"] == job_queue.SCHEMA_VERSION
    assert worker_entry["schema_version"] == diagnostic_job.WORKER_RESULT_SCHEMA_VERSION
    assert trajectory_entry["schema_version"] == trajectory_store.SCHEMA_VERSION
    assert summary_entry["schema_version"] == diagnostic_worker_trajectory.SCHEMA_VERSION

    assert queue_entry["path"] == ("build/local-diagnostic-queue/queue.json")
    assert worker_entry["path"] == (
        "build/local-diagnostic-queue/worker/<job-id>/diagnostic-worker-result.json"
    )
    assert trajectory_entry["path"] == (
        "build/local-diagnostic-queue/worker/<job-id>/trajectory/diagnostic-worker-trajectory.jsonl"
    )
    assert summary_entry["path"] == (
        "build/local-diagnostic-queue/worker/"
        "<job-id>/trajectory/"
        "diagnostic-worker-trajectory-summary.json"
    )

    assert {
        "schema_version",
        "execution_mode",
        "jobs",
        "decision_boundary",
    }.issubset(queue_entry["required_fields"])

    assert {
        "schema_version",
        "job_id",
        "status",
        "output_artifacts",
        "decision_boundary",
        "execution",
    }.issubset(worker_entry["required_fields"])

    assert {
        "schema_version",
        "trajectory_id",
        "decision",
        "proof",
        "worker_evidence",
    }.issubset(trajectory_entry["required_fields"])

    assert {
        "schema_version",
        "trajectory_schema_version",
        "reporting_only",
        "current_pr_decision_input",
        "automation_allowed",
        "merge_authorized",
    }.issubset(summary_entry["required_fields"])

    for artifact_id in artifact_ids:
        entry = entries[artifact_id]

        assert entry["stability"] == "advanced"
        assert entry["produced_by"].startswith("sdetkit-diagnostic-queue-runner ")
        assert "--max-jobs <count>" in entry["produced_by"]
        assert "--claimed-at <timestamp>" in entry["produced_by"]
        assert "--finished-at <timestamp>" in entry["produced_by"]


def test_artifact_contract_index_includes_local_diagnostic_queue_dashboard_json() -> None:
    payload = build_index()
    entries = {item["id"]: item for item in payload["artifacts"]}

    artifact_id = "local-diagnostic-queue-dashboard-json"
    assert artifact_id in entries

    entry = entries[artifact_id]
    assert entry["schema_version"] == local_diagnostic_queue_dashboard.SCHEMA_VERSION
    assert entry["path"] == (
        local_diagnostic_queue_dashboard.DEFAULT_OUT.with_suffix(".json").as_posix()
    )
    assert entry["stability"] == "advanced"

    assert {
        "schema_version",
        "status",
        "queue_path",
        "queue_exists",
        "source_queue_schema_version",
        "execution_mode",
        "local_only",
        "read_only",
        "job_count",
        "state_counts",
        "artifact_count",
        "present_artifact_count",
        "missing_artifact_count",
        "jobs",
        "decision_boundary",
    }.issubset(set(entry["required_fields"]))

    assert entry["produced_by"].startswith("sdetkit-local-diagnostic-queue-dashboard ")
    assert "--queue-path build/local-diagnostic-queue/queue.json" in (entry["produced_by"])
    assert "--format json" in entry["produced_by"]
    assert "--out build/local-diagnostic-queue/dashboard.json" in (entry["produced_by"])



def test_artifact_contract_index_includes_diagnostic_execution_plan_json() -> None:
    payload = build_index()
    entries = {item["id"]: item for item in payload["artifacts"]}

    artifact_id = "diagnostic-execution-plan-json"
    assert artifact_id in entries

    entry = entries[artifact_id]
    assert entry["schema_version"] == diagnostic_execution_plan.SCHEMA_VERSION
    assert entry["path"] == diagnostic_execution_plan.DEFAULT_OUT
    assert entry["stability"] == "advanced"

    assert {
        "schema_version",
        "plan_status",
        "repo_identity",
        "source_artifacts",
        "summary",
        "commands",
        "review_first_items",
        "policies",
        "rules",
        "execution_allowed",
        "automation_allowed",
        "patch_application_allowed",
        "merge_authorized",
        "semantic_equivalence_proven",
        "authority_boundary",
    }.issubset(set(entry["required_fields"]))

    assert entry["produced_by"].startswith(
        "python -m sdetkit.diagnostic_execution_plan "
    )
    assert "--root ." in entry["produced_by"]
    assert "--out build/sdetkit/diagnostic-execution-plan.json" in entry["produced_by"]
    assert "--format json" in entry["produced_by"]

def test_artifact_contract_index_includes_adoption_learning_report_json() -> None:
    payload = build_index()
    entries = {item["id"]: item for item in payload["artifacts"]}

    artifact_id = "adoption-learning-report-json"
    assert artifact_id in entries

    entry = entries[artifact_id]
    assert entry["schema_version"] == adoption_learning_report.SCHEMA_VERSION
    assert entry["path"] == ("build/sdetkit/adoption-learning-report.json")
    assert entry["stability"] == "advanced"

    assert {
        "schema_version",
        "source_matrix",
        "source_matrix_schema_version",
        "source_matrix_status",
        "source_repo_count",
        "candidate_count",
        "top_candidate",
        "prioritized_upgrade_candidates",
        "repo_memory_profile",
        "operator_summary",
        "rules",
        "automation_allowed",
        "patch_application_allowed",
        "merge_authorized",
        "semantic_equivalence_proven",
        "authority_boundary",
    }.issubset(set(entry["required_fields"]))

    assert entry["produced_by"].startswith("python -m sdetkit adoption-learning-report ")
    assert (
        "--matrix-json "
        "build/sdetkit/adoption-real-world-learning/"
        "adoption-real-world-matrix.json" in entry["produced_by"]
    )
    assert "--out build/sdetkit/adoption-learning-report.json" in entry["produced_by"]
    assert "--format json" in entry["produced_by"]


def test_artifact_contract_index_includes_public_repo_trial_matrix_report_json() -> None:
    payload = build_index()
    entries = {item["id"]: item for item in payload["artifacts"]}

    artifact_id = "public-repo-trial-matrix-report-json"
    assert artifact_id in entries

    entry = entries[artifact_id]
    assert entry["schema_version"] == adoption_public_repo_trial_matrix_report.SCHEMA_VERSION
    assert entry["path"] == (adoption_public_repo_trial_matrix_report.DEFAULT_OUT.as_posix())
    assert entry["stability"] == "advanced"

    assert {
        "schema_version",
        "report_status",
        "input_provenance",
        "source_matrix",
        "summary",
        "trials",
        "operator_summary",
        "rules",
        "reporting_only",
        "repo_mutation",
        "automation_allowed",
        "patch_application_allowed",
        "merge_authorized",
        "semantic_equivalence_proven",
        "authority_boundary",
    }.issubset(set(entry["required_fields"]))

    assert entry["produced_by"].startswith("python -m sdetkit adoption-public-trial-matrix-report ")
    assert (
        "--matrix-json "
        "tests/fixtures/adoption_public_trials/"
        "public_repo_trial_matrix.json" in entry["produced_by"]
    )
    assert "--out build/sdetkit/public-repo-trial-matrix-report.json" in entry["produced_by"]
    assert "--format json" in entry["produced_by"]


def test_artifact_contract_index_includes_adoption_learning_report_dashboard_json() -> None:
    payload = build_index()
    entries = {item["id"]: item for item in payload["artifacts"]}

    artifact_id = "adoption-learning-report-dashboard-json"
    assert artifact_id in entries

    entry = entries[artifact_id]
    assert entry["schema_version"] == adoption_learning_report_dashboard.SCHEMA_VERSION
    assert entry["path"] == (
        adoption_learning_report_dashboard.DEFAULT_OUT.with_suffix(".json").as_posix()
    )
    assert entry["stability"] == "advanced"

    assert {
        "schema_version",
        "status",
        "report_path",
        "report_exists",
        "source_report_schema_version",
        "source_matrix",
        "source_matrix_schema_version",
        "source_matrix_status",
        "source_repo_count",
        "candidate_count",
        "top_candidate",
        "prioritized_upgrade_candidates",
        "repo_memory_profile",
        "operator_summary",
        "local_only",
        "read_only",
        "decision_boundary",
    }.issubset(set(entry["required_fields"]))

    assert entry["produced_by"].startswith("sdetkit-adoption-learning-report-dashboard ")
    assert "--report-path build/sdetkit/adoption-learning-report.json" in entry["produced_by"]
    assert "--format json" in entry["produced_by"]
    assert "--out build/sdetkit/adoption-learning-report-dashboard.json" in entry["produced_by"]


def test_artifact_contract_index_includes_maintenance_queue_rollup_dashboard_json() -> None:
    payload = build_index()
    entries = {item["id"]: item for item in payload["artifacts"]}

    artifact_id = "maintenance-queue-rollup-dashboard-json"
    assert artifact_id in entries

    entry = entries[artifact_id]
    assert entry["schema_version"] == maintenance_queue_rollup_dashboard.SCHEMA_VERSION
    assert entry["path"] == (
        maintenance_queue_rollup_dashboard.DEFAULT_OUT.with_suffix(".json").as_posix()
    )
    assert entry["stability"] == "advanced"

    assert {
        "schema_version",
        "status",
        "rollup_path",
        "rollup_exists",
        "source_rollup_schema_version",
        "source_rollup_status",
        "source_issue_count",
        "queue_item_count",
        "review_required_count",
        "close_candidate_count",
        "primary_issue",
        "recommended_next_action",
        "lane_counts",
        "input_artifacts",
        "queue_items",
        "local_only",
        "read_only",
        "decision_boundary",
    }.issubset(set(entry["required_fields"]))

    assert entry["produced_by"].startswith("sdetkit-maintenance-queue-rollup-dashboard ")
    assert "--rollup-path build/sdetkit/maintenance-queue-rollup.json" in entry["produced_by"]
    assert "--format json" in entry["produced_by"]
    assert "--out build/sdetkit/maintenance-queue-rollup-dashboard.json" in entry["produced_by"]


def test_artifact_contract_index_includes_ci_failure_extractor_json() -> None:
    payload = build_index()
    entries = {item["id"]: item for item in payload["artifacts"]}

    artifact_id = "ci-failure-extractor-json"
    assert artifact_id in entries

    entry = entries[artifact_id]
    assert entry["schema_version"] == ci_failure_extractor.SCHEMA_VERSION
    assert entry["path"] == ci_failure_extractor.DEFAULT_OUT
    assert entry["stability"] == "advanced"

    assert {
        "schema_version",
        "failed_check_count",
        "failed_checks",
        "summary",
    }.issubset(set(entry["required_fields"]))

    assert entry["produced_by"].startswith("python -m sdetkit.ci_failure_extractor ")
    assert "--log <raw-ci.log>" in entry["produced_by"]
    assert "--out build/sdetkit/failed-check-logs.json" in entry["produced_by"]
    assert "--format text" in entry["produced_by"]


def test_artifact_contract_index_docs_json_matches_generator_payload() -> None:
    docs_payload = json.loads(Path("docs/artifact-contract-index.json").read_text(encoding="utf-8"))
    assert docs_payload == build_index()


def test_artifact_contract_index_write_index_roundtrip(tmp_path: Path) -> None:
    out = tmp_path / "artifact-contract-index.json"
    write_index(out)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload == build_index()


def test_product_maturity_radar_contract_is_registered() -> None:
    from sdetkit import product_maturity_radar

    payload = build_index()
    artifacts = {artifact["id"]: artifact for artifact in payload["artifacts"]}
    contract = artifacts["product-maturity-radar-json"]

    assert contract["path"] == product_maturity_radar.DEFAULT_OUT
    assert contract["schema_version"] == product_maturity_radar.SCHEMA_VERSION
    assert {
        "generated_at",
        "current_head_sha",
        "input_provenance",
        "projection_status",
        "report_dependencies",
        "dependency_status",
        "claim_sources",
    }.issubset(contract["required_fields"])


def test_artifact_contract_index_includes_cross_report_consistency() -> None:
    from sdetkit import cross_report_consistency

    payload = build_index()
    entries = {item["id"]: item for item in payload["artifacts"]}
    entry = entries["cross-report-consistency-json"]

    assert entry["path"] == cross_report_consistency.DEFAULT_OUT
    assert entry["schema_version"] == cross_report_consistency.SCHEMA_VERSION
    assert entry["stability"] == "advanced"
    assert {
        "schema_version",
        "generated_at",
        "current_head_sha",
        "input_provenance",
        "consistency_status",
        "report_records",
        "findings",
        "finding_counts",
        "authority_boundary",
        "automation_allowed",
        "merge_authorized",
    }.issubset(set(entry["required_fields"]))
    assert "python -m sdetkit cross-report-consistency" in entry["produced_by"]


def test_artifact_contract_index_includes_post_merge_verification_json() -> None:
    payload = build_index()
    entries = {item["id"]: item for item in payload["artifacts"]}

    entry = entries["post-merge-verification-json"]
    assert entry["path"] == post_merge_verification.DEFAULT_OUT
    assert entry["schema_version"] == post_merge_verification.SCHEMA_VERSION
    assert entry["stability"] == "advanced"
    assert set(post_merge_verification.REQUIRED_FIELDS).issubset(set(entry["required_fields"]))
    assert entry["produced_by"].startswith("python -m sdetkit post-merge-verification ")
    assert "--evidence-dir <evidence-dir>" in entry["produced_by"]
    assert "--previous-main-sha <sha>" in entry["produced_by"]
