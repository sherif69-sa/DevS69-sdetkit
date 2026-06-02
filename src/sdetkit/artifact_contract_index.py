from __future__ import annotations

from pathlib import Path
from typing import Any

from . import (
    adoption_surface,
    check_intelligence,
    doctor,
    pr_quality_runtime_proof_artifacts,
    protected_verifier,
    replayable_benchmark_harness,
    repo_memory,
    review,
    safe_fix_history_memory,
    trajectory_store,
)
from .checks import artifacts as check_artifacts

INDEX_SCHEMA_VERSION = "sdetkit.artifact-contract-index.v1"


def build_index() -> dict[str, Any]:
    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "artifacts": [
            {
                "id": "gate-fast-json",
                "path": "build/gate-fast.json",
                "produced_by": "python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json",
                "schema_version": None,
                "required_fields": ["ok", "failed_steps", "profile"],
                "stability": "public",
            },
            {
                "id": "release-preflight-json",
                "path": "build/release-preflight.json",
                "produced_by": "python -m sdetkit gate release --format json --out build/release-preflight.json",
                "schema_version": None,
                "required_fields": ["ok", "failed_steps", "profile"],
                "stability": "public",
            },
            {
                "id": "pr-quality-runtime-proof-artifacts-json",
                "path": (
                    pr_quality_runtime_proof_artifacts.DEFAULT_OUT_DIR
                    / pr_quality_runtime_proof_artifacts.SUMMARY_JSON
                ).as_posix(),
                "produced_by": "python -m sdetkit.pr_quality_runtime_proof_artifacts --isolated-proof <isolated-proof.json> --live-benchmark-report <benchmark-report.json> --repo-memory-profile <repo-memory-profile.json> --trusted-history-evidence <trusted-history.json> --out-dir build/pr-quality/runtime-proof/summary --format json",
                "schema_version": pr_quality_runtime_proof_artifacts.SCHEMA_VERSION,
                "required_fields": [
                    "schema_version",
                    "status",
                    "collected_components",
                    "isolated_proof",
                    "live_benchmark",
                    "repo_memory",
                    "trusted_history",
                    "decision_boundary",
                ],
                "stability": "advanced",
            },
            {
                "id": "protected-verifier-result-json",
                "path": (
                    protected_verifier.DEFAULT_OUT_DIR / protected_verifier.RESULT_JSON
                ).as_posix(),
                "produced_by": "python -m sdetkit.protected_verifier --patch-score <patch-score.json> --verification-evidence <verification-evidence.json> --out-dir build/protected-verifier --format json",
                "schema_version": protected_verifier.SCHEMA_VERSION,
                "required_fields": [
                    "schema_version",
                    "patch_id",
                    "diagnosis_id",
                    "patch_score",
                    "scored_files",
                    "observed_changed_files",
                    "allowed_files",
                    "proof_requirements",
                    "findings",
                    "decision",
                ],
                "stability": "advanced",
            },
            {
                "id": "replayable-benchmark-report-json",
                "path": (
                    replayable_benchmark_harness.DEFAULT_OUT_DIR
                    / replayable_benchmark_harness.REPORT_JSON
                ).as_posix(),
                "produced_by": "python -m sdetkit.replayable_benchmark_harness --scenario <scenario.json> --out-dir build/replayable-benchmark-harness --format json",
                "schema_version": replayable_benchmark_harness.SCHEMA_VERSION,
                "required_fields": [
                    "schema_version",
                    "status",
                    "scenario_count",
                    "passed_count",
                    "failed_count",
                    "required_contract",
                    "safety_boundary",
                    "attempt_scored_count",
                    "scenarios",
                    "next_boundary",
                ],
                "stability": "advanced",
            },
            {
                "id": "trajectory-jsonl",
                "path": trajectory_store.DEFAULT_OUT,
                "produced_by": "python -m sdetkit.trajectory_store --diagnostic-vector <diagnostic-vector.json> --remediation-plan <remediation-plan.json> --out build/sdetkit/trajectory.jsonl --format json",
                "schema_version": trajectory_store.SCHEMA_VERSION,
                "required_fields": [
                    "schema_version",
                    "trajectory_id",
                    "environment",
                    "diagnosis",
                    "decision",
                    "response",
                    "fix",
                    "final_result",
                ],
                "stability": "advanced",
            },
            {
                "id": "repo-memory-profile-json",
                "path": (repo_memory.DEFAULT_OUT_DIR / repo_memory.PROFILE_JSON).as_posix(),
                "produced_by": "python -m sdetkit.repo_memory --out-dir build/repo-memory --format json",
                "schema_version": repo_memory.SCHEMA_VERSION,
                "required_fields": [
                    "schema_version",
                    "profile_status",
                    "memory_mode",
                    "inputs",
                    "safe_fix_history",
                    "known_safe_candidate_count",
                ],
                "stability": "advanced",
            },
            {
                "id": "safe-fix-history-json",
                "path": f"{safe_fix_history_memory.DEFAULT_OUT_DIR}/{safe_fix_history_memory.HISTORY_JSON}",
                "produced_by": "python -m sdetkit.safe_fix_history_memory --out-dir build/operator-loop/safe-fix-history",
                "schema_version": safe_fix_history_memory.SCHEMA_VERSION,
                "required_fields": [
                    "schema_version",
                    "attempts",
                    "metrics",
                ],
                "stability": "advanced",
            },
            {
                "id": "safe-fix-trends-json",
                "path": f"{safe_fix_history_memory.DEFAULT_OUT_DIR}/{safe_fix_history_memory.TRENDS_JSON}",
                "produced_by": "python -m sdetkit.safe_fix_history_memory --out-dir build/operator-loop/safe-fix-history",
                "schema_version": safe_fix_history_memory.TRENDS_SCHEMA_VERSION,
                "required_fields": [
                    "schema_version",
                    "metrics",
                ],
                "stability": "advanced",
            },
            {
                "id": "check-intelligence-json",
                "path": "build/pr-quality/check-intelligence.json",
                "produced_by": "python -m sdetkit.check_intelligence --checks-json <checks.json> --out-dir build/pr-quality",
                "schema_version": check_intelligence.CHECK_INTELLIGENCE_SCHEMA_VERSION,
                "required_fields": [
                    "schema_version",
                    "checks_seen",
                    "failed_checks",
                    "queued_checks",
                    "startup_failures",
                    "real_evidence_quality",
                    "security_review",
                    "code_scanning_review",
                ],
                "stability": "advanced",
            },
            {
                "id": "check-intelligence-action-report-json",
                "path": "build/pr-quality/action-report.json",
                "produced_by": "python -m sdetkit.check_intelligence --checks-json <checks.json> --out-dir build/pr-quality",
                "schema_version": check_intelligence.ACTION_REPORT_SCHEMA_VERSION,
                "required_fields": [
                    "schema_version",
                    "status",
                    "primary_blocker",
                    "automation",
                    "recommended_actions",
                    "proof_commands",
                    "evidence",
                ],
                "stability": "advanced",
            },
            {
                "id": "adoption-surface-json",
                "path": "build/sdetkit/adoption-surface.json",
                "produced_by": "python -m sdetkit adoption-surface --root . --out build/sdetkit/adoption-surface.json --format text",
                "schema_version": adoption_surface.SCHEMA_VERSION,
                "required_fields": [
                    "schema_version",
                    "detected_languages",
                    "package_managers",
                    "test_runners",
                    "ci_systems",
                    "security_tools",
                    "artifact_surfaces",
                    "recommended_proof_commands",
                    "review_first_unknowns",
                    "automation_allowed",
                    "merge_authorized",
                    "semantic_equivalence_proven",
                ],
                "stability": "advanced",
            },
            {
                "id": "doctor-json",
                "path": "build/doctor.json",
                "produced_by": "python -m sdetkit doctor --format json --out build/doctor.json",
                "schema_version": doctor.SCHEMA_VERSION,
                "required_fields": ["schema_version", "ok", "checks"],
                "stability": "public",
            },
            {
                "id": "doctor-evidence-json",
                "path": "build/doctor-evidence.json",
                "produced_by": "python -m sdetkit doctor --emit-evidence --format json --out build/doctor.json",
                "schema_version": doctor.EVIDENCE_SCHEMA_VERSION,
                "required_fields": ["schema_version", "doctor_schema_version", "summary"],
                "stability": "advanced",
            },
            {
                "id": "doctor-evidence-manifest-json",
                "path": "build/doctor-evidence-manifest.json",
                "produced_by": "python -m sdetkit doctor --emit-evidence --format json --out build/doctor.json",
                "schema_version": doctor.EVIDENCE_MANIFEST_SCHEMA_VERSION,
                "required_fields": ["schema_version", "doctor_schema_version", "artifacts"],
                "stability": "advanced",
            },
            {
                "id": "review-json",
                "path": "build/review.json",
                "produced_by": "python -m sdetkit review . --no-workspace --format json --out build/review.json",
                "schema_version": review.SCHEMA_VERSION,
                "required_fields": ["schema_version", "status", "severity"],
                "stability": "advanced",
            },
            {
                "id": "review-operator-json",
                "path": "build/review-operator.json",
                "produced_by": "python -m sdetkit review . --no-workspace --format operator-json --out build/review-operator.json",
                "schema_version": None,
                "required_fields": ["situation", "actions", "artifacts"],
                "stability": "advanced",
            },
            {
                "id": "checks-verdict-json",
                "path": "build/verdict.json",
                "produced_by": "python -m sdetkit gate release --format json --out build/release-preflight.json",
                "schema_version": check_artifacts.VERDICT_SCHEMA_VERSION,
                "required_fields": ["schema_version", "ok", "summary", "check_results_summary"],
                "stability": "public",
            },
            {
                "id": "checks-fix-plan-json",
                "path": "build/fix-plan.json",
                "produced_by": "python -m sdetkit gate release --format json --out build/release-preflight.json",
                "schema_version": check_artifacts.FIX_PLAN_SCHEMA_VERSION,
                "required_fields": ["schema_version", "generated_from", "actions"],
                "stability": "public",
            },
            {
                "id": "checks-risk-summary-json",
                "path": "build/risk-summary.json",
                "produced_by": "python -m sdetkit gate release --format json --out build/release-preflight.json",
                "schema_version": check_artifacts.RISK_SUMMARY_SCHEMA_VERSION,
                "required_fields": ["schema_version", "risk", "summary"],
                "stability": "public",
            },
            {
                "id": "checks-evidence-zip",
                "path": "build/evidence.zip",
                "produced_by": "python -m sdetkit gate release --format json --out build/release-preflight.json",
                "schema_version": check_artifacts.EVIDENCE_SCHEMA_VERSION,
                "required_fields": ["schema_version"],
                "stability": "public",
            },
        ],
    }


def write_index(path: Path) -> None:
    import json

    payload = build_index()
    path.write_text(
        json.dumps(payload, ensure_ascii=True, sort_keys=False, indent=2) + "\n", encoding="utf-8"
    )
