from __future__ import annotations

import json
from pathlib import Path

from sdetkit.agent import cli
from sdetkit.agent.core import init_agent, run_agent
from sdetkit.agent.dashboard import build_dashboard


def _seed_history(root: Path) -> None:
    init_agent(root, root / ".sdetkit/agent/config.yaml")
    run_agent(
        root,
        config_path=root / ".sdetkit/agent/config.yaml",
        task="template:alpha",
        auto_approve=True,
    )
    run_agent(
        root,
        config_path=root / ".sdetkit/agent/config.yaml",
        task='action fs.read {"path":"missing.txt"}',
        auto_approve=True,
    )


def test_dashboard_build_is_deterministic(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    _seed_history(tmp_path)

    first_output = tmp_path / "out" / "dashboard.html"
    second_output = tmp_path / "out" / "dashboard-second.html"

    first = build_dashboard(
        history_dir=tmp_path / ".sdetkit/agent/history",
        output=first_output,
        fmt="html",
        summary_output=tmp_path / "out" / "summary.md",
    )
    second = build_dashboard(
        history_dir=tmp_path / ".sdetkit/agent/history",
        output=second_output,
        fmt="html",
        summary_output=tmp_path / "out" / "summary-second.md",
    )

    assert first["runs"] == second["runs"]
    assert first_output.read_text(encoding="utf-8") == second_output.read_text(encoding="utf-8")


def test_dashboard_and_history_export_formats(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    _seed_history(tmp_path)
    monkeypatch.chdir(tmp_path)

    assert cli.main(["dashboard", "build", "--format", "json", "--output", "dashboard.json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["format"] == "json"
    parsed = json.loads((tmp_path / "dashboard.json").read_text(encoding="utf-8"))
    assert parsed["runs"]["total"] == 2
    assert "latest_status" in parsed["runs"]
    assert "workers" in parsed
    assert "approvals" in parsed

    assert cli.main(["dashboard", "build", "--format", "csv", "--output", "dashboard.csv"]) == 0
    csv_lines = (tmp_path / "dashboard.csv").read_text(encoding="utf-8").splitlines()
    assert csv_lines[0] == "captured_at,hash,status,task,action_count"

    assert cli.main(["history", "export", "--format", "csv", "--output", "history.csv"]) == 0
    history_csv = (tmp_path / "history.csv").read_text(encoding="utf-8")
    assert "captured_at,hash,status,task,action_count" in history_csv


def _write_template(root: Path, template_id: str) -> None:
    tpl_dir = root / "templates" / "automations"
    tpl_dir.mkdir(parents=True, exist_ok=True)
    (tpl_dir / f"{template_id}.yaml").write_text(
        (
            "metadata:\n"
            f"  id: {template_id}\n"
            f"  title: {template_id}\n"
            "  version: 1.0.0\n"
            f"  description: {template_id} template\n"
            "workflow:\n"
            "  - action: fs.write\n"
            "    with:\n"
            "      path: ${{run.output_dir}}/artifact.txt\n"
            "      content: ok\n"
        ),
        encoding="utf-8",
    )


def test_demo_repo_enterprise_audit_outputs_artifacts(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    for template_id in ["repo-health-audit", "security-governance-summary", "report-dashboard"]:
        _write_template(tmp_path, template_id)

    monkeypatch.chdir(tmp_path)
    assert cli.main(["demo", "--scenario", "repo-enterprise-audit"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "ok"
    artifacts = payload["artifacts"]
    assert Path(artifacts["dashboard_html"]).exists()
    assert Path(artifacts["dashboard_md"]).exists()
    assert Path(artifacts["history_dir"]).exists()


def test_demo_umbrella_upgrade_control_plane_outputs_blueprint(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    for template_id in ["repo-health-audit", "report-dashboard"]:
        _write_template(tmp_path, template_id)

    monkeypatch.chdir(tmp_path)
    assert cli.main(["demo", "--scenario", "umbrella-upgrade-control-plane"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "ok"
    blueprint = tmp_path / ".sdetkit" / "agent" / "workdir" / "umbrella-blueprint.json"
    assert blueprint.exists()
    blueprint_payload = json.loads(blueprint.read_text(encoding="utf-8"))
    assert blueprint_payload["architecture_layers"][0]["name"] == "experience-surface"
