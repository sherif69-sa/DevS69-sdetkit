from __future__ import annotations

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

FIXTURE = Path("tests/fixtures/adoption_repos/mixed_dotnet_workspaces")
ORDERS_WORKSPACE = Path("services", "orders").as_posix()
BILLING_WORKSPACE = Path("services", "billing").as_posix()
LEGACY_WORKSPACE = Path("services", "legacy").as_posix()
CATALOG_PROJECT = Path("services", "catalog", "Catalog.csproj").as_posix()
WORKSPACES = {ORDERS_WORKSPACE, BILLING_WORKSPACE, LEGACY_WORKSPACE}


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


def _test_project_xml(*, package_reference: bool = False) -> str:
    package = (
        '<PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.10.0" />'
        if package_reference
        else ""
    )
    return (
        '<Project Sdk="Microsoft.NET.Sdk">'
        "<PropertyGroup><TargetFramework>net8.0</TargetFramework>"
        + ("" if package_reference else "<IsTestProject>true</IsTestProject>")
        + "</PropertyGroup><ItemGroup>"
        + package
        + "</ItemGroup></Project>\n"
    )


def test_dotnet_workspaces_emit_only_explicit_test_project_proof() -> None:
    payload = discover_adoption_surface(FIXTURE)

    assert validate_adoption_surface_payload(payload) == []
    languages = _named(payload["detected_languages"])
    managers = _named(payload["package_managers"])
    runners = _named(payload["test_runners"])
    scoped = _scoped_commands(payload)

    assert set(languages["csharp"]["evidence"]) == {
        f"{ORDERS_WORKSPACE}/Orders.Tests.csproj",
        CATALOG_PROJECT,
    }
    assert set(languages["fsharp"]["evidence"]) == {f"{BILLING_WORKSPACE}/Billing.Tests.fsproj"}
    assert set(languages["visual_basic"]["evidence"]) == {f"{LEGACY_WORKSPACE}/Legacy.Tests.vbproj"}
    assert set(managers["nuget"]["files"]) == {
        f"{ORDERS_WORKSPACE}/Orders.Tests.csproj",
        f"{ORDERS_WORKSPACE}/packages.lock.json",
        f"{BILLING_WORKSPACE}/Billing.Tests.fsproj",
        f"{LEGACY_WORKSPACE}/Legacy.Tests.vbproj",
        CATALOG_PROJECT,
        "services/Directory.Packages.props",
    }
    assert set(scoped) == WORKSPACES
    assert [item["command"] for item in scoped[ORDERS_WORKSPACE]] == [
        "dotnet test Orders.Tests.csproj"
    ]
    assert [item["command"] for item in scoped[BILLING_WORKSPACE]] == [
        "dotnet test Billing.Tests.fsproj"
    ]
    assert [item["command"] for item in scoped[LEGACY_WORKSPACE]] == [
        "dotnet test Legacy.Tests.vbproj"
    ]
    assert set(runners["dotnet_test"]["commands"]) == {
        "dotnet test Orders.Tests.csproj",
        "dotnet test Billing.Tests.fsproj",
        "dotnet test Legacy.Tests.vbproj",
    }
    assert payload["review_first_unknowns"] == [
        f".NET project {CATALOG_PROJECT} detected but test-project evidence is not proven"
    ]
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_dotnet_scope_survives_recommendations_and_reports() -> None:
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
    assert all(item["operator_level"] == "required" for items in scoped.values() for item in items)
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


def test_root_and_nested_dotnet_projects_remain_distinct(tmp_path: Path) -> None:
    root_project = tmp_path / "Shared.Tests.csproj"
    root_project.write_text(_test_project_xml(), encoding="utf-8")
    workspace = tmp_path / "services" / "orders"
    workspace.mkdir(parents=True)
    (workspace / "Shared.Tests.csproj").write_text(_test_project_xml(), encoding="utf-8")

    payload = discover_adoption_surface(tmp_path)
    commands = [
        item
        for item in payload["recommended_proof_commands"]
        if item.get("surface") == "dotnet"
        and item.get("command") == "dotnet test Shared.Tests.csproj"
    ]

    assert len(commands) == 2
    root_command = next(item for item in commands if not item.get("source"))
    nested_command = next(item for item in commands if item.get("source"))
    assert root_command["evidence"] == ["Shared.Tests.csproj"]
    assert nested_command["source"] == {
        "scope": "nested_workspace",
        "file": "services/orders/Shared.Tests.csproj",
        "working_directory": "services/orders",
    }


def test_package_reference_proves_test_project_and_malformed_xml_does_not(
    tmp_path: Path,
) -> None:
    proven = tmp_path / "src" / "Proven.Tests"
    malformed = tmp_path / "src" / "Malformed.Tests"
    proven.mkdir(parents=True)
    malformed.mkdir(parents=True)
    (proven / "Proven.Tests.csproj").write_text(
        _test_project_xml(package_reference=True),
        encoding="utf-8",
    )
    (malformed / "Malformed.Tests.csproj").write_text(
        '<Project><PackageReference Include="Microsoft.NET.Test.Sdk">',
        encoding="utf-8",
    )

    payload = discover_adoption_surface(tmp_path)
    commands = [
        item for item in payload["recommended_proof_commands"] if item.get("surface") == "dotnet"
    ]

    assert [item["command"] for item in commands] == ["dotnet test Proven.Tests.csproj"]
    assert payload["review_first_unknowns"] == [
        ".NET project src/Malformed.Tests/Malformed.Tests.csproj detected "
        "but test-project evidence is not proven"
    ]


def test_dotnet_discovery_ignores_non_owned_top_level_trees(tmp_path: Path) -> None:
    ignored_docs = tmp_path / "docs" / "sample" / "Docs.Tests.csproj"
    ignored_tests = tmp_path / "tests" / "fixture" / "Fixture.Tests.fsproj"
    ignored_docs.parent.mkdir(parents=True)
    ignored_tests.parent.mkdir(parents=True)
    ignored_docs.write_text(_test_project_xml(), encoding="utf-8")
    ignored_tests.write_text(_test_project_xml(package_reference=True), encoding="utf-8")

    payload = discover_adoption_surface(tmp_path)

    languages = _named(payload["detected_languages"])
    assert "csharp" not in languages
    assert "fsharp" not in languages
    assert "nuget" not in _named(payload["package_managers"])
    assert payload["recommended_proof_commands"] == []
