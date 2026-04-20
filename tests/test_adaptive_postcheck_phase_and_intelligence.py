from __future__ import annotations

import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_module():
    module_path = Path("scripts/adaptive_postcheck.py")
    spec = spec_from_file_location("adaptive_postcheck", module_path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_alignment_checks_include_six_phase_and_intelligence_requirements() -> None:
    mod = _load_module()

    scenario_db = {
        "summary": {"total_scenarios": 3200, "kinds": {"adaptive_reviewer_matrix": 7560}}
    }
    plan_payload = {"phases": ["p1", "p2", "p3", "p4", "p5", "p6"]}

    payload = {"adaptive_database": {"release_readiness_contract": {"recommendation_backlog": []}}}
    scenario = {
        "enabled_checks": [
            "scenario_database_minimum_coverage",
            "six_phase_workflow_ready",
            "intelligence_matrix_present",
        ],
        "scenario_minimum": 3000,
        "warn_only_checks": [],
    }

    checks = mod._run_alignment_checks(
        payload, scenario, {"hint_count": 1}, scenario_db, plan_payload
    )
    by_name = {row["check"]: row for row in checks}

    assert by_name["scenario_database_minimum_coverage"]["passed"] is True
    assert by_name["six_phase_workflow_ready"]["passed"] is True
    assert by_name["intelligence_matrix_present"]["passed"] is True


def test_alignment_check_accepts_alternate_signal_keys() -> None:
    mod = _load_module()
    scenario_db = {
        "summary": {"total_scenarios": 3200, "kinds": {"adaptive_reviewer_matrix": 7560}}
    }
    plan_payload = {"phases": ["p1", "p2", "p3", "p4", "p5", "p6"]}
    payload = {
        "adaptive_database": {
            "release_readiness_contract": {
                "recommendation_backlog": [{"priority_index": 1}],
                "agent_orchestration": [
                    {"signals": ["s1"]},
                    {"evidence_signals": ["s2"]},
                    {"engine_signals": {"engine_score": 85}},
                ],
            }
        }
    }
    scenario = {
        "enabled_checks": [
            "agent_entries_include_engine_signals",
            "recommendation_backlog_sorted_desc",
            "scenario_database_minimum_coverage",
        ],
        "scenario_minimum": 3000,
        "warn_only_checks": [],
    }
    checks = mod._run_alignment_checks(
        payload, scenario, {"hint_count": 1}, scenario_db, plan_payload
    )
    by_name = {row["check"]: row for row in checks}
    assert by_name["agent_entries_include_engine_signals"]["passed"] is True


def test_follow_up_enhancements_include_dashboard_feature_when_six_phase_ready() -> None:
    mod = _load_module()
    checks = [
        {"check": "six_phase_workflow_ready", "passed": True},
        {"check": "intelligence_matrix_present", "passed": True},
    ]
    enhancements = mod._build_follow_up_enhancements(
        checks=checks,
        scenario_db={"summary": {"total_scenarios": 10000}},
        plan_payload={"phases": ["p1", "p2", "p3", "p4", "p5", "p6"]},
    )

    ids = {row["id"] for row in enhancements}
    assert "phase6-outcome-intel" in ids
    commands = {row["id"]: row.get("next_command", "") for row in enhancements}
    assert commands["phase6-outcome-intel"] == "make adaptive-ops-bundle"


def test_markdown_summary_includes_follow_up_commands() -> None:
    mod = _load_module()
    text = mod._render_markdown_summary(
        scenario="fast",
        summary={
            "ok": True,
            "passed": 2,
            "total": 2,
            "confidence_score": 96,
            "confidence_band": "auto-approve-candidate",
            "confidence_trend": "improving",
        },
        checks=[{"check": "x", "passed": True, "severity": "required", "details": "ok"}],
        follow_up_enhancements=[
            {
                "id": "phase6-outcome-intel",
                "priority": "medium",
                "area": "reviewer",
                "feature": "Publish per-phase outcomes",
                "next_command": "make adaptive-ops-bundle",
            }
        ],
        scenario_database={
            "source": "latest-artifact",
            "total_scenarios": 1234,
            "domain_confidence": {"quality": 90, "security": 80},
        },
    )

    assert "Adaptive Postcheck Summary" in text
    assert "Scenario DB: `latest-artifact` (1234 scenarios)" in text
    assert "Confidence score: `96`" in text
    assert "Confidence band: `auto-approve-candidate`" in text
    assert "Confidence trend: `improving`" in text
    assert "## Domain Confidence" in text
    assert "`quality`: `90`" in text
    assert "Next command: `make adaptive-ops-bundle`" in text


def test_build_fresh_scenario_database_temp_file_is_cleaned(tmp_path: Path) -> None:
    mod = _load_module()
    out_path = tmp_path / "fresh-db.json"

    def fake_run(cmd, **kwargs):
        idx = cmd.index("--out")
        target = Path(cmd[idx + 1])
        target.write_text(json.dumps({"summary": {"total_scenarios": 9999}}), encoding="utf-8")
        return type("Proc", (), {"returncode": 0})()

    mod.subprocess.run = fake_run  # type: ignore[assignment]
    payload = mod._build_fresh_scenario_database(out_path=out_path, persist=False)

    assert isinstance(payload, dict)
    assert payload["summary"]["total_scenarios"] == 9999
    assert out_path.exists() is False


def test_compute_confidence_score_is_bounded_and_uses_matrix_and_coverage() -> None:
    mod = _load_module()
    score = mod._compute_confidence_score(
        checks=[{"passed": True}, {"passed": True}, {"passed": False}],
        scenario_db={
            "summary": {
                "total_scenarios": 6000,
                "kinds": {"adaptive_reviewer_matrix": 7560},
            }
        },
        scenario_minimum=3000,
    )
    assert 0 <= score <= 100
    assert score >= 75


def test_confidence_band_routes_expected_paths() -> None:
    mod = _load_module()
    assert mod._confidence_band(95)["band"] == "auto-approve-candidate"
    assert mod._confidence_band(80)["band"] == "manual-review"
    assert mod._confidence_band(60)["band"] == "remediation-required"


def test_update_confidence_history_writes_and_computes_trend(tmp_path: Path) -> None:
    mod = _load_module()
    history_path = tmp_path / "history.json"
    mod._update_confidence_history(history_path=history_path, score=70)
    mod._update_confidence_history(history_path=history_path, score=75)
    mod._update_confidence_history(history_path=history_path, score=82)
    payload = mod._update_confidence_history(history_path=history_path, score=86)

    assert history_path.exists()
    assert payload["trend"] == "improving"
    assert len(payload["entries"]) == 4
    assert payload["trend_window_size"] == 4


def test_update_confidence_history_can_detect_regression(tmp_path: Path) -> None:
    mod = _load_module()
    history_path = tmp_path / "history-regress.json"
    for score in [90, 88, 86, 80, 76]:
        payload = mod._update_confidence_history(history_path=history_path, score=score)
    assert payload["trend"] == "regressing"


def test_next_follow_up_plan_adds_regression_audit_when_needed() -> None:
    mod = _load_module()
    steps = mod._next_follow_up_plan(confidence_band="manual-review", confidence_trend="regressing")
    ids = [row["id"] for row in steps]
    assert "trend-regression-audit" in ids
    assert "targeted-remediation" in ids


def test_build_domain_confidence_snapshot_scores_each_domain() -> None:
    mod = _load_module()
    snapshot = mod._build_domain_confidence_snapshot(
        scenario_db={"summary": {"domains": {"quality": 1000, "security": 500}}},
        scenario_minimum=3000,
    )
    assert snapshot["quality"] == 100
    assert snapshot["security"] == 83
