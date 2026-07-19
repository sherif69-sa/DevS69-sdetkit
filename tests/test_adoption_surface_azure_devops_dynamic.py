from __future__ import annotations

from pathlib import Path

from sdetkit.adoption_surface import discover_adoption_surface


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _proof_commands(payload: dict) -> dict[str, dict]:
    return {str(item["command"]): item for item in payload["recommended_proof_commands"]}


def test_adoption_surface_reports_dynamic_azure_devops_behavior_review_first(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "azure-pipelines.yaml",
        """
extends:
  template: pipelines/base.yml
variables:
  - group: shared-values
resources:
  repositories:
    - repository: shared
      type: git
jobs:
  - job: dynamic
    strategy:
      matrix:
        py312:
          python.version: "3.12"
    steps:
      - template: pipelines/test.yml
      - task: UsePythonVersion@0
      - script: $(TEST_COMMAND)
      - bash: ${{ parameters.lintCommand }}
      - pwsh: |
          python -m pytest -q
  - deployment: release
    environment: production
    steps:
      - script: echo deploy
""".lstrip(),
    )

    payload = discover_adoption_surface(tmp_path)
    commands = _proof_commands(payload)
    unknowns = set(payload["review_first_unknowns"])

    assert commands == {}
    expected_unknowns = {
        "Azure DevOps templates or extends detected; referenced behavior was not resolved",
        "Azure DevOps variables or variable groups detected; values were not resolved",
        "Azure DevOps external resources or service connections detected; behavior was not resolved",
        "Azure DevOps job dynamic declares strategy or matrix behavior that was not resolved",
        "Azure DevOps job dynamic invokes a template; template behavior was not resolved",
        "Azure DevOps job dynamic invokes task UsePythonVersion@0; task behavior was not resolved",
        "Azure DevOps job dynamic has dynamic script content that was not guessed",
        "Azure DevOps job dynamic has multiline script content that was not guessed",
        "Azure DevOps deployment job release detected; environment behavior was not resolved",
    }
    assert expected_unknowns <= unknowns
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_azure_devops_discovery_preserves_existing_ci_provider_behavior(tmp_path: Path) -> None:
    _write(tmp_path / ".github" / "workflows" / "ci.yml", "name: CI\n")
    _write(
        tmp_path / ".gitlab-ci.yml",
        "gitlab_test:\n  script:\n    - python -m pytest -q\n",
    )
    _write(
        tmp_path / "Jenkinsfile",
        (
            "pipeline {\n  stages {\n    stage('Lint') {\n      steps {\n"
            "        sh 'ruff check .'\n      }\n    }\n  }\n}\n"
        ),
    )
    _write(
        tmp_path / ".circleci" / "config.yml",
        (
            "version: 2.1\njobs:\n  types:\n    docker:\n"
            "      - image: cimg/base:stable\n    steps:\n      - run: mypy src\n"
        ),
    )
    _write(
        tmp_path / "azure-pipelines.yml",
        "jobs:\n  - job: security\n    steps:\n      - script: pip-audit\n",
    )

    payload = discover_adoption_surface(tmp_path)
    commands = _proof_commands(payload)
    ci_systems = {str(item["name"]) for item in payload["ci_systems"]}

    assert ci_systems == {
        "azure_devops",
        "circleci",
        "github_actions",
        "gitlab_ci",
        "jenkins",
    }
    assert commands["python -m pytest -q"]["source"]["ci_system"] == "gitlab_ci"
    assert commands["ruff check ."]["source"]["ci_system"] == "jenkins"
    assert commands["mypy src"]["source"]["ci_system"] == "circleci"
    assert commands["pip-audit"]["source"] == {
        "ci_system": "azure_devops",
        "file": "azure-pipelines.yml",
        "job": "security",
        "task_key": "script",
    }
