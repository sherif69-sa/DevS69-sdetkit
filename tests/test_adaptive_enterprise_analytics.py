from __future__ import annotations

import json
from pathlib import Path

from sdetkit import adaptive_enterprise_analytics
from sdetkit.cli import main as top_level_main


def _portfolio() -> dict[str, object]:
    return {
        "schema_version": "sdetkit.adaptive.portfolio_rollup.v1",
        "recommendation": "SHIP_WITH_CONTROLS",
        "repo_count": 2,
        "artifact_count": 2,
        "portfolio_risk_score": 72,
        "top_risk_scenarios": [
            {"code": "PYTEST_ASSERTION_FAILURE", "occurrences": 3, "risk_points": 44},
            {"code": "RUFF_LINT_FAILURE", "occurrences": 1, "risk_points": 18},
        ],
        "recurrence_by_repo": [
            {
                "repo": "api",
                "max_status": "needs_attention",
                "risk_score": 42,
                "diagnosis_count": 2,
                "artifact_count": 1,
            },
            {
                "repo": "web",
                "max_status": "monitor",
                "risk_score": 30,
                "diagnosis_count": 1,
                "artifact_count": 1,
            },
        ],
    }


def _audit_records() -> list[dict[str, object]]:
    base = {
        "schema_version": "sdetkit.adaptive.fix_audit.v1",
        "plan_kind": "safe_fix",
        "source_path": "build/format-plan.json",
        "source_code": "RUFF_LINT_FAILURE",
        "action_type": "format_only",
    }
    unknown = {
        "schema_version": "sdetkit.adaptive.fix_audit.v1",
        "plan_kind": "assisted_patch_plan",
        "source_path": "build/unknown-plan.json",
        "source_code": "UNKNOWN_REVIEW_REQUIRED",
        "action_type": "review_required",
    }
    return [
        {**base, "outcome": "planned", "recorded_at": "2026-05-08T10:00:00+00:00"},
        {**base, "outcome": "proof_passed", "recorded_at": "2026-05-08T10:10:00+00:00"},
        {**unknown, "outcome": "planned", "recorded_at": "2026-05-08T11:00:00+00:00"},
    ]


def test_enterprise_analytics_combines_portfolio_and_fix_audit_metrics() -> None:
    payload = adaptive_enterprise_analytics.build_enterprise_analytics(
        _portfolio(), _audit_records()
    )

    assert payload["schema_version"] == "sdetkit.adaptive.enterprise_analytics.v1"
    assert payload["recommendation"] == "SHIP_WITH_CONTROLS"
    assert payload["metrics"]["record_count"] == 3
    assert payload["metrics"]["remediation_decision_count"] == 2
    assert payload["metrics"]["remediation_success_rate"] == 0.5
    assert payload["metrics"]["missing_proof_rate"] == 0.5
    assert payload["metrics"]["failed_proof_rate"] == 0.0
    assert payload["metrics"]["mean_time_to_proof_seconds"] == 600.0
    top_codes = {row["code"]: row["count"] for row in payload["top_recurring_source_codes"]}
    assert top_codes["PYTEST_ASSERTION_FAILURE"] == 3
    assert top_codes["RUFF_LINT_FAILURE"] == 3
    assert payload["top_risky_repos"][0]["repo"] == "api"


def test_enterprise_analytics_blocks_release_on_failed_proof() -> None:
    records = [
        *_audit_records(),
        {
            "schema_version": "sdetkit.adaptive.fix_audit.v1",
            "plan_kind": "safe_fix",
            "source_path": "build/import-plan.json",
            "source_code": "PYTEST_IMPORT_FAILURE",
            "action_type": "dependency_install",
            "outcome": "proof_failed",
            "recorded_at": "2026-05-08T12:00:00+00:00",
        },
    ]

    payload = adaptive_enterprise_analytics.build_enterprise_analytics(_portfolio(), records)

    assert payload["ok"] is False
    assert payload["recommendation"] == "NO_SHIP"
    assert payload["metrics"]["proof_failed_count"] == 1
    assert payload["metrics"]["failed_proof_rate"] == 0.5


def test_enterprise_analytics_cli_and_top_level_passthrough(tmp_path: Path) -> None:
    portfolio = tmp_path / "portfolio.json"
    audit = tmp_path / "audit.jsonl"
    out = tmp_path / "analytics.json"
    portfolio.write_text(json.dumps(_portfolio()), encoding="utf-8")
    audit.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in _audit_records()) + "\n",
        encoding="utf-8",
    )

    rc = top_level_main(
        [
            "adaptive",
            "enterprise-analytics",
            "--portfolio",
            str(portfolio),
            "--fix-audit",
            str(audit),
            "--format",
            "json",
            "--out",
            str(out),
        ]
    )

    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["portfolio"]["portfolio_risk_score"] == 72
    assert payload["metrics"]["missing_proof_count"] == 1
