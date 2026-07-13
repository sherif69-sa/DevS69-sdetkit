from __future__ import annotations

from pathlib import Path

from sdetkit.adoption_surface import discover_adoption_surface


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _proof_commands(payload: dict) -> dict[str, dict]:
    return {str(item["command"]): item for item in payload["recommended_proof_commands"]}


def test_adoption_surface_extracts_literal_jenkins_sh_commands_with_stage_context(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "Jenkinsfile",
        """
pipeline {
  agent any
  stages {
    stage('Test') {
      steps {
        sh 'python -m pytest -q'
      }
    }
    stage("Quality") {
      steps {
        sh("python -m ruff check .")
        sh ('mypy src')
      }
    }
    stage('Security') {
      steps {
        sh "pip-audit"
      }
    }
    stage('Docs') {
      steps {
        sh('mkdocs build --strict')
      }
    }
    stage('Build') {
      steps {
        sh 'python -m compileall src'
        sh 'echo smoke only'
      }
    }
  }
}
""".lstrip(),
    )

    payload = discover_adoption_surface(tmp_path)
    commands = _proof_commands(payload)
    ci_systems = {str(item["name"]) for item in payload["ci_systems"]}

    assert "jenkins" in ci_systems
    assert commands["python -m pytest -q"]["purpose"] == "test"
    assert commands["python -m ruff check ."]["purpose"] == "lint"
    assert commands["mypy src"]["purpose"] == "type"
    assert commands["pip-audit"]["purpose"] == "security"
    assert commands["mkdocs build --strict"]["purpose"] == "docs"
    assert commands["python -m compileall src"]["purpose"] == "unknown"
    assert "echo smoke only" not in commands
    assert commands["python -m pytest -q"]["source"] == {
        "ci_system": "jenkins",
        "file": "Jenkinsfile",
        "stage": "Test",
    }
    assert commands["python -m ruff check ."]["source"]["stage"] == "Quality"
    assert commands["pip-audit"]["source"]["stage"] == "Security"
    assert all(command["auto_run_allowed"] is False for command in commands.values())
    assert all(command["executes_untrusted_code"] is True for command in commands.values())
    assert payload["review_first_unknowns"] == []
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_adoption_surface_reports_dynamic_jenkins_behavior_review_first(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "Jenkinsfile",
        """
@Library('shared-ci') _
node {
  echo 'scripted pipeline'
}
pipeline {
  agent any
  stages {
    stage(STAGE_NAME) {
      steps {
        sh buildCommand()
      }
    }
    stage('Dynamic') {
      steps {
        script {
          sh "${TEST_COMMAND}"
        }
        sh(script: env.TEST_COMMAND)
        sh '''python -m pytest -q'''
      }
    }
  }
}
""".lstrip(),
    )

    payload = discover_adoption_surface(tmp_path)
    commands = _proof_commands(payload)
    unknowns = set(payload["review_first_unknowns"])

    assert commands == {}
    assert "Jenkins shared library detected; external pipeline behavior was not resolved" in unknowns
    assert "Jenkins scripted node block detected; Groovy behavior was not evaluated" in unknowns
    assert "Jenkins pipeline uses a dynamic stage declaration that was not resolved" in unknowns
    assert (
        "Jenkins pipeline has dynamic or unsupported sh content that was not guessed" in unknowns
    )
    assert (
        "Jenkins stage Dynamic uses a script block; Groovy behavior was not evaluated" in unknowns
    )
    assert "Jenkins stage Dynamic has dynamic shell command that was not guessed" in unknowns
    assert (
        "Jenkins stage Dynamic has dynamic or unsupported sh content that was not guessed"
        in unknowns
    )
    assert "Jenkins stage Dynamic has multiline sh content that was not guessed" in unknowns
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_jenkins_extraction_preserves_existing_github_and_gitlab_ci_behavior(
    tmp_path: Path,
) -> None:
    _write(tmp_path / ".github" / "workflows" / "ci.yml", "name: CI\n")
    _write(
        tmp_path / ".gitlab-ci.yml",
        "gitlab_test:\n  script:\n    - python -m pytest -q\n",
    )
    _write(
        tmp_path / "Jenkinsfile",
        "pipeline {\n  stages {\n    stage('Lint') {\n      steps {\n        sh 'ruff check .'\n      }\n    }\n  }\n}\n",
    )

    payload = discover_adoption_surface(tmp_path)
    commands = _proof_commands(payload)
    ci_systems = {str(item["name"]) for item in payload["ci_systems"]}

    assert ci_systems == {"github_actions", "gitlab_ci", "jenkins"}
    assert commands["python -m pytest -q"]["source"] == {
        "ci_system": "gitlab_ci",
        "file": ".gitlab-ci.yml",
        "job": "gitlab_test",
    }
    assert commands["ruff check ."]["source"] == {
        "ci_system": "jenkins",
        "file": "Jenkinsfile",
        "stage": "Lint",
    }
