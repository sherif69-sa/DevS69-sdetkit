from __future__ import annotations

import json
from pathlib import Path

from sdetkit.portfolio_orchestrator import (
    _adapter_command,
    _adapter_command_from_registry,
    _analyze_plan,
    _append_history_record,
    _build_plan,
    _build_risk_report,
    _build_history_trend,
    _execute_plan,
    _evaluate_policy,
    _load_adapter_registry,
    _score_execution_results,
    _render_portfolio_report,
    _render_portfolio_dashboard_html,
    _load_policy,
    _parse_policy_overrides,
    _resolve_policy_profile,
    _validate_against_repo_schema,
    _validate_repo_graph_shape,
)


def test_build_plan_orders_dependencies_before_dependents() -> None:
    graph = {
        "repos": [
            {"name": "web", "path": "repos/web", "language": "node", "priority": 40, "depends_on": ["api"]},
            {"name": "api", "path": "repos/api", "language": "python", "priority": 10},
        ]
    }
    plan = _build_plan(graph, max_workers=2)
    items = plan["execution_plan"]
    assert isinstance(items, list)
    assert items[0]["repo"] == "api"
    assert items[1]["repo"] == "web"


def test_build_plan_rejects_unknown_dependency() -> None:
    graph = {"repos": [{"name": "web", "path": "repos/web", "language": "node", "depends_on": ["missing"]}]}
    try:
        _build_plan(graph, max_workers=2)
    except ValueError as exc:
        assert "unknown dependency" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_risk_report_shape() -> None:
    plan = {
        "execution_plan": [
            {"repo": "api", "priority": 10},
            {"repo": "web", "priority": 50},
            {"repo": "docs", "priority": 90},
        ]
    }
    report = _build_risk_report(plan)
    assert report["ok"] is True
    assert report["risk_buckets"] == {"high": 1, "medium": 1, "low": 1}
    assert report["recommendation"] in {"SHIP_WITH_CONTROLS", "NO_SHIP"}
    json.dumps(report)


def test_execute_plan_generates_threaded_execution_intents() -> None:
    plan = {
        "execution_plan": [
            {"repo": "api", "path": "repos/api", "language": "python", "priority": 10},
            {"repo": "web", "path": "repos/web", "language": "node", "priority": 20},
        ]
    }
    result = _execute_plan(plan, max_workers=2, run=False)
    assert result["ok"] is True
    rows = result["results"]
    assert isinstance(rows, list)
    assert len(rows) == 2
    assert rows[0]["status"] == "queued"
    assert rows[0]["mode"] == "dry-run"
    assert "run_id" in rows[0]
    assert "started_at" in rows[0]
    assert "finished_at" in rows[0]
    assert "escalation" in rows[0]


def test_execute_plan_writes_worker_artifacts(tmp_path: Path) -> None:
    plan = {
        "execution_plan": [
            {"repo": "contracts", "path": "repos/contracts", "language": "go", "depends_on": []},
            {"repo": "api", "path": "repos/api", "language": "python", "depends_on": ["contracts"]},
        ]
    }
    result = _execute_plan(plan, max_workers=2, run=False, artifact_dir=tmp_path)
    assert result["ok"] is True
    assert (tmp_path / "contracts.worker.json").exists()
    assert (tmp_path / "api.worker.json").exists()


def test_execute_plan_retries_failed_run() -> None:
    plan = {"execution_plan": [{"repo": "api", "path": "repos/api", "language": "python", "depends_on": []}]}
    registry = {"python": ["python", "-c", "import sys; sys.exit(1)"]}
    result = _execute_plan(plan, max_workers=1, run=True, adapter_registry=registry, retries=1)
    rows = result["results"]
    assert isinstance(rows, list)
    assert rows[0]["status"] == "fail"
    assert rows[0]["attempts"] == 2


def test_execute_plan_stops_early_after_max_failures() -> None:
    plan = {
        "execution_plan": [
            {"repo": "a", "path": "repos/a", "language": "python", "depends_on": []},
            {"repo": "b", "path": "repos/b", "language": "python", "depends_on": []},
        ]
    }
    registry = {"python": ["python", "-c", "import sys; sys.exit(1)"]}
    result = _execute_plan(
        plan,
        max_workers=1,
        run=True,
        adapter_registry=registry,
        retries=0,
        max_failures=1,
    )
    assert result["stopped_early"] is True
    assert result["failure_count"] >= 1


def test_adapter_command_for_unknown_language() -> None:
    cmd = _adapter_command("rust", "repos/engine")
    assert cmd[0] == "echo"


def test_adapter_registry_loading_and_resolution(tmp_path: Path) -> None:
    path = tmp_path / "adapters.json"
    path.write_text(json.dumps({"python": ["python", "-m", "tool", "{repo_path}"]}), encoding="utf-8")
    registry = _load_adapter_registry(path)
    cmd = _adapter_command_from_registry(registry, "python", "repos/api")
    assert cmd == ["python", "-m", "tool", "repos/api"]


