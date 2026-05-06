from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from sdetkit import investigate


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = "src"
    return env


def test_repo_investigation_wraps_boost_and_keeps_safety_flags(tmp_path):
    root = tmp_path
    src = root / "src" / "sdetkit"
    src.mkdir(parents=True)
    (src / "netclient.py").write_text("def get_json():\n    return {}\n", encoding="utf-8")
    tests = root / "tests"
    tests.mkdir()
    (tests / "test_netclient.py").write_text(
        "def test_get_json():\n    assert True\n", encoding="utf-8"
    )
    workflows = root / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text("name: CI\n", encoding="utf-8")

    payload = investigate._payload_for_repo(str(root))

    assert payload["schema_version"] == "sdetkit.investigate.repo.v1"
    assert payload["diagnostic_only"] is True
    assert payload["automation_allowed"] is False
    assert payload["repo_shape"] == {"source_files": 1, "test_files": 1, "workflow_files": 1}
    assert payload["source_engines"] == ["boost", "index-style repo scan"]
    assert payload["top_surfaces"][0]["name"] == "netclient"
    assert payload["top_surfaces"][0]["production_files"] == ["src/sdetkit/netclient.py"]
    assert payload["top_surfaces"][0]["test_files"] == ["tests/test_netclient.py"]
    assert payload["boost_summary"]["summary"]


def test_repo_investigation_json_cli_writes_output(tmp_path, capsys):
    root = tmp_path
    (root / "src").mkdir()
    (root / "src" / "surface.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    out = tmp_path / "repo.json"

    rc = investigate.main(["repo", "--root", str(root), "--format", "json", "--out", str(out)])

    assert rc == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    printed = json.loads(capsys.readouterr().out)
    assert written["schema_version"] == "sdetkit.investigate.repo.v1"
    assert printed["schema_version"] == "sdetkit.investigate.repo.v1"
    assert written["command"] == "investigate repo"
    assert written["automation_allowed"] is False


def test_repo_investigation_markdown_cli(tmp_path, capsys):
    root = tmp_path
    (root / "src").mkdir()
    (root / "src" / "surface.py").write_text("def run():\n    return 1\n", encoding="utf-8")

    rc = investigate.main(["repo", "--root", str(root), "--format", "markdown"])

    assert rc == 0
    rendered = capsys.readouterr().out
    assert "# Repository investigation" in rendered
    assert "diagnostic only: **True**" in rendered
    assert "automation allowed: **False**" in rendered
    assert "## Top surfaces" in rendered
    assert "investigate surface --surface" in rendered


def test_repo_investigation_missing_root_returns_2(tmp_path, capsys):
    missing = tmp_path / "missing"

    rc = investigate.main(["repo", "--root", str(missing), "--format", "json"])

    assert rc == 2
    assert "repository root does not exist" in capsys.readouterr().err


def test_python_m_sdetkit_investigate_repo_outputs_json(tmp_path):
    root = tmp_path
    (root / "src").mkdir()
    (root / "src" / "surface.py").write_text("def run():\n    return 1\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "investigate",
            "repo",
            "--root",
            str(root),
            "--format",
            "json",
        ],
        cwd=Path.cwd(),
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "sdetkit.investigate.repo.v1"
    assert payload["repo_shape"]["source_files"] == 1
    assert payload["automation_allowed"] is False
