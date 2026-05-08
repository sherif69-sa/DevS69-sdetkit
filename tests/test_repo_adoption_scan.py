from __future__ import annotations

import json
from pathlib import Path

from sdetkit import repo_adoption_scan
from sdetkit.cli import main as top_level_main


def test_repo_adoption_scan_detects_stack_and_gaps(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# demo\n", encoding="utf-8")

    payload = repo_adoption_scan.build_repo_adoption_scan(tmp_path)

    assert payload["schema_version"] == "sdetkit.repo_adoption_scan.v1"
    assert payload["stack"]["python"] is True
    assert payload["stack"]["has_tests"] is False
    codes = {gap["code"] for gap in payload["adoption_gaps"]}
    assert "TEST_SURFACE_MISSING" in codes
    assert "CI_CONTRACT_MISSING" in codes
    assert any("sdetkit review" in command for command in payload["recommended_commands"])


def test_repo_adoption_scan_ready_repo_has_canonical_commands(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# demo\n", encoding="utf-8")
    (tmp_path / "LICENSE").write_text("MIT\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_smoke.py").write_text("def test_smoke(): assert True\n", encoding="utf-8")
    workflow = tmp_path / ".github" / "workflows"
    workflow.mkdir(parents=True)
    (workflow / "ci.yml").write_text("name: ci\n", encoding="utf-8")

    payload = repo_adoption_scan.build_repo_adoption_scan(tmp_path)

    assert payload["recommendation"] == "READY_FOR_CANONICAL_ADOPTION"
    assert payload["ok"] is True
    assert payload["risk_score"] == 0
    assert payload["next_owner_action"] == "Adopt the canonical gate/review path in CI now."


def test_top_level_cli_adopt_scan_passthrough(tmp_path: Path) -> None:
    out = tmp_path / "adopt-scan.json"
    (tmp_path / "package.json").write_text('{"scripts":{"test":"node test.js"}}\n', encoding="utf-8")

    rc = top_level_main(["adopt-scan", str(tmp_path), "--format", "json", "--out", str(out)])

    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["stack"]["javascript"] is True
    assert payload["adoption_gaps"]
