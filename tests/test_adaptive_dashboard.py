from __future__ import annotations

import json
from pathlib import Path

from sdetkit import adaptive_dashboard
from sdetkit.cli import main as top_level_main


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_adaptive_dashboard_builds_summary_with_missing_warnings(tmp_path: Path) -> None:
    diagnosis = _write_json(
        tmp_path / "diagnosis.json",
        {
            "schema_version": "sdetkit.adaptive.diagnosis.v1",
            "status": "needs_attention",
            "risk_score": 42,
            "diagnoses": [{"code": "RUFF_FIXABLE_LINT"}],
        },
    )
    portfolio = _write_json(
        tmp_path / "portfolio.json",
        {
            "schema_version": "sdetkit.adaptive.portfolio_rollup.v1",
            "recommendation": "SHIP_WITH_CONTROLS",
            "repo_count": 2,
            "portfolio_risk_score": 64,
            "top_risk_scenarios": [{"code": "RUFF_FIXABLE_LINT"}],
        },
    )
    out = tmp_path / "build" / "adaptive-dashboard.html"

    payload = adaptive_dashboard.build_dashboard(
        {"diagnosis": str(diagnosis), "portfolio": str(portfolio)}, out_path=out
    )

    assert payload["schema_version"] == "sdetkit.adaptive.dashboard.v1"
    assert payload["ok"] is True
    assert payload["present_artifact_count"] == 2
    assert payload["missing_artifact_count"] == 6
    diagnosis_card = next(row for row in payload["artifacts"] if row["kind"] == "diagnosis")
    assert diagnosis_card["summary"]["top_code"] == "RUFF_FIXABLE_LINT"
    assert "brief" in payload["next_owner_action"]


def test_adaptive_dashboard_renders_static_local_html(tmp_path: Path) -> None:
    analytics = _write_json(
        tmp_path / "analytics.json",
        {
            "schema_version": "sdetkit.adaptive.enterprise_analytics.v1",
            "recommendation": "SHIP_WITH_CONTROLS",
            "metrics": {
                "remediation_success_rate": 0.75,
                "missing_proof_rate": 0.25,
                "failed_proof_rate": 0.0,
            },
        },
    )
    out = tmp_path / "dashboard.html"

    rc = adaptive_dashboard.main(
        ["--analytics", str(analytics), "--format", "html", "--out", str(out)]
    )

    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "Adaptive next-wave dashboard" in text
    assert "Enterprise analytics" in text
    assert "remediation_success_rate" in text
    assert "local only: true" in text


def test_top_level_cli_adaptive_dashboard_passthrough(tmp_path: Path) -> None:
    policy = _write_json(
        tmp_path / "policy-result.json",
        {
            "schema_version": "sdetkit.adaptive.remediation_policy.result.v1",
            "ok": True,
            "recommendation": "APPROVE",
            "finding_count": 0,
        },
    )
    out = tmp_path / "dashboard.json"

    rc = top_level_main(
        [
            "adaptive",
            "dashboard",
            "--remediation-policy",
            str(policy),
            "--format",
            "json",
            "--out",
            str(out),
        ]
    )

    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["present_artifact_count"] == 1
    policy_card = next(row for row in payload["artifacts"] if row["kind"] == "remediation_policy")
    assert policy_card["summary"]["recommendation"] == "APPROVE"
