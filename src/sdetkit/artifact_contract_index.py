from __future__ import annotations

from pathlib import Path
from typing import Any

from . import doctor, review
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
    path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=False, indent=2) + "\n", encoding="utf-8")
