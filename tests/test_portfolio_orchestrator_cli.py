from __future__ import annotations

import json
from pathlib import Path

from sdetkit.portfolio_orchestrator import main


def _sample_graph() -> dict[str, object]:
    return {
        "repos": [
            {"name": "api", "path": "repos/api", "language": "python", "priority": 10},
            {"name": "web", "path": "repos/web", "language": "node", "priority": 40, "depends_on": ["api"]},
        ]
    }


def test_cli_validate_and_orchestrate(tmp_path: Path) -> None:
    graph_path = tmp_path / "graph.json"
    schema_path = tmp_path / "schema.json"
    out_path = tmp_path / "plan.json"
    graph_path.write_text(json.dumps(_sample_graph()), encoding="utf-8")
    schema_path.write_text(
        json.dumps({"type": "object", "required": ["repos"], "properties": {"repos": {"type": "array"}}}),
        encoding="utf-8",
    )
    assert main(["validate-graph", "--repo-graph", str(graph_path), "--schema", str(schema_path)]) == 0
    assert (
        main(
            [
                "orchestrate",
                "--repo-graph",
                str(graph_path),
                "--schema",
                str(schema_path),
                "--max-workers",
                "2",
                "--out",
                str(out_path),
            ]
        )
        == 0
    )
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["repos"] == 2


