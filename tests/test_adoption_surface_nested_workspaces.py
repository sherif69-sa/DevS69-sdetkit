from __future__ import annotations

import json
from pathlib import Path

from sdetkit.adoption_proof_recommendations import (
    build_proof_recommendations_payload,
    render_proof_recommendations_text,
)
from sdetkit.adoption_surface import (
    discover_adoption_surface,
    render_adoption_surface_report,
    validate_adoption_surface_payload,
)

FIXTURE = Path("tests/fixtures/adoption_repos/mixed_nested_workspaces")
ADMIN_WORKSPACE = Path("apps", "admin").as_posix()
WEB_WORKSPACE = Path("apps", "web").as_posix()
API_WORKSPACE = Path("services", "api").as_posix()
WORKSPACES = {ADMIN_WORKSPACE, WEB_WORKSPACE, API_WORKSPACE}


def _names(items: object) -> set[str]:
    assert isinstance(items, list)
    return {str(item["name"]) for item in items if isinstance(item, dict)}


def _workspace_commands(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    raw_commands = payload["recommended_proof_commands"]
    assert isinstance(raw_commands, list)
    scoped: dict[str, dict[str, object]] = {}
    for item in raw_commands:
        if not isinstance(item, dict):
            continue
        source = item.get("source")
        if not isinstance(source, dict):
            continue
        working_directory = str(source.get("working_directory", ""))
        if working_directory:
            scoped[working_directory] = item
    return scoped


def _workspace_source(workspace: str) -> dict[str, str]:
    return {
        "scope": "nested_workspace",
        "file": f"{workspace}/package.json",
        "working_directory": workspace,
    }


def _scope_text(workspace: str) -> str:
    return f"working_directory={workspace}"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_nested_mixed_workspaces_emit_scoped_manual_proof() -> None:
    payload = discover_adoption_surface(FIXTURE)

    assert validate_adoption_surface_payload(payload) == []
    assert {"python", "javascript_typescript"} <= _names(payload["detected_languages"])
    assert {"pip", "npm"} <= _names(payload["package_managers"])
    assert {"pytest", "node_test_script"} <= _names(payload["test_runners"])

    scoped = _workspace_commands(payload)
    assert set(scoped) == WORKSPACES
    assert scoped[API_WORKSPACE]["command"] == "python -m pytest -q -o addopts="
    assert scoped[ADMIN_WORKSPACE]["command"] == "npm test"
    assert scoped[WEB_WORKSPACE]["command"] == "npm test"
    assert scoped[ADMIN_WORKSPACE]["source"] == _workspace_source(ADMIN_WORKSPACE)
    assert scoped[WEB_WORKSPACE]["source"] == _workspace_source(WEB_WORKSPACE)
    assert payload["review_first_unknowns"] == []
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False
    assert all(item["auto_run_allowed"] is False for item in scoped.values())


def test_nested_workspace_context_survives_proof_recommendations() -> None:
    payload = build_proof_recommendations_payload(FIXTURE)
    recommendations = payload["proof_recommendations"]
    assert isinstance(recommendations, list)

    by_directory = {
        str(item["working_directory"]): item
        for item in recommendations
        if isinstance(item, dict) and item.get("working_directory")
    }
    assert set(by_directory) == WORKSPACES
    assert by_directory[API_WORKSPACE]["operator_level"] == "required"
    assert by_directory[ADMIN_WORKSPACE]["source"] == _workspace_source(ADMIN_WORKSPACE)
    assert by_directory[WEB_WORKSPACE]["source"] == _workspace_source(WEB_WORKSPACE)
    assert all(item["execution_policy"] == "manual_only" for item in by_directory.values())
    assert all(item["auto_run_allowed"] is False for item in by_directory.values())

    text = render_proof_recommendations_text(payload)
    assert all(_scope_text(workspace) in text for workspace in WORKSPACES)


def test_nested_workspace_reports_show_operator_scope() -> None:
    report = render_adoption_surface_report(discover_adoption_surface(FIXTURE))

    assert all(_scope_text(workspace) in report for workspace in WORKSPACES)
    assert "auto_run_allowed=false" in report


def test_unproven_nested_workspaces_remain_review_first(tmp_path: Path) -> None:
    python_workspace = tmp_path / "services" / "worker"
    python_workspace.mkdir(parents=True)
    (python_workspace / "pyproject.toml").write_text(
        '[project]\nname = "worker"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )

    node_workspace = tmp_path / "apps" / "portal"
    node_workspace.mkdir(parents=True)
    (node_workspace / "package.json").write_text(
        '{"name": "portal", "private": true}\n',
        encoding="utf-8",
    )

    payload = discover_adoption_surface(tmp_path)
    node_scope = Path("apps", "portal").as_posix()
    python_scope = Path("services", "worker").as_posix()

    assert payload["review_first_unknowns"] == [
        f"JavaScript/TypeScript workspace {node_scope} detected but test command is not proven",
        f"Python workspace {python_scope} detected but test command is not proven",
    ]
    assert payload["recommended_proof_commands"] == []
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False


def test_mixed_workspace_identity_excludes_generated_and_vendored_manifests(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "services" / "api" / "pyproject.toml",
        '[project]\nname = "api"\nversion = "0.1.0"\n'
        '[project.optional-dependencies]\ntest = ["pytest"]\n',
    )
    _write(
        tmp_path / "apps" / "admin" / "package.json",
        '{"name":"admin","scripts":{"test":"node --test"}}\n',
    )
    _write(
        tmp_path / "apps" / "web" / "package.json",
        '{"name":"web","scripts":{"test":"node --test"}}\n',
    )
    _write(
        tmp_path / "crates" / "native" / "Cargo.toml",
        '[package]\nname = "native"\nversion = "0.1.0"\nedition = "2021"\n',
    )

    _write(
        tmp_path / "services" / "api" / "build" / "generated" / "pyproject.toml",
        '[project]\nname = "generated"\nversion = "0.1.0"\ndependencies = ["pytest"]\n',
    )
    _write(
        tmp_path / "apps" / "admin" / "node_modules" / "generated" / "package.json",
        '{"name":"generated","scripts":{"test":"node --test"}}\n',
    )
    _write(
        tmp_path / "crates" / "native" / "target" / "dependency" / "Cargo.toml",
        '[package]\nname = "dependency"\nversion = "0.1.0"\nedition = "2021"\n',
    )
    _write(
        tmp_path / "vendor" / "portal" / "package.json",
        '{"name":"vendor-portal","scripts":{"test":"node --test"}}\n',
    )

    payload = discover_adoption_surface(tmp_path)
    scoped = _workspace_commands(payload)

    expected = {
        Path("apps", "admin").as_posix(),
        Path("apps", "web").as_posix(),
        Path("crates", "native").as_posix(),
        Path("services", "api").as_posix(),
    }
    assert set(scoped) == expected
    assert scoped[Path("crates", "native").as_posix()]["command"] == "cargo test"
    assert payload["review_first_unknowns"] == []
    assert all(item["auto_run_allowed"] is False for item in scoped.values())

    npm_owners = sorted(
        workspace for workspace, item in scoped.items() if item["command"] == "npm test"
    )
    assert npm_owners == [Path("apps", "admin").as_posix(), Path("apps", "web").as_posix()]


def test_mixed_workspace_identity_is_serialization_deterministic(tmp_path: Path) -> None:
    _write(
        tmp_path / "apps" / "web" / "package.json",
        '{"name":"web","scripts":{"test":"node --test"}}\n',
    )
    _write(
        tmp_path / "services" / "api" / "pyproject.toml",
        '[project]\nname = "api"\nversion = "0.1.0"\ndependencies = ["pytest"]\n',
    )
    _write(
        tmp_path / "crates" / "native" / "Cargo.toml",
        '[package]\nname = "native"\nversion = "0.1.0"\nedition = "2021"\n',
    )

    first = discover_adoption_surface(tmp_path)
    second = discover_adoption_surface(tmp_path)

    assert json.dumps(first, sort_keys=True, separators=(",", ":")) == json.dumps(
        second,
        sort_keys=True,
        separators=(",", ":"),
    )
    first_commands = first["recommended_proof_commands"]
    assert isinstance(first_commands, list)
    identities = [
        (
            str(item["surface"]),
            str(item["command"]),
            str(item["source"]["working_directory"]),
            str(item["source"]["file"]),
        )
        for item in first_commands
        if isinstance(item, dict) and isinstance(item.get("source"), dict)
    ]
    assert identities == sorted(identities)
