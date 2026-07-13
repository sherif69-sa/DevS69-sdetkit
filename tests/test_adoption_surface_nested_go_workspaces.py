from __future__ import annotations

from pathlib import Path

import pytest

from sdetkit.adoption_proof_recommendations import (
    build_proof_recommendations_payload,
    render_proof_recommendations_text,
)
from sdetkit.adoption_surface import (
    discover_adoption_surface,
    render_adoption_surface_report,
    validate_adoption_surface_payload,
)

FIXTURE = Path("tests/fixtures/adoption_repos/mixed_nested_go_workspaces")
API_WORKSPACE = Path("services", "api").as_posix()
WORKER_WORKSPACE = Path("services", "worker").as_posix()
WORKSPACES = {API_WORKSPACE, WORKER_WORKSPACE}


def _named(items: object) -> dict[str, dict[str, object]]:
    assert isinstance(items, list)
    return {
        str(item["name"]): item for item in items if isinstance(item, dict) and item.get("name")
    }


def _scoped_commands(payload: dict[str, object]) -> dict[str, list[dict[str, object]]]:
    raw_commands = payload["recommended_proof_commands"]
    assert isinstance(raw_commands, list)
    scoped: dict[str, list[dict[str, object]]] = {}
    for item in raw_commands:
        if not isinstance(item, dict):
            continue
        source = item.get("source")
        if not isinstance(source, dict):
            continue
        workspace = str(source.get("working_directory", ""))
        if workspace:
            scoped.setdefault(workspace, []).append(item)
    return scoped


def _command_names(items: list[dict[str, object]]) -> set[str]:
    return {str(item["command"]) for item in items}


def _source(workspace: str, file_name: str) -> dict[str, str]:
    return {
        "scope": "nested_workspace",
        "file": f"{workspace}/{file_name}",
        "working_directory": workspace,
    }


def test_nested_go_workspaces_emit_scoped_test_and_explicit_security_proof() -> None:
    payload = discover_adoption_surface(FIXTURE)

    assert validate_adoption_surface_payload(payload) == []
    languages = _named(payload["detected_languages"])
    package_managers = _named(payload["package_managers"])
    test_runners = _named(payload["test_runners"])
    security_tools = _named(payload["security_tools"])

    expected_go_files = {
        f"{workspace}/{file_name}" for workspace in WORKSPACES for file_name in ("go.mod", "go.sum")
    }
    assert set(languages["go"]["evidence"]) == expected_go_files
    assert set(package_managers["go_modules"]["files"]) == expected_go_files
    assert test_runners["go_test"]["commands"] == ["go test ./..."]

    security_file = f"{API_WORKSPACE}/scripts/security.sh"
    assert security_tools["govulncheck"]["evidence"] == [security_file]

    scoped = _scoped_commands(payload)
    assert set(scoped) == WORKSPACES
    assert _command_names(scoped[API_WORKSPACE]) == {"go test ./...", "govulncheck ./..."}
    assert _command_names(scoped[WORKER_WORKSPACE]) == {"go test ./..."}

    api_test = next(item for item in scoped[API_WORKSPACE] if item["command"] == "go test ./...")
    api_security = next(
        item for item in scoped[API_WORKSPACE] if item["command"] == "govulncheck ./..."
    )
    worker_test = scoped[WORKER_WORKSPACE][0]
    assert api_test["source"] == _source(API_WORKSPACE, "go.mod")
    assert api_security["source"] == _source(API_WORKSPACE, "scripts/security.sh")
    assert worker_test["source"] == _source(WORKER_WORKSPACE, "go.mod")

    assert payload["review_first_unknowns"] == []
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False
    assert all(item["auto_run_allowed"] is False for items in scoped.values() for item in items)


def test_nested_go_scope_survives_recommendations_and_reports() -> None:
    surface = discover_adoption_surface(FIXTURE)
    recommendations = build_proof_recommendations_payload(FIXTURE, surface_payload=surface)
    raw_items = recommendations["proof_recommendations"]
    assert isinstance(raw_items, list)

    scoped = {
        workspace: [
            item
            for item in raw_items
            if isinstance(item, dict) and item.get("working_directory") == workspace
        ]
        for workspace in WORKSPACES
    }
    assert _command_names(scoped[API_WORKSPACE]) == {"go test ./...", "govulncheck ./..."}
    assert _command_names(scoped[WORKER_WORKSPACE]) == {"go test ./..."}

    api_test = next(item for item in scoped[API_WORKSPACE] if item["command"] == "go test ./...")
    api_security = next(
        item for item in scoped[API_WORKSPACE] if item["command"] == "govulncheck ./..."
    )
    assert api_test["operator_level"] == "required"
    assert api_security["operator_level"] == "review_first"
    assert all(
        item["execution_policy"] == "manual_only" for items in scoped.values() for item in items
    )
    assert all(item["auto_run_allowed"] is False for items in scoped.values() for item in items)

    proof_text = render_proof_recommendations_text(recommendations)
    surface_report = render_adoption_surface_report(surface)
    for workspace in WORKSPACES:
        scope = f"working_directory={workspace}"
        assert scope in proof_text
        assert scope in surface_report


def test_nested_go_mod_alone_does_not_infer_govulncheck(tmp_path: Path) -> None:
    workspace = tmp_path / "services" / "api"
    workspace.mkdir(parents=True)
    (workspace / "go.mod").write_text("module example.com/api\n\ngo 1.23\n", encoding="utf-8")

    payload = discover_adoption_surface(tmp_path)
    security_tools = _named(payload["security_tools"])
    scoped = _scoped_commands(payload)
    workspace_name = Path("services", "api").as_posix()

    assert "govulncheck" not in security_tools
    assert _command_names(scoped[workspace_name]) == {"go test ./..."}
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False


@pytest.mark.parametrize(
    ("relative_path", "content"),
    [
        ("Makefile", "security:\n\tgovulncheck ./...\n"),
        ("scripts/security.sh", "#!/usr/bin/env sh\nset -eu\ngovulncheck ./...\n"),
        (
            ".github/workflows/security.yml",
            "jobs:\n  scan:\n    steps:\n      - run: govulncheck ./...\n",
        ),
    ],
)
def test_nested_go_security_requires_workspace_owned_literal_evidence(
    tmp_path: Path,
    relative_path: str,
    content: str,
) -> None:
    workspace = tmp_path / "services" / "api"
    workspace.mkdir(parents=True)
    (workspace / "go.mod").write_text("module example.com/api\n\ngo 1.23\n", encoding="utf-8")
    evidence = workspace / relative_path
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(content, encoding="utf-8")

    payload = discover_adoption_surface(tmp_path)
    scoped = _scoped_commands(payload)
    workspace_name = Path("services", "api").as_posix()
    security_file = f"{workspace_name}/{relative_path}"

    assert _named(payload["security_tools"])["govulncheck"]["evidence"] == [security_file]
    security = next(
        item for item in scoped[workspace_name] if item["command"] == "govulncheck ./..."
    )
    assert security["source"] == _source(workspace_name, relative_path)
    assert security["purpose"] == "security"
    assert security["auto_run_allowed"] is False
