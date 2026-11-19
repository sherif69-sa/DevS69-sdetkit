"""Tests for sdetkit cockpit, radar, and scan 360-degree quality intelligence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import cli, cockpit

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_gather_workspace_intel() -> None:
    intel = cockpit.gather_workspace_intel(REPO_ROOT)
    assert intel["repo_name"] == REPO_ROOT.name
    assert "branch" in intel
    assert "commit" in intel
    assert "dirty" in intel
    assert "Python" in intel["surfaces"]
    assert "python_version" in intel


def test_run_radar_checks() -> None:
    res = cockpit.run_radar_checks(REPO_ROOT, scan=False)
    assert res["schema_version"] == "sdetkit.cockpit.v1"
    assert res["workspace"]["repo_name"] == REPO_ROOT.name
    assert res["doctor"]["status"] in ("pass", "needs_attention")
    assert res["mcp"]["tool_count"] == 16
    assert "verify_change" in res["mcp"]["active_tools"]
    assert "gate_fast" in res["mcp"]["active_tools"]
    assert "auto_fix" in res["mcp"]["active_tools"]
    assert "run_mutation" in res["mcp"]["active_tools"]
    assert "hunt_flakes" in res["mcp"]["active_tools"]
    assert "select_impacted_tests" in res["mcp"]["active_tools"]
    assert "manage_test_quarantine" in res["mcp"]["active_tools"]
    assert "evaluate_blast_radius" in res["mcp"]["active_tools"]
    assert "heal_workspace" in res["mcp"]["active_tools"]
    assert "inject_chaos" in res["mcp"]["active_tools"]
    assert "shard_test_suite" in res["mcp"]["active_tools"]
    assert "query_reliability_trends" in res["mcp"]["active_tools"]
    assert "classify_flake_risk" in res["mcp"]["active_tools"]
    assert "run_polyglot_tests" in res["mcp"]["active_tools"]
    assert "trend" in res
    assert res["mutation"]["status"] == "active"
    assert "verdict" in res
    assert "recommendation" in res


def test_render_cockpit_view_ascii_discipline() -> None:
    data = cockpit.run_radar_checks(REPO_ROOT, scan=False)
    view = cockpit.render_cockpit_view(data, use_ascii=True)
    assert "DEVS69 SDETKIT 2.0" in view
    assert "QUALITY COCKPIT & TEST RADAR" in view
    assert "[ RADAR DIMENSIONS & QUALITY HEALTH ]" in view
    assert "[ MCP AGENT SUPER-BRIDGE ]" in view
    assert "[ VERDICT & ACTION ]" in view
    # Verify strict ASCII discipline
    assert all(ord(c) < 128 for c in view)


def test_render_cockpit_markdown_ascii_discipline() -> None:
    data = cockpit.run_radar_checks(REPO_ROOT, scan=False)
    md = cockpit.render_cockpit_markdown(data)
    assert "# SDETKit 2.0 Quality Radar" in md
    assert "### Radar Dimensions" in md
    assert "### MCP Agent Super-Bridge" in md
    assert all(ord(c) < 128 for c in md)


def test_render_cockpit_html_ascii_discipline() -> None:
    data = cockpit.run_radar_checks(REPO_ROOT, scan=False)
    html_doc = cockpit.render_cockpit_html(data)
    assert "<!DOCTYPE html>" in html_doc
    assert "SDETKit 2.0" in html_doc
    assert "gauge-circle" in html_doc
    assert "MCP Agent Super-Bridge" in html_doc
    assert all(ord(c) < 128 for c in html_doc)


def test_cockpit_cli_main_text(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cockpit.main(["--repo-root", str(REPO_ROOT), "--format", "text"])
    captured = capsys.readouterr()
    assert rc in (0, 1)
    assert "DEVS69 SDETKIT 2.0" in captured.out
    assert "VERDICT" in captured.out


def test_cockpit_cli_main_json(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cockpit.main(["--repo-root", str(REPO_ROOT), "--format", "json"])
    captured = capsys.readouterr()
    assert rc in (0, 1)
    payload = json.loads(captured.out)
    assert payload["schema_version"] == "sdetkit.cockpit.v1"
    assert payload["mcp"]["tool_count"] == 16
    assert "manage_test_quarantine" in payload["mcp"]["active_tools"]
    assert "evaluate_blast_radius" in payload["mcp"]["active_tools"]
    assert "heal_workspace" in payload["mcp"]["active_tools"]
    assert "inject_chaos" in payload["mcp"]["active_tools"]
    assert "shard_test_suite" in payload["mcp"]["active_tools"]
    assert "query_reliability_trends" in payload["mcp"]["active_tools"]
    assert "classify_flake_risk" in payload["mcp"]["active_tools"]
    assert "run_polyglot_tests" in payload["mcp"]["active_tools"]


def test_cockpit_cli_format_md(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cockpit.main(["--repo-root", str(REPO_ROOT), "--format", "md"])
    captured = capsys.readouterr()
    assert rc in (0, 1)
    assert "# SDETKit 2.0 Quality Radar" in captured.out
    assert "### Radar Dimensions" in captured.out


def test_cockpit_cli_format_html(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cockpit.main(["--repo-root", str(REPO_ROOT), "--format", "html"])
    captured = capsys.readouterr()
    assert rc in (0, 1)
    assert "<!DOCTYPE html>" in captured.out
    assert "Release Confidence Radar" in captured.out


def test_cockpit_cli_html_flag(tmp_path: Path) -> None:
    target_html = tmp_path / "dashboard.html"
    rc = cockpit.main(["--repo-root", str(REPO_ROOT), "--html", str(target_html)])
    assert rc in (0, 1)
    assert target_html.is_file()
    content = target_html.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "gauge-circle" in content


def test_cockpit_cli_step_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    summary_file = tmp_path / "step_summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))
    rc = cockpit.main(["--repo-root", str(REPO_ROOT), "--step-summary"])
    assert rc in (0, 1)
    assert summary_file.is_file()
    summary_content = summary_file.read_text(encoding="utf-8")
    assert "# SDETKit 2.0 Quality Radar" in summary_content


def test_cockpit_watch_loop() -> None:
    rc = cockpit.run_watch_loop(REPO_ROOT, poll_interval=0.01, max_iterations=1)
    assert rc == 0


def test_cockpit_cli_agent_config(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cockpit.main(["--agent-config"])
    captured = capsys.readouterr()
    assert rc == 0
    assert ".mcp.json" in captured.out
    assert "CLAUDE.md" in captured.out
    assert "AGENTS.md" in captured.out
    assert "verify_change" in captured.out


def test_cockpit_cli_init_agent(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cockpit.main(["--repo-root", str(tmp_path), "--init-agent"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "Scaffolded AI agent bridge files" in captured.out
    assert (tmp_path / "CLAUDE.md").is_file()
    assert (tmp_path / "AGENTS.md").is_file()
    assert (tmp_path / ".mcp.json").is_file()

    # Second invocation without --force notes files exist
    rc2 = cockpit.main(["--repo-root", str(tmp_path), "--init-agent"])
    captured2 = capsys.readouterr()
    assert rc2 == 0
    assert "AI agent bridge files already exist" in captured2.out


def test_cockpit_scan_mode(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cockpit.main(["--repo-root", str(REPO_ROOT), "--scan"])
    captured = capsys.readouterr()
    assert rc in (0, 1)
    assert "ZERO-TO-VALUE QUALITY SCAN" in captured.out
    assert "Security & Secrets" in captured.out


def test_cli_dispatch_cockpit_and_radar() -> None:
    assert "cockpit" in cli.COMMANDS
    assert "radar" in cli.COMMANDS
    assert "scan" in cli.COMMANDS
    assert cli.COMMANDS["cockpit"].module == "sdetkit.cockpit"
    assert cli.COMMANDS["radar"].module == "sdetkit.cockpit"
    assert cli.COMMANDS["scan"].module == "sdetkit.cockpit"
