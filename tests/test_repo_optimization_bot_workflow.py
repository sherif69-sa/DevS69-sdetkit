from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = Path(".github/workflows/repo-optimization-bot.yml")


def _steps() -> list[dict[str, object]]:
    payload = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return payload["jobs"]["optimize"]["steps"]


def test_repo_optimization_bot_installs_sdetkit_before_module_execution() -> None:
    steps = _steps()
    names = [str(step.get("name", "")) for step in steps]

    assert "Set up Python" in names
    assert "Install SDETKit" in names
    assert "Run optimize lane snapshot" in names
    assert names.index("Install SDETKit") < names.index("Run optimize lane snapshot")

    install_step = next(step for step in steps if step.get("name") == "Install SDETKit")
    run = str(install_step.get("run", ""))

    assert "python -m pip install --upgrade pip" in run
    assert "python -m pip install -c constraints-ci.txt -e ." in run


def test_repo_optimization_bot_keeps_manual_recovery_trigger() -> None:
    payload = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    triggers = payload[True]

    assert "workflow_dispatch" in triggers
    assert "schedule" in triggers


def test_repo_optimization_bot_declares_top_level_permissions() -> None:
    payload = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))

    assert payload["permissions"] == {
        "contents": "read",
        "issues": "write",
    }
    assert "permissions" not in payload["jobs"]["optimize"]
