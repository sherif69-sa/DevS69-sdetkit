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
    assert all(
        item.get("command") != "dotnet test"
        for item in payload["recommended_proof_commands"]
        if item.get("surface") == "dotnet"
    )
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
    proven = tmp_path / "services" / "Proven.Tests"
    malformed = tmp_path / "services" / "Malformed.Tests"
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
        ".NET project services/Malformed.Tests/Malformed.Tests.csproj detected "
        "but test-project evidence is not proven"
    ]


def test_solution_only_repo_preserves_generic_dotnet_proof(tmp_path: Path) -> None:
    (tmp_path / "Product.sln").write_text("\n", encoding="utf-8")

    payload = discover_adoption_surface(tmp_path)
    languages = _named(payload["detected_languages"])
    managers = _named(payload["package_managers"])
    commands = [
        item for item in payload["recommended_proof_commands"] if item.get("surface") == "dotnet"
    ]

    assert languages["dotnet"]["evidence"] == ["Product.sln"]
    assert managers["nuget"]["files"] == ["Product.sln"]
    assert [item["command"] for item in commands] == ["dotnet test"]


def test_dotnet_discovery_ignores_non_owned_top_level_trees(tmp_path: Path) -> None:
    ignored_docs = tmp_path / "docs" / "sample" / "Docs.Tests.csproj"
    ignored_tests = tmp_path / "tests" / "fixture" / "Fixture.Tests.fsproj"
    ignored_docs.parent.mkdir(parents=True)
    ignored_tests.parent.mkdir(parents=True)
    ignored_docs.write_text(_test_project_xml(), encoding="utf-8")
    ignored_tests.write_text(_test_project_xml(package_reference=True), encoding="utf-8")

    payload = discover_adoption_surface(tmp_path)

    languages = _named(payload["detected_languages"])
    assert "dotnet" not in languages
    assert "csharp" not in languages
    assert "fsharp" not in languages
    assert "nuget" not in _named(payload["package_managers"])
    assert payload["recommended_proof_commands"] == []


def _write_dotnet_project(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '<Project Sdk="Microsoft.NET.Sdk">'
        "<PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup>"
        '<ItemGroup><PackageReference Include="Contoso.Runtime" Version="1.0.0" /></ItemGroup>'
        "</Project>\n",
        encoding="utf-8",
    )


def test_dotnet_package_reference_does_not_invent_security_proof(tmp_path: Path) -> None:
    _write_dotnet_project(tmp_path / "src" / "Api" / "Api.csproj")

    payload = discover_adoption_surface(tmp_path)
    security = _named(payload["security_tools"])
    commands = [
        item
        for item in payload["recommended_proof_commands"]
        if item.get("surface") == "dotnet" and item.get("purpose") == "security"
    ]

    assert "nuget_audit" not in security
    assert commands == []
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False


def test_dotnet_audit_config_and_literal_command_are_source_grounded(tmp_path: Path) -> None:
    _write_dotnet_project(tmp_path / "src" / "Api" / "Api.csproj")
    (tmp_path / "Directory.Build.props").write_text(
        "<Project><PropertyGroup><NuGetAudit>true</NuGetAudit>"
        "<NuGetAuditMode>all</NuGetAuditMode></PropertyGroup></Project>\n",
        encoding="utf-8",
    )
    workflow = tmp_path / ".github" / "workflows" / "security.yml"
    workflow.parent.mkdir(parents=True)
    command = (
        "dotnet list src/Api/Api.csproj package --vulnerable --include-transitive --format json"
    )
    workflow.write_text(f"jobs:\n  audit:\n    steps:\n      - run: {command}\n", encoding="utf-8")

    payload = discover_adoption_surface(tmp_path)
    security = _named(payload["security_tools"])
    proof = next(
        item
        for item in payload["recommended_proof_commands"]
        if item.get("surface") == "dotnet" and item.get("purpose") == "security"
    )

    assert set(security["nuget_audit"]["evidence"]) == {
        ".github/workflows/security.yml",
        "Directory.Build.props",
    }
    assert proof["command"] == command
    assert proof["confidence"] == "high"
    assert proof["auto_run_allowed"] is False
    assert proof["source"] == {
        "scope": "repository_command",
        "file": ".github/workflows/security.yml",
    }


def test_dotnet_noun_first_vulnerability_command_is_preserved(tmp_path: Path) -> None:
    _write_dotnet_project(tmp_path / "services" / "billing" / "Billing.csproj")
    script = tmp_path / "scripts" / "nuget-audit.sh"
    script.parent.mkdir(parents=True)
    command = (
        "dotnet package list --project services/billing/Billing.csproj "
        "--include-transitive --vulnerable --format json > security/nuget-report.json"
    )
    script.write_text(f"#!/usr/bin/env sh\n{command}\n", encoding="utf-8")

    payload = discover_adoption_surface(tmp_path)
    commands = [
        item
        for item in payload["recommended_proof_commands"]
        if item.get("surface") == "dotnet" and item.get("purpose") == "security"
    ]

    assert [item["command"] for item in commands] == [command]
    assert commands[0]["evidence"] == ["scripts/nuget-audit.sh"]