def test_validate_graph_rejects_duplicates() -> None:
    payload = {
        "repos": [
            {"name": "api", "path": "repos/api", "language": "python"},
            {"name": "api", "path": "repos/api2", "language": "go"},
        ]
    }
    try:
        _validate_repo_graph_shape(payload)
    except ValueError as exc:
        assert "duplicate repo name" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_score_execution_results() -> None:
    payload = {
        "results": [
            {"repo": "api", "status": "ok"},
            {"repo": "web", "status": "fail"},
            {"repo": "jobs", "status": "error"},
        ]
    }
    score = _score_execution_results(payload)
    assert score["ok"] is True
    assert score["totals"] == {"ok": 1, "fail": 1, "error": 1}
    assert score["recommendation"] == "NO_SHIP"


def test_validate_against_schema_fallback_or_jsonschema(tmp_path: Path) -> None:
    schema = {"type": "object", "required": ["repos"], "properties": {"repos": {"type": "array"}}}
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    payload = {"repos": [{"name": "api", "path": "repos/api", "language": "python"}]}
    _validate_against_repo_schema(payload, schema_path)


def test_render_portfolio_report() -> None:
    report = _render_portfolio_report(
        plan={"repos": 3, "max_workers": 4},
        risk={"portfolio_risk_score": 82, "recommendation": "SHIP_WITH_CONTROLS"},
        score={"execution_reliability_score": 90, "recommendation": "SHIP_WITH_CONTROLS"},
    )
    assert "Portfolio Orchestration Report" in report
    assert "Planned repositories: 3" in report


def test_analyze_plan_critical_path() -> None:
    analysis = _analyze_plan(
        {
            "execution_plan": [
                {"repo": "contracts", "depends_on": []},
                {"repo": "api", "depends_on": ["contracts"]},
                {"repo": "web", "depends_on": ["api"]},
            ]
        }
    )
    assert analysis["ok"] is True
    assert analysis["critical_path_length"] == 3


def test_evaluate_policy_no_ship_violation(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "name": "strict",
                "max_risk_score": 20,
                "min_execution_reliability": 90,
                "max_failures": 0,
                "allow_stopped_early": False,
            }
        ),
        encoding="utf-8",
    )
    policy = _load_policy(policy_path)
    evaluation = _evaluate_policy(
        risk={"portfolio_risk_score": 50},
        score={"execution_reliability_score": 70},
        execution={"failure_count": 1, "stopped_early": True},
        policy=policy,
    )
    assert evaluation["decision"] == "NO_SHIP"
    assert len(evaluation["violations"]) >= 1


def test_resolve_policy_profile_with_overrides(tmp_path: Path) -> None:
    pack_path = tmp_path / "packs.json"
    pack_path.write_text(
        json.dumps(
            {
                "default_profile": "standard",
                "profiles": {
                    "standard": {"name": "standard", "max_risk_score": 35, "min_execution_reliability": 80},
                    "regulated": {"name": "regulated", "max_risk_score": 20, "min_execution_reliability": 90},
                },
            }
        ),
        encoding="utf-8",
    )
    policy = _resolve_policy_profile(pack_path, profile="regulated", overrides={"max_risk_score": 10})
    assert policy["profile"] == "regulated"
    assert policy["max_risk_score"] == 10


def test_parse_policy_overrides_rejects_non_object() -> None:
    try:
        _parse_policy_overrides('["not-an-object"]')
    except ValueError as exc:
        assert "POLICY_OVERRIDE_INVALID_TYPE" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_history_trend_rollup(tmp_path: Path) -> None:
    history = tmp_path / "history.jsonl"
    _append_history_record(history, {"decision": "SHIP", "risk_score": 20})
    _append_history_record(history, {"decision": "NO_SHIP", "risk_score": 60})
    trend = _build_history_trend(history)
    assert trend["runs"] == 2
    assert trend["ship_rate"] == 0.5


def test_render_dashboard_html() -> None:
    html = _render_portfolio_dashboard_html(
        plan={"repos": 2, "max_workers": 2},
        risk={"portfolio_risk_score": 40},
        score={"execution_reliability_score": 85},
        execution={"results": [{"repo": "api", "language": "python", "status": "ok", "mode": "run"}]},
        policy={"decision": "SHIP"},
    )
    assert "Portfolio Orchestration Dashboard" in html
    assert "<table>" in html


def test_execute_plan_contains_transport_and_lease() -> None:
    plan = {"execution_plan": [{"repo": "api", "path": "repos/api", "language": "python"}]}
    result = _execute_plan(plan, max_workers=1, run=False, transport="ssh")
    row = result["results"][0]
    assert row["transport"] == "ssh"
    assert str(row["lease_id"]).startswith("lease-")


def test_execute_plan_respects_cancel_targets() -> None:
    plan = {"execution_plan": [{"repo": "api", "path": "repos/api", "language": "python"}]}
    result = _execute_plan(plan, max_workers=1, run=False, cancel_targets={"api"})
    row = result["results"][0]
    assert row["status"] == "canceled"
