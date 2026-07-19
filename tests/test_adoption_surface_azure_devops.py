from __future__ import annotations

from pathlib import Path

from sdetkit.adoption_surface import discover_adoption_surface


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _proof_commands(payload: dict) -> dict[str, dict]:
    return {str(item["command"]): item for item in payload["recommended_proof_commands"]}


def test_adoption_surface_extracts_literal_azure_devops_scripts_with_job_context(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "azure-pipelines.yml",
        """
trigger:
  - main
jobs:
  - job: quality
    steps:
      - script: python -m pytest -q
      - bash: python -m ruff check .
      - pwsh: mypy src
      - powershell: pip-audit
      - script: echo smoke only
  - job: docs
    steps:
      - script: mkdocs build --strict
""".lstrip(),
    )

    payload = discover_adoption_surface(tmp_path)
    commands = _proof_commands(payload)
    ci_systems = {str(item["name"]): item for item in payload["ci_systems"]}

    assert ci_systems["azure_devops"]["files"] == ["azure-pipelines.yml"]
    assert commands["python -m pytest -q"]["purpose"] == "test"
    assert commands["python -m ruff check ."]["purpose"] == "lint"
    assert commands["mypy src"]["purpose"] == "type"
    assert commands["pip-audit"]["purpose"] == "security"
    assert commands["mkdocs build --strict"]["purpose"] == "docs"
    assert "echo smoke only" not in commands
    assert commands["python -m pytest -q"]["source"] == {
        "ci_system": "azure_devops",
        "file": "azure-pipelines.yml",
        "job": "quality",
        "task_key": "script",
    }
    assert commands["python -m ruff check ."]["source"]["task_key"] == "bash"
    assert commands["mypy src"]["source"]["task_key"] == "pwsh"
    assert commands["pip-audit"]["source"]["task_key"] == "powershell"
    assert commands["mkdocs build --strict"]["source"] == {
        "ci_system": "azure_devops",
        "file": "azure-pipelines.yml",
        "job": "docs",
        "task_key": "script",
    }
    assert all(command["auto_run_allowed"] is False for command in commands.values())
    assert all(command["executes_untrusted_code"] is True for command in commands.values())
    assert payload["review_first_unknowns"] == []
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False
