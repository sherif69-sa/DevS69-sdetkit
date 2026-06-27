from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from sdetkit.diagnostic_execution_plan import (
    SCHEMA_VERSION,
    build_diagnostic_execution_plan,
    validate_diagnostic_execution_plan,
    write_diagnostic_execution_plan_artifact,
)


def _surface(*, commands: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {
        "schema_version": "sdetkit.adoption_surface.v1",
        "repo_root": ".",
        "repo_identity": {
            "name": "example",
            "is_current_sdetkit_repo": False,
            "git_detected": True,
            "remote_url": "https://example.com/org/example.git",
        },
        "detected_languages": [
            {
                "name": "python",
                "confidence": "high",
                "evidence": ["pyproject.toml", "src/"],
            }
        ],
        "package_managers": [],
        "test_runners": [],
        "ci_systems": [],
        "security_tools": [],
        "docs_tools": [],
        "release_surfaces": [],
        "artifact_surfaces": [],
        "recommended_proof_commands": commands or [],
        "review_first_unknowns": [],
        "operator_summary": {"status": "read_only_profile_generated", "next_action": "review"},
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def _proof(recommendations: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": "sdetkit.adoption_proof_recommendations.v1",
        "repo_identity": _surface()["repo_identity"],
        "summary": {},
        "proof_recommendations": recommendations,
        "review_first_items": [],
        "rules": {},
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "authority_boundary": {
            "automation_allowed": False,
            "patch_application_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }


def _topology(sequence: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": "sdetkit.adoption_repo_topology.v1",
        "repo_identity": _surface()["repo_identity"],
        "topology": {},
        "review_first_unknowns": [],
        "manual_proof_sequence": sequence,
        "operator_summary": {},
        "rules": {},
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "authority_boundary": {
            "automation_allowed": False,
            "patch_application_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }


def _recommendation(
    command: str,
    *,
    index: int = 1,
    surface: str = "python",
    purpose: str = "test",
    confidence: str = "high",
    level: str = "required",
    cwd: str | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    proof_item: dict[str, object] = {
        "index": index,
        "command": command,
        "surface": surface,
        "purpose": purpose,
        "confidence": confidence,
        "operator_level": level,
        "execution_policy": "manual_only",
        "manual_execution_required": True,
        "auto_run_allowed": False,
    }
    if cwd is not None:
        proof_item["cwd"] = cwd
    topology_item = {
        "step": index,
        "command": command,
        "surface": surface,
        "purpose": purpose,
        "operator_level": level,
        "manual_only": True,
        "auto_run_allowed": False,
    }
    return proof_item, topology_item


def _build(
    recommendations: list[dict[str, object]],
    sequence: list[dict[str, object]],
    *,
    surface: dict[str, object] | None = None,
) -> dict[str, object]:
    source = surface or _surface()
    proof = _proof(recommendations)
    topology = _topology(sequence)
    proof["repo_identity"] = source["repo_identity"]
    topology["repo_identity"] = source["repo_identity"]
    return build_diagnostic_execution_plan(
        ".",
        surface_payload=source,
        proof_payload=proof,
        topology_payload=topology,
    )


def test_plan_builds_ordered_non_executing_commands() -> None:
    pytest_item, pytest_step = _recommendation("python -m pytest -q -o addopts=")
    sphinx_item, sphinx_step = _recommendation(
        "python -m sphinx -W -b html docs docs/_build/html",
        index=2,
        surface="docs",
        purpose="docs",
        level="recommended",
    )
    surface = _surface()
    surface["docs_tools"] = [
        {"name": "sphinx", "confidence": "high", "evidence": ["docs/conf.py"]}
    ]

    payload = _build([pytest_item, sphinx_item], [pytest_step, sphinx_step], surface=surface)

    assert payload["schema_version"] == SCHEMA_VERSION
    assert [item["step"] for item in payload["commands"]] == [1, 2]
    assert payload["commands"][0]["argv"] == ["python", "-m", "pytest", "-q", "-o", "addopts="]
    assert payload["commands"][0]["cwd"] == "."
    assert payload["commands"][0]["surface_confidence"] == "high"
    assert payload["commands"][1]["expected_artifacts"][1]["path"] == "docs/_build/html"
    assert payload["summary"] == {
        "command_count": 2,
        "required_count": 1,
        "recommended_count": 1,
        "review_command_count": 0,
        "review_first_item_count": 0,
        "recommended_next_action": "review_plan_before_execution",
    }
    assert payload["execution_allowed"] is False
    assert payload["authority_boundary"] == {
        "execution_allowed": False,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }
    assert validate_diagnostic_execution_plan(payload) == []


def test_environment_assignment_is_structured_without_shell_execution() -> None:
    proof_item, topology_item = _recommendation(
        "NO_MKDOCS_2_WARNING=1 python -m mkdocs build --strict",
        surface="docs",
        purpose="docs",
        level="recommended",
    )
    surface = _surface()
    surface["docs_tools"] = [
        {"name": "mkdocs", "confidence": "high", "evidence": ["mkdocs.yml", "docs/"]}
    ]

    payload = _build([proof_item], [topology_item], surface=surface)
    command = payload["commands"][0]

    assert command["environment"] == {"NO_MKDOCS_2_WARNING": "1"}
    assert command["argv"] == ["python", "-m", "mkdocs", "build", "--strict"]
    assert command["expected_artifacts"][1]["path"] == "site"
    assert command["execution_allowed"] is False


def test_duplicate_command_and_cwd_are_suppressed() -> None:
    first, first_step = _recommendation("python -m pytest -q", index=1)
    second, second_step = _recommendation("python -m pytest -q", index=2)

    payload = _build([first, second], [first_step, second_step])

    assert payload["summary"]["command_count"] == 1
    assert len(payload["commands"]) == 1


def test_explicit_nested_workspace_cwd_is_preserved() -> None:
    proof_item, topology_item = _recommendation(
        "npm test",
        surface="javascript_typescript",
        confidence="medium",
        cwd="apps/web",
    )
    surface = _surface()
    surface["detected_languages"] = [
        {
            "name": "javascript_typescript",
            "confidence": "medium",
            "evidence": ["package.json"],
        }
    ]

    payload = _build([proof_item], [topology_item], surface=surface)
    command = payload["commands"][0]

    assert command["cwd"] == "apps/web"
    assert command["cwd_confidence"] == "high"
    assert command["command_confidence"] == "medium"


def test_unsafe_cwd_becomes_review_first() -> None:
    proof_item, topology_item = _recommendation("npm test", cwd="../outside")

    payload = _build([proof_item], [topology_item])
    command = payload["commands"][0]

    assert command["cwd"] == "."
    assert command["cwd_confidence"] == "unknown"
    assert command["review_required"] is True
    assert "safe repository-relative path" in command["review_reasons"][0]


def test_multiple_dotnet_roots_are_explicitly_review_first() -> None:
    proof_item, topology_item = _recommendation("dotnet test", surface="dotnet")
    surface = _surface()
    surface["detected_languages"] = [
        {
            "name": "dotnet",
            "confidence": "high",
            "evidence": ["src/App/App.csproj", "tests/App.Tests/App.Tests.csproj"],
        }
    ]

    payload = _build([proof_item], [topology_item], surface=surface)
    command = payload["commands"][0]

    assert command["cwd_confidence"] == "unknown"
    assert command["review_required"] is True
    assert "multiple .NET workspace roots" in command["review_reasons"][0]


def test_shell_control_syntax_is_not_converted_to_argv() -> None:
    proof_item, topology_item = _recommendation("python -m pytest && echo done")

    payload = _build([proof_item], [topology_item])
    command = payload["commands"][0]

    assert command["argv"] == []
    assert command["review_required"] is True
    assert command["execution_allowed"] is False


def test_unknown_command_confidence_is_review_first() -> None:
    proof_item, topology_item = _recommendation("custom-test", confidence="unknown")

    payload = _build([proof_item], [topology_item])

    assert payload["commands"][0]["review_required"] is True
    assert payload["summary"]["review_command_count"] == 1


def test_malformed_or_authority_expanding_source_is_rejected() -> None:
    proof_item, topology_item = _recommendation("python -m pytest")
    proof = _proof([proof_item])
    topology = _topology([topology_item])
    surface = _surface()

    bad_schema = copy.deepcopy(proof)
    bad_schema["schema_version"] = "unsupported"
    with pytest.raises(ValueError, match="schema is not supported"):
        build_diagnostic_execution_plan(
            ".",
            surface_payload=surface,
            proof_payload=bad_schema,
            topology_payload=topology,
        )

    expanded = copy.deepcopy(proof)
    expanded["automation_allowed"] = True
    with pytest.raises(ValueError, match="expands authority"):
        build_diagnostic_execution_plan(
            ".",
            surface_payload=surface,
            proof_payload=expanded,
            topology_payload=topology,
        )


def test_topology_cannot_invent_a_command() -> None:
    proof_item, _ = _recommendation("python -m pytest")
    _, topology_item = _recommendation("python -m mypy src")

    with pytest.raises(ValueError, match="commands absent"):
        _build([proof_item], [topology_item])


def test_empty_plan_is_a_structured_non_crashing_outcome() -> None:
    payload = _build([], [])

    assert payload["plan_status"] == "generated"
    assert payload["commands"] == []
    assert payload["summary"]["command_count"] == 0
    assert payload["execution_allowed"] is False


def test_artifact_write_is_deterministic_and_does_not_mutate_target(tmp_path: Path) -> None:
    target = tmp_path / "repo with spaces"
    target.mkdir()
    marker = target / "README.md"
    marker.write_text("unchanged\n", encoding="utf-8")
    proof_item, topology_item = _recommendation("python -m pytest")
    surface = _surface()
    surface["repo_root"] = target.as_posix()

    surface_path = tmp_path / "surface.json"
    proof_path = tmp_path / "proof.json"
    topology_path = tmp_path / "topology.json"
    surface_path.write_text(json.dumps(surface), encoding="utf-8")
    proof_path.write_text(json.dumps(_proof([proof_item])), encoding="utf-8")
    topology_path.write_text(json.dumps(_topology([topology_item])), encoding="utf-8")
    out_a = tmp_path / "a.json"
    out_b = tmp_path / "b.json"

    write_diagnostic_execution_plan_artifact(
        repo_root=target,
        surface_json=surface_path,
        proof_json=proof_path,
        topology_json=topology_path,
        out=out_a,
    )
    write_diagnostic_execution_plan_artifact(
        repo_root=target,
        surface_json=surface_path,
        proof_json=proof_path,
        topology_json=topology_path,
        out=out_b,
    )

    assert out_a.read_bytes() == out_b.read_bytes()
    assert marker.read_text(encoding="utf-8") == "unchanged\n"
