from __future__ import annotations

from pathlib import Path

from sdetkit.adoption_surface import discover_adoption_surface


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _proof_commands(payload: dict) -> dict[str, dict]:
    return {str(item["command"]): item for item in payload["recommended_proof_commands"]}


def test_adoption_surface_extracts_literal_circleci_run_commands_with_job_context(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / ".circleci" / "config.yml",
        """
version: 2.1
jobs:
  test:
    docker:
      - image: cimg/python:3.12
    steps:
      - checkout
      - run: python -m pytest -q
      - run:
          name: Lint
          command: python -m ruff check .
      - run: {name: Types, command: mypy src}
      - run:
          name: Security
          command: pip-audit
      - run: echo smoke only
  docs:
    docker:
      - image: cimg/python:3.12
    steps:
      - run:
          name: Strict docs
          command: mkdocs build --strict
""".lstrip(),
    )

    payload = discover_adoption_surface(tmp_path)
    commands = _proof_commands(payload)
    ci_systems = {str(item["name"]): item for item in payload["ci_systems"]}

    assert ci_systems["circleci"]["files"] == [".circleci/config.yml"]
    assert commands["python -m pytest -q"]["purpose"] == "test"
    assert commands["python -m ruff check ."]["purpose"] == "lint"
    assert commands["mypy src"]["purpose"] == "type"
    assert commands["pip-audit"]["purpose"] == "security"
    assert commands["mkdocs build --strict"]["purpose"] == "docs"
    assert "echo smoke only" not in commands
    assert commands["python -m pytest -q"]["source"] == {
        "ci_system": "circleci",
        "file": ".circleci/config.yml",
        "job": "test",
    }
    assert commands["python -m ruff check ."]["source"]["step_name"] == "Lint"
    assert commands["mypy src"]["source"]["step_name"] == "Types"
    assert commands["mkdocs build --strict"]["source"] == {
        "ci_system": "circleci",
        "file": ".circleci/config.yml",
        "job": "docs",
        "step_name": "Strict docs",
    }
    assert all(command["auto_run_allowed"] is False for command in commands.values())
    assert all(command["executes_untrusted_code"] is True for command in commands.values())
    assert payload["review_first_unknowns"] == []
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_adoption_surface_reports_dynamic_circleci_behavior_review_first(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / ".circleci" / "config.yaml",
        """
version: 2.1
setup: true
orbs:
  node: circleci/node@6.3.0
parameters:
  test-command:
    type: string
    default: npm test
commands:
  run-tests:
    steps:
      - run: npm test
jobs:
  build:
    parameters:
      executor-tag:
        type: string
    docker:
      - image: cimg/base:stable
    steps:
      - node/test
      - run-tests
      - custom-step:
          value: true
      - run: << pipeline.parameters.test-command >>
      - run:
          name: Environment command
          command: $TEST_COMMAND
      - run:
          name: Multiline
          command: |
            python -m pytest -q
""".lstrip(),
    )

    payload = discover_adoption_surface(tmp_path)
    commands = _proof_commands(payload)
    unknowns = set(payload["review_first_unknowns"])

    assert commands == {}
    expected_unknowns = {
        "CircleCI dynamic configuration detected; continuation behavior was not resolved",
        "CircleCI orbs detected; orb behavior was not resolved",
        "CircleCI pipeline parameters detected; parameter values were not resolved",
        "CircleCI reusable commands detected; command bodies were not expanded",
        "CircleCI job build declares parameters that were not resolved",
        "CircleCI job build invokes orb step node/test; behavior was not resolved",
        "CircleCI job build invokes reusable command run-tests; behavior was not expanded",
        "CircleCI job build invokes custom step custom-step; behavior was not resolved",
        "CircleCI job build has dynamic run content that was not guessed",
        (
            "CircleCI job build step Environment command has dynamic run content "
            "that was not guessed"
        ),
        "CircleCI job build step Multiline has multiline run content that was not guessed",
    }
    assert expected_unknowns <= unknowns
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_circleci_discovery_preserves_existing_ci_provider_behavior(tmp_path: Path) -> None:
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

    payload = discover_adoption_surface(tmp_path)
    commands = _proof_commands(payload)
    ci_systems = {str(item["name"]) for item in payload["ci_systems"]}

    assert ci_systems == {"circleci", "github_actions", "gitlab_ci", "jenkins"}
    assert commands["python -m pytest -q"]["source"]["ci_system"] == "gitlab_ci"
    assert commands["ruff check ."]["source"]["ci_system"] == "jenkins"
    assert commands["mypy src"]["source"] == {
        "ci_system": "circleci",
        "file": ".circleci/config.yml",
        "job": "types",
    }
