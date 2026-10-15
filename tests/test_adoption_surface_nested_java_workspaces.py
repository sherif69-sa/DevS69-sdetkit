from __future__ import annotations

from pathlib import Path

from sdetkit.adoption_surface import (
    discover_adoption_surface,
    validate_adoption_surface_payload,
)

FIXTURE = Path("tests/fixtures/adoption_repos/mixed_nested_java_workspaces")
MAVEN_WORKSPACE = Path("services", "orders").as_posix()
GRADLE_WORKSPACE = Path("services", "catalog").as_posix()
WORKSPACES = {MAVEN_WORKSPACE, GRADLE_WORKSPACE}


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


def _source(workspace: str, file_name: str) -> dict[str, str]:
    return {
        "scope": "nested_workspace",
        "file": f"{workspace}/{file_name}",
        "working_directory": workspace,
    }


def test_nested_java_workspaces_emit_scoped_maven_and_gradle_proof() -> None:
    payload = discover_adoption_surface(FIXTURE)

    assert validate_adoption_surface_payload(payload) == []
    languages = _named(payload["detected_languages"])
    package_managers = _named(payload["package_managers"])
    scoped = _scoped_commands(payload)

    expected_java_files = {
        f"{MAVEN_WORKSPACE}/pom.xml",
        f"{MAVEN_WORKSPACE}/mvnw",
        f"{GRADLE_WORKSPACE}/build.gradle.kts",
        f"{GRADLE_WORKSPACE}/gradlew",
    }
    assert set(languages["java"]["evidence"]) == expected_java_files
    assert set(package_managers["maven"]["files"]) == {
        f"{MAVEN_WORKSPACE}/pom.xml",
        f"{MAVEN_WORKSPACE}/mvnw",
    }
    assert set(package_managers["gradle"]["files"]) == {
        f"{GRADLE_WORKSPACE}/build.gradle.kts",
        f"{GRADLE_WORKSPACE}/gradlew",
    }

    assert set(scoped) == WORKSPACES
    assert [item["command"] for item in scoped[MAVEN_WORKSPACE]] == ["./mvnw test"]
    assert [item["command"] for item in scoped[GRADLE_WORKSPACE]] == ["./gradlew test"]

    maven = scoped[MAVEN_WORKSPACE][0]
    gradle = scoped[GRADLE_WORKSPACE][0]
    assert maven["confidence"] == "high"
    assert gradle["confidence"] == "high"
    assert maven["source"] == _source(MAVEN_WORKSPACE, "pom.xml")
    assert gradle["source"] == _source(GRADLE_WORKSPACE, "build.gradle.kts")
    assert maven["purpose"] == "test"
    assert gradle["purpose"] == "test"

    assert payload["review_first_unknowns"] == []
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False
    assert all(item["auto_run_allowed"] is False for items in scoped.values() for item in items)


def test_root_and_nested_maven_commands_remain_distinct(tmp_path: Path) -> None:
    (tmp_path / "pom.xml").write_text("<project />\n", encoding="utf-8")
    workspace = tmp_path / "services" / "orders"
    workspace.mkdir(parents=True)
    (workspace / "pom.xml").write_text("<project />\n", encoding="utf-8")

    payload = discover_adoption_surface(tmp_path)
    commands = [
        item
        for item in payload["recommended_proof_commands"]
        if item.get("surface") == "java" and item.get("command") == "mvn test"
    ]

    assert len(commands) == 2
    root_command = next(item for item in commands if not item.get("source"))
    nested_command = next(item for item in commands if item.get("source"))
    assert root_command["confidence"] == "high"
    assert nested_command["source"] == _source(Path("services", "orders").as_posix(), "pom.xml")

    managers = _named(payload["package_managers"])
    assert set(managers["maven"]["files"]) == {"pom.xml", "services/orders/pom.xml"}


def test_nested_java_discovery_ignores_non_owned_top_level_trees(tmp_path: Path) -> None:
    ignored_maven = tmp_path / "tests" / "fixture" / "pom.xml"
    ignored_gradle = tmp_path / "docs" / "sample" / "build.gradle.kts"
    ignored_maven.parent.mkdir(parents=True)
    ignored_gradle.parent.mkdir(parents=True)
    ignored_maven.write_text("<project />\n", encoding="utf-8")
    ignored_gradle.write_text("plugins { java }\n", encoding="utf-8")

    payload = discover_adoption_surface(tmp_path)

    assert "java" not in _named(payload["detected_languages"])
    assert "maven" not in _named(payload["package_managers"])
    assert "gradle" not in _named(payload["package_managers"])
    assert payload["recommended_proof_commands"] == []
