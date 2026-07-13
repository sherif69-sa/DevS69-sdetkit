from __future__ import annotations

from pathlib import Path
from typing import Any

from sdetkit.adoption_surface import _base
from sdetkit.adoption_surface import core as _core


def _maven_workspace_command(root: Path, workspace: str) -> tuple[str, str, list[str]]:
    wrapper = _base._workspace_path(workspace, "mvnw")
    if _core._file(root, wrapper):
        return "./mvnw test", "high", [wrapper]
    return "mvn test", "high", []


def _gradle_workspace_command(root: Path, workspace: str) -> tuple[str, str, list[str]]:
    wrapper = _base._workspace_path(workspace, "gradlew")
    if _core._file(root, wrapper):
        return "./gradlew test", "high", [wrapper]
    return "gradle test", "medium", []


def extend_nested_java_workspaces(payload: dict[str, Any], root: Path) -> None:
    maven_manifests = _base._nested_owned_files(root, "pom.xml")
    gradle_manifests = sorted(
        set(
            _base._nested_owned_files(root, "build.gradle")
            + _base._nested_owned_files(root, "build.gradle.kts")
        )
    )
    if not maven_manifests and not gradle_manifests:
        return

    java_files: list[str] = []
    maven_files: list[str] = []
    gradle_files: list[str] = []

    for manifest in maven_manifests:
        workspace = _base._workspace_directory(manifest)
        command, confidence, wrapper_files = _maven_workspace_command(root, workspace)
        workspace_files = [manifest, *wrapper_files]
        java_files.extend(workspace_files)
        maven_files.extend(workspace_files)
        _base._add_workspace_proof_command(
            payload["recommended_proof_commands"],
            surface="java",
            command=command,
            confidence=confidence,
            purpose="test",
            file=manifest,
            working_directory=workspace,
        )

    for manifest in gradle_manifests:
        workspace = _base._workspace_directory(manifest)
        command, confidence, wrapper_files = _gradle_workspace_command(root, workspace)
        workspace_files = [manifest, *wrapper_files]
        java_files.extend(workspace_files)
        gradle_files.extend(workspace_files)
        _base._add_workspace_proof_command(
            payload["recommended_proof_commands"],
            surface="java",
            command=command,
            confidence=confidence,
            purpose="test",
            file=manifest,
            working_directory=workspace,
        )

    _base._merge_named_list(
        payload["detected_languages"],
        "java",
        list_field="evidence",
        values=java_files,
        confidence="high",
    )
    if maven_files:
        _base._merge_named_list(
            payload["package_managers"],
            "maven",
            list_field="files",
            values=maven_files,
        )
    if gradle_files:
        _base._merge_named_list(
            payload["package_managers"],
            "gradle",
            list_field="files",
            values=gradle_files,
        )
