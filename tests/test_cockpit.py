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
    assert res["mcp"]["tool_count"] == 6
    assert "verify_change" in res["mcp"]["active_tools"]
    assert "gate_fast" in res["mcp"]["active_tools"]
    assert "auto_fix" in res["mcp"]["active_tools"]
    assert "run_mutation" in res["mcp"]["active_tools"]
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
    assert payload["mcp"]["tool_count"] == 6


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
