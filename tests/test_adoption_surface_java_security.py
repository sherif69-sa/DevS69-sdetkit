from __future__ import annotations

from pathlib import Path

from sdetkit.adoption_surface import discover_adoption_surface


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _named(items: object) -> dict[str, dict[str, object]]:
    assert isinstance(items, list)
    return {
        str(item["name"]): item for item in items if isinstance(item, dict) and item.get("name")
    }


def _commands(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    items = payload["recommended_proof_commands"]
    assert isinstance(items, list)
    return {
        str(item["command"]): item
        for item in items
        if isinstance(item, dict) and item.get("command")
    }


def test_maven_dependency_check_plugin_emits_wrapper_aware_security_proof(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "pom.xml",
        """<project>
  <modelVersion>4.0.0</modelVersion>
  <groupId>example</groupId>
  <artifactId>demo</artifactId>
  <version>1.0.0</version>
  <build>
    <plugins>
      <plugin>
        <groupId>org.owasp</groupId>
        <artifactId>dependency-check-maven</artifactId>
        <version>12.1.0</version>
      </plugin>
    </plugins>
  </build>
</project>
""",
    )
    _write(tmp_path / "mvnw", "#!/bin/sh\n")

    payload = discover_adoption_surface(tmp_path)
    security = _named(payload["security_tools"])
    commands = _commands(payload)
    command = "./mvnw org.owasp:dependency-check-maven:check"

    assert security["owasp_dependency_check"]["evidence"] == ["pom.xml"]
    assert command in commands
    assert commands[command]["purpose"] == "security"
    assert commands[command]["confidence"] == "medium"
    assert commands[command]["evidence"] == ["pom.xml"]
    assert commands[command]["source"] == {
        "scope": "build_configuration",
        "file": "pom.xml",
        "package_manager": "maven",
    }
    assert commands[command]["executes_untrusted_code"] is True
    assert commands[command]["auto_run_allowed"] is False
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_nested_gradle_plugin_preserves_workspace_scope(tmp_path: Path) -> None:
    _write(
        tmp_path / "services" / "api" / "build.gradle.kts",
        """plugins {
    java
    id("org.owasp.dependencycheck") version "12.1.0"
}
""",
    )
    _write(tmp_path / "services" / "api" / "gradlew", "#!/bin/sh\n")

    payload = discover_adoption_surface(tmp_path)
    security = _named(payload["security_tools"])
    commands = _commands(payload)
    security_command = "./gradlew dependencyCheckAnalyze"

    assert security["owasp_dependency_check"]["evidence"] == ["services/api/build.gradle.kts"]
    assert security_command in commands
    assert commands[security_command]["source"] == {
        "scope": "build_configuration",
        "file": "services/api/build.gradle.kts",
        "package_manager": "gradle",
        "working_directory": "services/api",
    }
    assert "./gradlew test" in commands
    assert commands["./gradlew test"]["source"]["working_directory"] == "services/api"


def test_literal_maven_security_command_preserves_exact_repository_text(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "pom.xml",
        """<project>
  <modelVersion>4.0.0</modelVersion>
  <groupId>example</groupId>
  <artifactId>demo</artifactId>
  <version>1.0.0</version>
</project>
""",
    )
    workflow = tmp_path / ".github" / "workflows" / "security.yml"
    command = "./mvnw -B org.owasp:dependency-check-maven:check -Dformat=JSON"
    _write(workflow, f"jobs:\n  audit:\n    steps:\n      - run: {command}\n")

    payload = discover_adoption_surface(tmp_path)
    security = _named(payload["security_tools"])
    commands = _commands(payload)

    assert security["owasp_dependency_check"]["evidence"] == [".github/workflows/security.yml"]
    assert command in commands
    assert commands[command]["confidence"] == "high"
    assert commands[command]["evidence"] == [".github/workflows/security.yml"]
    assert commands[command]["source"] == {
        "scope": "repository_command",
        "file": ".github/workflows/security.yml",
        "package_manager": "maven",
    }


def test_java_manifest_without_security_evidence_remains_neutral(tmp_path: Path) -> None:
    _write(
        tmp_path / "pom.xml",
        """<project>
  <modelVersion>4.0.0</modelVersion>
  <groupId>example</groupId>
  <artifactId>demo</artifactId>
  <version>1.0.0</version>
</project>
""",
    )

    payload = discover_adoption_surface(tmp_path)
    security = _named(payload["security_tools"])
    commands = _commands(payload)

    assert "owasp_dependency_check" not in security
    assert not any(
        item.get("surface") == "java" and item.get("purpose") == "security"
        for item in commands.values()
    )
    assert "mvn test" in commands


def test_dynamic_composite_and_mutating_commands_remain_review_first(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "build.gradle", "plugins { id 'java' }\n")
    workflow = tmp_path / ".github" / "workflows" / "security.yml"
    _write(
        workflow,
        """name: ./gradlew dependencyCheckAnalyze
jobs:
  audit:
    steps:
      - run: echo ./gradlew dependencyCheckAnalyze
      - run: ./gradlew dependencyCheckAnalyze ${{ matrix.args }}
      - run: ./gradlew dependencyCheckAnalyze && echo complete
      - run: ./gradlew dependencyCheckUpdate
""",
    )

    payload = discover_adoption_surface(tmp_path)
    security = _named(payload["security_tools"])
    commands = _commands(payload)
    unknowns = payload["review_first_unknowns"]

    assert security["owasp_dependency_check"]["evidence"] == [".github/workflows/security.yml"]
    assert "./gradlew dependencyCheckAnalyze" not in commands
    assert "./gradlew dependencyCheckUpdate" not in commands
    assert isinstance(unknowns, list)
    assert any("dynamic or composite" in str(item) for item in unknowns)
    assert any("requests mutation" in str(item) for item in unknowns)
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False


def test_dependency_check_text_without_java_manifest_is_ignored(tmp_path: Path) -> None:
    _write(tmp_path / "package.json", '{"name": "demo"}\n')
    _write(
        tmp_path / ".github" / "workflows" / "security.yml",
        "jobs:\n  audit:\n    steps:\n      - run: ./gradlew dependencyCheckAnalyze\n",
    )

    payload = discover_adoption_surface(tmp_path)
    security = _named(payload["security_tools"])
    commands = _commands(payload)

    assert "owasp_dependency_check" not in security
    assert "./gradlew dependencyCheckAnalyze" not in commands


def test_commented_gradle_plugin_does_not_create_security_evidence(tmp_path: Path) -> None:
    _write(
        tmp_path / "build.gradle.kts",
        """plugins {
    java
    // id("org.owasp.dependencycheck") version "12.1.0"
    /* id("org.owasp.dependencycheck") version "12.1.0" */
}
""",
    )

    payload = discover_adoption_surface(tmp_path)
    security = _named(payload["security_tools"])
    commands = _commands(payload)

    assert "owasp_dependency_check" not in security
    assert "gradle dependencyCheckAnalyze" not in commands
