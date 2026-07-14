from __future__ import annotations

import json
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
_DOTNET_AUDIT_CONFIG_FILES = (
    "Directory.Build.props",
    "Directory.Build.targets",
    "Directory.Packages.props",
    "NuGet.config",
    "nuget.config",
)
_DOTNET_COMMAND_PATTERNS = ("*.sh", "*.ps1", "*.cmd", "*.bat")
_DOTNET_AUDIT_ELEMENTS = {
    "auditsources",
    "nugetauditlevel",
    "nugetauditmode",
    "nugetauditsuppress",
}


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


def _dotnet_audit_config_state(text: str) -> tuple[bool, bool]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return False, False

    explicit_values: set[str] = set()
    audit_setting_detected = False
    for element in root.iter():
        name = _local_name(str(element.tag))
        value = (element.text or "").strip().lower()
        if name == "nugetaudit" and value in {"true", "false"}:
            explicit_values.add(value)
        elif name in _DOTNET_AUDIT_ELEMENTS:
            audit_setting_detected = True

    if "true" in explicit_values:
        return True, False
    if "false" in explicit_values:
        return False, True
    return audit_setting_detected, False


def _dotnet_audit_config_evidence(
    root: Path,
    manifests: list[str],
) -> tuple[list[str], list[str]]:
    candidates = {name for name in _DOTNET_AUDIT_CONFIG_FILES if _core._file(root, name)}
    candidates.update(manifests)
    for manifest in manifests:
        workspace = _base._workspace_directory(manifest)
        for ancestor in _workspace_ancestors(workspace):
            for name in _DOTNET_AUDIT_CONFIG_FILES:
                path = _base._workspace_path(ancestor, name)
                if _core._file(root, path):
                    candidates.add(path)

    enabled: list[str] = []
    disabled: list[str] = []
    for path in sorted(candidates):
        is_enabled, is_disabled = _dotnet_audit_config_state(_core._read_text(root, path))
        if is_enabled:
            enabled.append(path)
        elif is_disabled:
            disabled.append(path)
    return enabled, disabled


def _is_repository_command_source(path: str) -> bool:
    parts = Path(path).parts
    if not parts:
        return False
    if parts[:2] == (".github", "workflows"):
        return True
    return len(parts) == 1 or parts[0] not in _base._WORKSPACE_IGNORED_TOP_LEVEL


def _owned_dotnet_command_files(root: Path) -> list[str]:
    files = set(_core._workflow_files(root) + _core._owned_script_files(root))
    for path in (".gitlab-ci.yml", "Jenkinsfile"):
        if _core._file(root, path):
            files.add(path)
    for pattern in _DOTNET_COMMAND_PATTERNS:
        files.update(_core._recursive_files(root, pattern))
    return sorted(path for path in files if _is_repository_command_source(path))


def _literal_dotnet_security_command(raw_line: str) -> str:
    lower = raw_line.lower()
    index = lower.find("dotnet ")
    if index < 0 or "echo " in lower[:index]:
        return ""

    command = raw_line[index:].strip()
    if " #" in command:
        command = command.split(" #", 1)[0].rstrip()
    command = command.rstrip("'\"")
    normalized = " ".join(command.lower().split())
    vulnerable_list = (
        normalized.startswith("dotnet package list")
        or (normalized.startswith("dotnet list ") and " package " in normalized)
    ) and "--vulnerable" in normalized
    explicit_restore_audit = normalized.startswith("dotnet restore") and any(
        token in normalized
        for token in (
            "nugetaudit=true",
            "nugetauditmode=",
            "nugetauditlevel=",
        )
    )
    return command if vulnerable_list or explicit_restore_audit else ""


def _dotnet_security_commands(root: Path) -> tuple[list[tuple[str, str]], list[str]]:
    commands: list[tuple[str, str]] = []
    unknowns: list[str] = []
    seen: set[tuple[str, str]] = set()
    for path in _owned_dotnet_command_files(root):
        for raw_line in _core._read_text(root, path).splitlines():
            command = _literal_dotnet_security_command(raw_line)
            if not command:
                continue
            if _core._command_is_dynamic(command):
                unknowns.append(
                    f".NET dependency security command in {path} is dynamic and was not guessed"
                )
                continue
            key = (path, command)
            if key not in seen:
                seen.add(key)
                commands.append(key)
    return commands, sorted(set(unknowns))


def _is_dotnet_vulnerability_report(payload: object) -> bool:
    if not isinstance(payload, dict) or "version" not in payload:
        return False
    projects = payload.get("projects")
    if not isinstance(projects, list):
        return False

    for project in projects:
        if not isinstance(project, dict) or not str(project.get("path", "")).strip():
            continue
        frameworks = project.get("frameworks")
        if not isinstance(frameworks, list):
            continue
        for framework in frameworks:
            if not isinstance(framework, dict) or not str(framework.get("framework", "")).strip():
                continue
            if any(
                isinstance(framework.get(field), list)
                for field in ("topLevelPackages", "transitivePackages")
            ):
                return True
    return False


def _dotnet_vulnerability_reports(root: Path) -> list[str]:
    reports: list[str] = []
    for path in _core._recursive_files(root, "*.json"):
        if not _is_repository_owned(path):
            continue
        try:
            payload = json.loads(_core._read_text(root, path))
        except json.JSONDecodeError:
            continue
        if _is_dotnet_vulnerability_report(payload):
            reports.append(path)
    return sorted(reports)


def _extend_dotnet_security_evidence(
    payload: dict[str, Any],
    root: Path,
    manifests: list[str],
) -> None:
    config_evidence, disabled_evidence = _dotnet_audit_config_evidence(root, manifests)
    commands, command_unknowns = _dotnet_security_commands(root)
    reports = _dotnet_vulnerability_reports(root)
    command_files = [path for path, _command in commands]
    evidence = sorted(set([*config_evidence, *command_files, *reports]))

    if evidence:
        _base._merge_named_list(
            payload["security_tools"],
            "nuget_audit",
            list_field="evidence",
            values=evidence,
            confidence="detected",
        )
    if reports:
        _base._merge_named_list(
            payload["artifact_surfaces"],
            "nuget_vulnerability_report",
            list_field="paths",
            values=reports,
            confidence="detected",
        )
        payload["artifact_surfaces"] = sorted(
            payload["artifact_surfaces"], key=lambda item: item["name"]
        )

    for path, command in commands:
        _core._add_proof_command(
            payload["recommended_proof_commands"],
            surface="dotnet",
            command=command,
            confidence="high",
            purpose="security",
            evidence=[path],
            source={"scope": "repository_command", "file": path},
        )

    payload["review_first_unknowns"].extend(command_unknowns)
    payload["review_first_unknowns"].extend(
        f".NET NuGet audit is explicitly disabled in {path}; security posture requires review"
        for path in disabled_evidence
    )
    if config_evidence and not commands and not reports:
        payload["review_first_unknowns"].append(
            ".NET NuGet audit configuration detected but a literal security proof command "
            "or saved vulnerability report is not proven"
        )


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
    if manifests or solutions:
        _extend_dotnet_security_evidence(payload, root, manifests)
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