def test_cli_score_execution(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    out_path = tmp_path / "score.json"
    results_path.write_text(
        json.dumps(
            {
                "results": [
                    {"repo": "api", "status": "ok"},
                    {"repo": "web", "status": "fail"},
                ]
            }
        ),
        encoding="utf-8",
    )
    assert main(["score-execution", "--results", str(results_path), "--out", str(out_path)]) == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["recommendation"] == "NO_SHIP"


def test_cli_report_generation(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    risk_path = tmp_path / "risk.json"
    score_path = tmp_path / "score.json"
    out_path = tmp_path / "report.md"
    plan_path.write_text(json.dumps({"repos": 2, "max_workers": 2}), encoding="utf-8")
    risk_path.write_text(
        json.dumps({"portfolio_risk_score": 80, "recommendation": "SHIP_WITH_CONTROLS"}),
        encoding="utf-8",
    )
    score_path.write_text(
        json.dumps({"execution_reliability_score": 95, "recommendation": "SHIP_WITH_CONTROLS"}),
        encoding="utf-8",
    )
    assert (
        main(
            [
                "report",
                "--plan",
                str(plan_path),
                "--risk",
                str(risk_path),
                "--score",
                str(score_path),
                "--out",
                str(out_path),
            ]
        )
        == 0
    )
    report = out_path.read_text(encoding="utf-8")
    assert "Portfolio Orchestration Report" in report


def test_cli_analyze_plan(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    out_path = tmp_path / "analysis.json"
    plan_path.write_text(
        json.dumps(
            {
                "execution_plan": [
                    {"repo": "contracts", "depends_on": []},
                    {"repo": "api", "depends_on": ["contracts"]},
                    {"repo": "web", "depends_on": ["api"]},
                ]
            }
        ),
        encoding="utf-8",
    )
    assert main(["analyze-plan", "--plan", str(plan_path), "--out", str(out_path)]) == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["critical_path_length"] == 3


def test_cli_run_pipeline(tmp_path: Path) -> None:
    graph_path = tmp_path / "graph.json"
    schema_path = tmp_path / "schema.json"
    adapters_path = tmp_path / "adapters.json"
    out_dir = tmp_path / "pipeline"
    graph_path.write_text(
        json.dumps(
            {
                "repos": [
                    {"name": "contracts", "path": "repos/contracts", "language": "go"},
                    {"name": "api", "path": "repos/api", "language": "python", "depends_on": ["contracts"]},
                ]
            }
        ),
        encoding="utf-8",
    )
    schema_path.write_text(
        json.dumps({"type": "object", "required": ["repos"], "properties": {"repos": {"type": "array"}}}),
        encoding="utf-8",
    )
    adapters_path.write_text(
        json.dumps({"python": ["echo", "py", "{repo_path}"], "go": ["echo", "go", "{repo_path}"]}),
        encoding="utf-8",
    )
    assert (
        main(
            [
                "run-pipeline",
                "--repo-graph",
                str(graph_path),
                "--schema",
                str(schema_path),
                "--adapters",
                str(adapters_path),
                "--max-workers",
                "2",
                "--out-dir",
                str(out_dir),
            ]
        )
        == 0
    )
    assert (out_dir / "plan.json").exists()
    assert (out_dir / "risk.json").exists()
    assert (out_dir / "execution.json").exists()
    assert (out_dir / "score.json").exists()
    assert (out_dir / "analysis.json").exists()
    assert (out_dir / "report.md").exists()
    assert (out_dir / "policy.json").exists()
    assert (out_dir / "history-trend.json").exists()
    assert (out_dir / "dashboard.html").exists()


def test_cli_run_pipeline_with_run_mode(tmp_path: Path) -> None:
    graph_path = tmp_path / "graph.json"
    schema_path = tmp_path / "schema.json"
    adapters_path = tmp_path / "adapters.json"
    out_dir = tmp_path / "pipeline-run"
    graph_path.write_text(
        json.dumps({"repos": [{"name": "api", "path": "repos/api", "language": "python"}]}),
        encoding="utf-8",
    )
    schema_path.write_text(
        json.dumps({"type": "object", "required": ["repos"], "properties": {"repos": {"type": "array"}}}),
        encoding="utf-8",
    )
    adapters_path.write_text(json.dumps({"python": ["echo", "ok", "{repo_path}"]}), encoding="utf-8")
    assert (
        main(
            [
                "run-pipeline",
                "--repo-graph",
                str(graph_path),
                "--schema",
                str(schema_path),
                "--adapters",
                str(adapters_path),
                "--max-workers",
                "1",
                "--run",
                "--timeout-seconds",
                "30",
                "--out-dir",
                str(out_dir),
            ]
        )
        == 0
    )
    execution = json.loads((out_dir / "execution.json").read_text(encoding="utf-8"))
    assert execution["ok"] is True


def test_cli_evaluate_policy(tmp_path: Path) -> None:
    risk_path = tmp_path / "risk.json"
    score_path = tmp_path / "score.json"
    execution_path = tmp_path / "execution.json"
    policy_path = tmp_path / "policy.json"
    out_path = tmp_path / "decision.json"
    risk_path.write_text(json.dumps({"portfolio_risk_score": 90}), encoding="utf-8")
    score_path.write_text(json.dumps({"execution_reliability_score": 60}), encoding="utf-8")
    execution_path.write_text(
        json.dumps({"failure_count": 2, "stopped_early": True}),
        encoding="utf-8",
    )
    policy_path.write_text(
        json.dumps(
            {
                "name": "strict",
                "max_risk_score": 30,
                "min_execution_reliability": 90,
                "max_failures": 0,
                "allow_stopped_early": False,
            }
        ),
        encoding="utf-8",
    )
    assert (
        main(
            [
                "evaluate-policy",
                "--risk",
                str(risk_path),
                "--score",
                str(score_path),
                "--execution",
                str(execution_path),
                "--policy",
                str(policy_path),
                "--out",
                str(out_path),
            ]
        )
        == 0
    )
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["decision"] == "NO_SHIP"


def test_cli_history_trend(tmp_path: Path) -> None:
    history = tmp_path / "history.jsonl"
    history.write_text(
        "\n".join(
            [
                json.dumps({"decision": "SHIP", "risk_score": 20}),
                json.dumps({"decision": "NO_SHIP", "risk_score": 50}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "trend.json"
    assert main(["history-trend", "--history", str(history), "--out", str(out)]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["runs"] == 2


def test_cli_dashboard(tmp_path: Path) -> None:
    plan = tmp_path / "plan.json"
    risk = tmp_path / "risk.json"
    score = tmp_path / "score.json"
    execution = tmp_path / "execution.json"
    policy = tmp_path / "policy.json"
    out = tmp_path / "dashboard.html"
    plan.write_text(json.dumps({"repos": 2, "max_workers": 2}), encoding="utf-8")
    risk.write_text(json.dumps({"portfolio_risk_score": 30}), encoding="utf-8")
    score.write_text(json.dumps({"execution_reliability_score": 90}), encoding="utf-8")
    execution.write_text(
        json.dumps({"results": [{"repo": "api", "language": "python", "status": "ok", "mode": "run"}]}),
        encoding="utf-8",
    )
    policy.write_text(json.dumps({"decision": "SHIP"}), encoding="utf-8")
    assert (
        main(
            [
                "dashboard",
                "--plan",
                str(plan),
                "--risk",
                str(risk),
                "--score",
                str(score),
                "--execution",
                str(execution),
                "--policy",
                str(policy),
                "--out",
                str(out),
            ]
        )
        == 0
    )
    html = out.read_text(encoding="utf-8")
    assert "Portfolio Orchestration Dashboard" in html


def test_cli_batch_run(tmp_path: Path) -> None:
    manifest = tmp_path / "batch.json"
    out_dir = tmp_path / "batch-out"
    graph = tmp_path / "graph.json"
    schema = tmp_path / "schema.json"
    adapters = tmp_path / "adapters.json"
    policy = tmp_path / "policy.json"
    graph.write_text(
        json.dumps({"repos": [{"name": "api", "path": "repos/api", "language": "python"}]}),
        encoding="utf-8",
    )
    schema.write_text(
        json.dumps({"type": "object", "required": ["repos"], "properties": {"repos": {"type": "array"}}}),
        encoding="utf-8",
    )
    adapters.write_text(json.dumps({"python": ["echo", "ok", "{repo_path}"]}), encoding="utf-8")
    policy.write_text(
        json.dumps(
            {
                "name": "default-enterprise",
                "max_risk_score": 100,
                "min_execution_reliability": 0,
                "max_failures": 10,
                "allow_stopped_early": True,
            }
        ),
        encoding="utf-8",
    )
    manifest.write_text(
        json.dumps(
            {
                "portfolios": [
                    {
                        "name": "p1",
                        "repo_graph": str(graph),
                        "schema": str(schema),
                        "adapters": str(adapters),
                        "policy": str(policy),
                        "max_workers": 1,
                        "run": False,
                    },
                    {
                        "name": "p2",
                        "repo_graph": str(graph),
                        "schema": str(schema),
                        "adapters": str(adapters),
                        "policy": str(policy),
                        "max_workers": 1,
                        "run": False,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    assert (
        main(
            [
                "batch-run",
                "--manifest",
                str(manifest),
                "--max-parallel",
                "2",
                "--out-dir",
                str(out_dir),
            ]
        )
        == 0
    )
    summary = json.loads((out_dir / "batch-summary.json").read_text(encoding="utf-8"))
    assert summary["portfolios"] == 2
    assert (out_dir / "p1" / "dashboard.html").exists()
    assert (out_dir / "p2" / "dashboard.html").exists()
    assert (out_dir / "batch-report.md").exists()
    assert (out_dir / "batch-dashboard.html").exists()


def test_cli_impact_plan_and_control_tower(tmp_path: Path) -> None:
    graph = tmp_path / "graph.json"
    changes = tmp_path / "changed.txt"
    out = tmp_path / "impact-plan.json"
    history = tmp_path / "batch-history.jsonl"
    tower = tmp_path / "tower.json"
    graph.write_text(
        json.dumps(
            {
                "repos": [
                    {"name": "contracts", "path": "repos/contracts", "language": "go"},
                    {"name": "api", "path": "repos/api", "language": "python", "depends_on": ["contracts"]},
                ]
            }
        ),
        encoding="utf-8",
    )
    changes.write_text("repos/contracts/schema.proto\n", encoding="utf-8")
    assert (
        main(
            [
                "impact-plan",
                "--repo-graph",
                str(graph),
                "--changed-files",
                str(changes),
                "--out",
                str(out),
            ]
        )
        == 0
    )
    impact = json.loads(out.read_text(encoding="utf-8"))
    assert impact["repos"] == 2
    history.write_text(
        json.dumps({"decision": "SHIP", "risk_score": 20}) + "\n",
        encoding="utf-8",
    )
    assert main(["batch-control-tower", "--history", str(history), "--out", str(tower)]) == 0
    tower_payload = json.loads(tower.read_text(encoding="utf-8"))
    assert tower_payload["control_tower"]["runs"] == 1


def test_cli_cancel_worker_registry(tmp_path: Path) -> None:
    cancel_file = tmp_path / "cancel.txt"
    assert main(["cancel-worker", "--target", "api", "--cancel-file", str(cancel_file)]) == 0
    assert "api" in cancel_file.read_text(encoding="utf-8")
