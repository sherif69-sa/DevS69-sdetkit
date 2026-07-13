from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from sdetkit.adoption_surface import _base
from sdetkit.adoption_surface import core as _core

_PROJECT_PATTERNS = ("*.csproj", "*.fsproj", "*.vbproj")
_LANGUAGE_BY_SUFFIX = {
    ".csproj": "csharp",
    ".fsproj": "fsharp",
    ".vbproj": "visual_basic",
}
_CENTRAL_NUGET_FILES = ("Directory.Packages.props", "NuGet.config", "nuget.config")


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


def _is_repository_owned(path: str) -> bool:
    parts = Path(path).parts
    return len(parts) == 1 or parts[0] not in _base._WORKSPACE_IGNORED_TOP_LEVEL


def _owned_dotnet_project_manifests(root: Path) -> list[str]:
    manifests = {
        path
        for pattern in _PROJECT_PATTERNS
        for path in _core._recursive_files(root, pattern)
        if _is_repository_owned(path)
    }
    return sorted(manifests)


def _owned_dotnet_solutions(root: Path) -> list[str]:
    return [path for path in _core._recursive_files(root, "*.sln") if _is_repository_owned(path)]


def _replace_named_evidence(
    items: list[dict[str, Any]],
    *,
    name: str,
    field: str,
    values: list[str],
) -> None:
    existing = next((item for item in items if item.get("name") == name), None)
    if not values:
        items[:] = [item for item in items if item.get("name") != name]
        return
    if existing is not None:
        existing[field] = values


def _normalize_base_dotnet_detection(
    payload: dict[str, Any],
    *,
    manifests: list[str],
    solutions: list[str],
) -> None:
    owned_evidence = sorted(set([*solutions, *manifests]))
    _replace_named_evidence(
        payload["detected_languages"],
        name="dotnet",
        field="evidence",
        values=owned_evidence,
    )
    _replace_named_evidence(
        payload["package_managers"],
        name="nuget",
        field="files",
        values=owned_evidence,
    )

    preserve_solution_command = bool(solutions and not manifests)
    if preserve_solution_command:
        return
    payload["recommended_proof_commands"] = [
        item
        for item in payload["recommended_proof_commands"]
        if not (item.get("surface") == "dotnet" and item.get("command") == "dotnet test")
    ]


def _local_name(value: str) -> str:
    return value.rsplit("}", 1)[-1].lower()


def _attribute(element: ET.Element, name: str) -> str:
    normalized = name.lower()
    for key, value in element.attrib.items():
        if _local_name(str(key)) == normalized:
            return str(value).strip()
    return ""


def _is_explicit_dotnet_test_project(text: str) -> bool:
    try:
        project = ET.fromstring(text)
    except ET.ParseError:
        return False

    for element in project.iter():
        name = _local_name(str(element.tag))
        value = (element.text or "").strip().lower()
        if name == "istestproject" and value == "true":
            return True
        if name == "packagereference":
            include = _attribute(element, "include") or _attribute(element, "update")
            if include.lower() == "microsoft.net.test.sdk":
                return True
    return False


def _workspace_ancestors(workspace: str) -> list[str]:
    current = Path(workspace)
    ancestors = [current.as_posix()]
    while current != Path("."):
        current = current.parent
        ancestors.append(current.as_posix())
    return ancestors


def _nuget_evidence(root: Path, workspace: str) -> list[str]:
    evidence: list[str] = []
    lockfile = _base._workspace_path(workspace, "packages.lock.json")
    if _core._file(root, lockfile):
        evidence.append(lockfile)

    for ancestor in _workspace_ancestors(workspace):
        for name in _CENTRAL_NUGET_FILES:
            path = _base._workspace_path(ancestor, name)
            if _core._file(root, path):
                evidence.append(path)
    return sorted(set(evidence))


def _add_root_dotnet_test_command(payload: dict[str, Any], *, manifest: str, command: str) -> None:
    for item in payload["recommended_proof_commands"]:
        if (
            item.get("surface") == "dotnet"
            and item.get("command") == command
            and not item.get("source")
        ):
            return
    payload["recommended_proof_commands"].append(
        {
            "surface": "dotnet",
            "command": command,
            "confidence": "high",
            "purpose": "test",
            "executes_untrusted_code": True,
            "auto_run_allowed": False,
            "evidence": [manifest],
        }
    )


def _add_dotnet_test_command(
    payload: dict[str, Any],
    *,
    manifest: str,
    workspace: str,
) -> None:
    command = f"dotnet test {Path(manifest).name}"
    _base._merge_named_list(
        payload["test_runners"],
        "dotnet_test",
        list_field="commands",
        values=[command],
        confidence="high",
    )
    if workspace == ".":
        _add_root_dotnet_test_command(payload, manifest=manifest, command=command)
        return

    _base._add_workspace_proof_command(
        payload["recommended_proof_commands"],
        surface="dotnet",
        command=command,
        confidence="high",
        purpose="test",
        file=manifest,
        working_directory=workspace,
    )


def extend_dotnet_workspaces(payload: dict[str, Any], root: Path) -> None:
    manifests = _owned_dotnet_project_manifests(root)
    solutions = _owned_dotnet_solutions(root)
    _normalize_base_dotnet_detection(payload, manifests=manifests, solutions=solutions)
    if not manifests:
        return

    language_files: dict[str, list[str]] = {}
    nuget_files: list[str] = []
    for manifest in manifests:
        workspace = _base._workspace_directory(manifest)
        language = _LANGUAGE_BY_SUFFIX[Path(manifest).suffix.lower()]
        language_files.setdefault(language, []).append(manifest)
        nuget_files.extend([manifest, *_nuget_evidence(root, workspace)])

        if _is_explicit_dotnet_test_project(_core._read_text(root, manifest)):
            _add_dotnet_test_command(payload, manifest=manifest, workspace=workspace)
        else:
            payload["review_first_unknowns"].append(
                f".NET project {manifest} detected but test-project evidence is not proven"
            )

    for language, files in sorted(language_files.items()):
        _base._merge_named_list(
            payload["detected_languages"],
            language,
            list_field="evidence",
            values=files,
            confidence="high",
        )
    _base._merge_named_list(
        payload["package_managers"],
        "nuget",
        list_field="files",
        values=nuget_files,
    )
