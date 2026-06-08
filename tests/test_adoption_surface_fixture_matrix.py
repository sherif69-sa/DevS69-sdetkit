from __future__ import annotations

from pathlib import Path

import pytest

from sdetkit.adoption_learning import build_adoption_learning_payload
from sdetkit.adoption_surface import (
    discover_adoption_surface,
    render_adoption_surface_report,
    validate_adoption_surface_payload,
)

FIXTURE_ROOT = Path("tests/fixtures/adoption_repos")


def _names(items: object) -> set[str]:
    assert isinstance(items, list)
    return {item["name"] for item in items if isinstance(item, dict)}


def _commands(payload: dict[str, object]) -> set[str]:
    commands = payload["recommended_proof_commands"]
    assert isinstance(commands, list)
    return {item["command"] for item in commands if isinstance(item, dict)}


def _unknowns(payload: dict[str, object]) -> set[str]:
    unknowns = payload["review_first_unknowns"]
    assert isinstance(unknowns, list)
    return {str(item) for item in unknowns}


@pytest.mark.parametrize(
    (
        "fixture",
        "languages",
        "package_managers",
        "test_runners",
        "ci_systems",
        "commands",
        "unknown_fragments",
    ),
    [
        (
            "python_pytest_github",
            {"python"},
            {"pip"},
            {"pytest"},
            {"github_actions"},
            {"python -m pytest -q -o addopts="},
            set(),
        ),
        (
            "node_no_test_script",
            {"javascript_typescript"},
            {"npm"},
            set(),
            set(),
            set(),
            {"JavaScript/TypeScript package manifest detected but test command is not proven"},
        ),
        (
            "node_with_test_script",
            {"javascript_typescript"},
            {"npm"},
            {"node_test_script"},
            set(),
            {"npm test"},
            set(),
        ),
        (
            "mixed_python_node",
            {"python", "javascript_typescript"},
            {"pip", "npm"},
            {"pytest"},
            {"github_actions"},
            {"python -m pytest -q -o addopts="},
            {"JavaScript/TypeScript package manifest detected but test command is not proven"},
        ),
        (
            "go_module",
            {"go"},
            {"go_modules"},
            set(),
            set(),
            {"go test ./..."},
            set(),
        ),
        (
            "rust_cargo",
            {"rust"},
            {"cargo"},
            set(),
            set(),
            {"cargo test"},
            set(),
        ),
        (
            "java_maven",
            {"java"},
            {"maven"},
            set(),
            set(),
            {"mvn test"},
            set(),
        ),
        (
            "dotnet_solution",
            {"dotnet"},
            {"nuget"},
            set(),
            set(),
            {"dotnet test"},
            set(),
        ),
        (
            "gitlab_python",
            {"python"},
            {"pip"},
            {"pytest"},
            {"gitlab_ci"},
            {"python -m pytest -q -o addopts="},
            set(),
        ),
        (
            "jenkins_java",
            {"java"},
            {"maven"},
            set(),
            {"jenkins"},
            {"mvn test"},
            set(),
        ),
    ],
)
def test_adoption_surface_fixture_matrix_detects_repo_shapes(
    fixture: str,
    languages: set[str],
    package_managers: set[str],
    test_runners: set[str],
    ci_systems: set[str],
    commands: set[str],
    unknown_fragments: set[str],
) -> None:
    payload = discover_adoption_surface(FIXTURE_ROOT / fixture)

    assert validate_adoption_surface_payload(payload) == []
    assert languages <= _names(payload["detected_languages"])
    assert package_managers <= _names(payload["package_managers"])
    assert test_runners <= _names(payload["test_runners"])
    assert ci_systems <= _names(payload["ci_systems"])
    assert commands <= _commands(payload)
    assert unknown_fragments <= _unknowns(payload)

    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False
    assert all(
        command["auto_run_allowed"] is False for command in payload["recommended_proof_commands"]
    )


@pytest.mark.parametrize(
    "fixture",
    [
        "python_pytest_github",
        "node_no_test_script",
        "node_with_test_script",
        "mixed_python_node",
        "go_module",
        "rust_cargo",
        "java_maven",
        "dotnet_solution",
        "gitlab_python",
        "jenkins_java",
    ],
)
def test_adoption_surface_fixture_reports_remain_operator_readable(fixture: str) -> None:
    payload = discover_adoption_surface(FIXTURE_ROOT / fixture)

    report = render_adoption_surface_report(payload)

    assert "# SDETKit adoption readiness report" in report
    assert "## Detected languages" in report
    assert "## Recommended proof commands" in report
    assert "## Review-first unknowns" in report
    assert "## Authority boundary" in report
    assert "- automation_allowed: false" in report
    assert "- patch_application_allowed: false" in report


def test_adoption_learning_uses_fixture_matrix_as_next_upgrade_source() -> None:
    payload = build_adoption_learning_payload(Path("."))

    assert payload["recommended_next_upgrade"] == "first permissive public repo read-only trial"
    assert "fixture repo matrix" in payload["upgrade_candidates"]
    assert "add fixture repo matrix for non-Python repo shapes" not in payload["learning_gaps"]
    assert payload["recommended_next_upgrade"] == "first permissive public repo read-only trial"
    assert "add fixture coverage for non-GitHub CI providers" not in payload["learning_gaps"]
    assert "add fixtures that prove review-first unknown handling" not in payload["learning_gaps"]
    assert "add local external-root smoke before public repo trials" not in payload["learning_gaps"]
    assert (
        "add public repo eligibility screen before using third-party repos"
        not in payload["learning_gaps"]
    )
    assert "run first permissive public repo read-only trial" in payload["learning_gaps"]


def test_fixture_matrix_proves_review_first_unknown_handling() -> None:
    payload = discover_adoption_surface(FIXTURE_ROOT / "node_no_test_script")

    assert _commands(payload) == set()
    assert _unknowns(payload) == {
        "JavaScript/TypeScript package manifest detected but test command is not proven"
    }
    assert payload["automation_allowed"] is False
    assert all(
        command["auto_run_allowed"] is False for command in payload["recommended_proof_commands"]
    )
