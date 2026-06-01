from __future__ import annotations

from pathlib import Path
from typing import Any

from . import adoption_surface, check_intelligence, doctor, review
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