def test_dynamic_dotnet_security_command_remains_review_first(tmp_path: Path) -> None:
    _write_dotnet_project(tmp_path / "services" / "billing" / "Billing.csproj")
    script = tmp_path / "scripts" / "nuget-audit.sh"
    script.parent.mkdir(parents=True)
    script.write_text(
        '#!/usr/bin/env sh\ndotnet package list --project "$PROJECT" --vulnerable\n',
        encoding="utf-8",
    )

    payload = discover_adoption_surface(tmp_path)

    assert not any(
        item.get("surface") == "dotnet" and item.get("purpose") == "security"
        for item in payload["recommended_proof_commands"]
    )
    assert (
        ".NET dependency security command in scripts/nuget-audit.sh is dynamic and was not guessed"
        in payload["review_first_unknowns"]
    )


def test_saved_dotnet_vulnerability_report_is_an_artifact_surface(tmp_path: Path) -> None:
    _write_dotnet_project(tmp_path / "src" / "Api" / "Api.csproj")
    report = tmp_path / "security" / "nuget-vulnerabilities.json"
    report.parent.mkdir(parents=True)
    report.write_text(
        '{"version": 1, "projects": [{"path": "src/Api/Api.csproj", '
        '"frameworks": [{"framework": "net8.0", "topLevelPackages": '
        '[{"id": "Contoso.Runtime", "resolvedVersion": "1.0.0", '
        '"vulnerabilities": [{"severity": "high", '
        '"advisoryurl": "https://example.invalid/advisory"}]}]}]}]}\n',
        encoding="utf-8",
    )

    payload = discover_adoption_surface(tmp_path)
    security = _named(payload["security_tools"])
    artifacts = _named(payload["artifact_surfaces"])

    assert security["nuget_audit"]["evidence"] == ["security/nuget-vulnerabilities.json"]
    assert artifacts["nuget_vulnerability_report"]["paths"] == [
        "security/nuget-vulnerabilities.json"
    ]
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_explicitly_disabled_nuget_audit_is_review_first(tmp_path: Path) -> None:
    _write_dotnet_project(tmp_path / "src" / "Api" / "Api.csproj")
    (tmp_path / "Directory.Build.props").write_text(
        "<Project><PropertyGroup><NuGetAudit>false</NuGetAudit></PropertyGroup></Project>\n",
        encoding="utf-8",
    )

    payload = discover_adoption_surface(tmp_path)

    assert "nuget_audit" not in _named(payload["security_tools"])
    assert (
        ".NET NuGet audit is explicitly disabled in Directory.Build.props; "
        "security posture requires review" in payload["review_first_unknowns"]
    )


def test_disabled_nuget_audit_overrides_mode_settings(tmp_path: Path) -> None:
    _write_dotnet_project(tmp_path / "src" / "Api" / "Api.csproj")
    (tmp_path / "Directory.Build.props").write_text(
        "<Project><PropertyGroup><NuGetAudit>false</NuGetAudit>"
        "<NuGetAuditMode>all</NuGetAuditMode></PropertyGroup></Project>\n",
        encoding="utf-8",
    )

    payload = discover_adoption_surface(tmp_path)

    assert "nuget_audit" not in _named(payload["security_tools"])
    assert (
        ".NET NuGet audit is explicitly disabled in Directory.Build.props; "
        "security posture requires review" in payload["review_first_unknowns"]
    )


def test_generic_projects_json_is_not_a_nuget_report(tmp_path: Path) -> None:
    _write_dotnet_project(tmp_path / "src" / "Api" / "Api.csproj")
    report = tmp_path / "security" / "generic.json"
    report.parent.mkdir(parents=True)
    report.write_text(
        '{"version": 1, "projects": [{"name": "other", "vulnerabilities": []}]}\n',
        encoding="utf-8",
    )

    payload = discover_adoption_surface(tmp_path)

    assert "nuget_audit" not in _named(payload["security_tools"])
    assert "nuget_vulnerability_report" not in _named(payload["artifact_surfaces"])


def test_package_inventory_json_is_not_a_vulnerability_report(tmp_path: Path) -> None:
    _write_dotnet_project(tmp_path / "src" / "Api" / "Api.csproj")
    report = tmp_path / "security" / "package-inventory.json"
    report.parent.mkdir(parents=True)
    report.write_text(
        '{"version": 1, "projects": [{"path": "src/Api/Api.csproj", '
        '"frameworks": [{"framework": "net8.0", "topLevelPackages": '
        '[{"id": "Contoso.Runtime", "resolvedVersion": "1.0.0"}]}]}]}\n',
        encoding="utf-8",
    )

    payload = discover_adoption_surface(tmp_path)

    assert "nuget_audit" not in _named(payload["security_tools"])
    assert "nuget_vulnerability_report" not in _named(payload["artifact_surfaces"])


def test_solution_only_dotnet_repo_can_surface_explicit_audit_command(tmp_path: Path) -> None:
    (tmp_path / "Product.sln").write_text("\n", encoding="utf-8")
    script = tmp_path / "audit.ps1"
    command = "dotnet package list --project Product.sln --vulnerable --format json"
    script.write_text(command + "\n", encoding="utf-8")

    payload = discover_adoption_surface(tmp_path)
    security = _named(payload["security_tools"])
    commands = [
        item
        for item in payload["recommended_proof_commands"]
        if item.get("surface") == "dotnet" and item.get("purpose") == "security"
    ]

    assert security["nuget_audit"]["evidence"] == ["audit.ps1"]
    assert [item["command"] for item in commands] == [command]
    assert commands[0]["auto_run_allowed"] is False
