from __future__ import annotations

from pathlib import Path

from sdetkit.adoption_surface import discover_adoption_surface


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _proof_commands(payload: dict) -> dict[str, dict]:
    return {str(item["command"]): item for item in payload["recommended_proof_commands"]}


def test_adoption_surface_extracts_literal_gitlab_ci_script_commands(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / ".gitlab-ci.yml",
        """
stages:
  - test
variables:
  PIP_CACHE_DIR: .cache/pip
image: python:3.12
pytest_job:
  stage: test
  script:
    - python -m pytest -q
    - python -m ruff check .
    - mypy src
security_scan:
  script: pip-audit
unknown_job:
  script: echo smoke
""".lstrip(),
    )

    payload = discover_adoption_surface(tmp_path)
    commands = _proof_commands(payload)
    ci_systems = {str(item["name"]) for item in payload["ci_systems"]}

    assert "gitlab_ci" in ci_systems
    assert commands["python -m pytest -q"]["purpose"] == "test"
    assert commands["python -m ruff check ."]["purpose"] == "lint"
    assert commands["mypy src"]["purpose"] == "type"
    assert commands["pip-audit"]["purpose"] == "security"
    assert commands["echo smoke"]["purpose"] == "unknown"
    assert commands["python -m pytest -q"]["source"] == {
        "ci_system": "gitlab_ci",
        "file": ".gitlab-ci.yml",
        "job": "pytest_job",
    }
    assert all(command["auto_run_allowed"] is False for command in commands.values())
    assert all(command["executes_untrusted_code"] is True for command in commands.values())
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_adoption_surface_reports_unresolved_gitlab_ci_scripts_review_first(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / ".gitlab-ci.yml",
        """
include:
  - remote: https://example.invalid/template.yml
dynamic_test:
  script: $TEST_COMMAND
anchored_job:
  script: *common_script
""".lstrip(),
    )

    payload = discover_adoption_surface(tmp_path)
    commands = _proof_commands(payload)

    assert "$TEST_COMMAND" not in commands
    assert "*common_script" not in commands
    assert payload["review_first_unknowns"] == [
        "GitLab CI include detected; remote configuration was not resolved",
        "GitLab CI job anchored_job uses YAML anchor or alias content that was not resolved",
        "GitLab CI job dynamic_test has dynamic script command that was not guessed",
    ]
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False
