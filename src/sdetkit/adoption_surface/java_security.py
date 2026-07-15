from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from sdetkit.adoption_surface import _base
from sdetkit.adoption_surface import core as _core

_COMMAND_PATTERNS = ("*.sh", "*.ps1", "*.cmd", "*.bat")
_ALLOWED_LINE_PREFIXES = {
    "",
    "-",
    "run:",
    "- run:",
    "script:",
    "- script:",
    "sh",
    "bat",
    "powershell",
    "pwsh",
}
_METADATA_PREFIXES = ("name:", "description:", "if:")
_SHELL_MESSAGE_COMMANDS = ("echo", "printf", "write-output")
_MAVEN_MARKERS = ("dependency-check-maven:check", "dependency-check:check")
_GRADLE_MARKER = "dependencycheckanalyze"
_MUTATION_MARKERS = (
    "dependencycheckupdate",
    "dependencycheckpurge",
    "dependency-check-maven:update-only",
    "dependency-check:update-only",
)


def _is_repository_owned(path: str) -> bool:
    parts = Path(path).parts
    if not parts:
        return False
    if parts[:2] == (".github", "workflows"):
        return True
    return len(parts) == 1 or parts[0] not in _base._WORKSPACE_IGNORED_TOP_LEVEL


def _owned_java_manifests(root: Path) -> list[str]:
    manifests = {
        path
        for pattern in ("pom.xml", "build.gradle", "build.gradle.kts")
        for path in _core._recursive_files(root, pattern)
        if _is_repository_owned(path)
    }
    return sorted(manifests)


def _owned_command_files(root: Path) -> list[str]:
    files = set(_core._workflow_files(root) + _core._owned_script_files(root))
    for path in (".gitlab-ci.yml", "Jenkinsfile"):
        if _core._file(root, path):
            files.add(path)
    for pattern in _COMMAND_PATTERNS:
        files.update(_core._recursive_files(root, pattern))
    return sorted(path for path in files if _is_repository_owned(path))


def _local_name(value: str) -> str:
    return value.rsplit("}", 1)[-1].lower()


def _child_text(element: ET.Element, name: str) -> str:
    normalized = name.lower()
    for child in element:
        if _local_name(str(child.tag)) == normalized:
            return (child.text or "").strip()
    return ""


def _maven_dependency_check_configured(text: str) -> bool:
    try:
        project = ET.fromstring(text)
    except ET.ParseError:
        return False

    for element in project.iter():
        if _local_name(str(element.tag)) != "plugin":
            continue
        group_id = _child_text(element, "groupId").lower()
        artifact_id = _child_text(element, "artifactId").lower()
        if group_id == "org.owasp" and artifact_id == "dependency-check-maven":
            return True
    return False


def _active_gradle_text(text: str) -> str:
    without_blocks = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    lines = []
    for raw_line in without_blocks.splitlines():
        line = raw_line.split("//", 1)[0].strip()
        if line:
            lines.append(line)
    return "\n".join(lines).lower()


def _gradle_dependency_check_configured(text: str) -> bool:
    active = _active_gradle_text(text)
    return "org.owasp.dependencycheck" in active


def _manifest_security_config(root: Path, path: str) -> tuple[str, str] | None:
    text = _core._read_text(root, path)
    name = Path(path).name
    if name == "pom.xml" and _maven_dependency_check_configured(text):
        return "maven", "owasp_dependency_check"
    if name in {"build.gradle", "build.gradle.kts"} and _gradle_dependency_check_configured(text):
        return "gradle", "owasp_dependency_check"
    return None


def _clean_line_prefix(prefix: str) -> str:
    return prefix.strip().lower().rstrip("'\"(").strip()


def _line_prefix_is_descriptive(prefix: str) -> bool:
    normalized = prefix.lstrip("- ").strip()
    if normalized.startswith(_METADATA_PREFIXES):
        return True
    return any(
        normalized == command
        or normalized.startswith(f"{command} ")
        or normalized.endswith(f" {command}")
        for command in _SHELL_MESSAGE_COMMANDS
    )


def _strip_command_suffix(command: str) -> str:
    if " #" in command:
        command = command.split(" #", 1)[0].rstrip()
    return command.rstrip("'\"),").strip()


def _command_start(lowered: str) -> tuple[int, str] | None:
    candidates = (
        ("./mvnw ", "maven"),
        ("mvnw ", "maven"),
        ("mvn ", "maven"),
        ("./gradlew ", "gradle"),
        ("gradlew ", "gradle"),
        ("gradle ", "gradle"),
    )
    matches = [
        (lowered.find(prefix), manager)
        for prefix, manager in candidates
        if lowered.find(prefix) >= 0
    ]
    return min(matches, key=lambda item: item[0]) if matches else None


def _looks_like_dependency_check(text: str) -> bool:
    normalized = "".join(text.lower().split())
    return any(
        marker in normalized
        for marker in (*_MAVEN_MARKERS, _GRADLE_MARKER, *_MUTATION_MARKERS)
    )


def _requests_mutation(command: str) -> bool:
    normalized = "".join(command.lower().split())
    return any(marker in normalized for marker in _MUTATION_MARKERS)


def _is_dynamic_or_composite(command: str) -> bool:
    return _core._command_is_dynamic(command) or any(
        token in command for token in ("${{", "&&", "||", ";", "|")
    )


def _literal_security_command(raw_value: str) -> tuple[str, str, str] | None:
    stripped = raw_value.strip()
    if not stripped or stripped.startswith("#") or not _looks_like_dependency_check(stripped):
        return None

    lowered = stripped.lower()
    start = _command_start(lowered)
    if start is None:
        return "java", "", "unresolved"

    index, manager = start
    line_prefix = _clean_line_prefix(stripped[:index])
    if _line_prefix_is_descriptive(line_prefix):
        return None
    if line_prefix not in _ALLOWED_LINE_PREFIXES:
        return manager, "", "unresolved"

    command = _strip_command_suffix(stripped[index:])
    if _requests_mutation(command):
        return manager, "", "mutation"
    normalized = command.lower()
    if manager == "maven" and not any(marker in normalized for marker in _MAVEN_MARKERS):
        return None
    if manager == "gradle" and _GRADLE_MARKER not in "".join(normalized.split()):
        return None
    if _is_dynamic_or_composite(command):
        return manager, "", "dynamic"
    return manager, command, ""


def _default_config_command(root: Path, manifest: str, manager: str) -> str:
    workspace = Path(manifest).parent.as_posix()
    if manager == "maven":
        wrapper = _base._workspace_path(workspace, "mvnw")
        executable = "./mvnw" if _core._file(root, wrapper) else "mvn"
        return f"{executable} org.owasp:dependency-check-maven:check"
    wrapper = _base._workspace_path(workspace, "gradlew")
    executable = "./gradlew" if _core._file(root, wrapper) else "gradle"
    return f"{executable} dependencyCheckAnalyze"


def _append_unknown(
    unknowns: list[str],
    *,
    manager: str,
    path: str,
    reason: str,
) -> None:
    if reason == "dynamic":
        unknowns.append(
            f"Java dependency security command for {manager} in {path} is dynamic or "
            "composite and was not guessed"
        )
    elif reason == "mutation":
        unknowns.append(
            f"Java dependency security command for {manager} in {path} requests mutation "
            "and was not recommended"
        )
    else:
        unknowns.append(
            f"Java dependency security command for {manager} in {path} has unresolved "
            "command context and was not guessed"
        )


def _merge_security_tool(payload: dict[str, Any], evidence: list[str]) -> None:
    _base._merge_named_list(
        payload["security_tools"],
        "owasp_dependency_check",
        list_field="evidence",
        values=evidence,
        confidence="detected",
    )


def _add_security_proof_command(
    payload: dict[str, Any],
    *,
    manager: str,
    command: str,
    file: str,
    working_directory: str,
    scope: str,
) -> None:
    for existing in payload["recommended_proof_commands"]:
        source = existing.get("source")
        source_payload = source if isinstance(source, dict) else {}
        if (
            existing.get("surface") == "java"
            and existing.get("command") == command
            and str(source_payload.get("working_directory", ".")) == working_directory
        ):
            evidence = existing.get("evidence", [])
            current = [str(value) for value in evidence] if isinstance(evidence, list) else []
            existing["evidence"] = sorted(set([*current, file]))
            if scope == "repository_command":
                existing["source"] = {
                    "scope": scope,
                    "file": file,
                    "package_manager": manager,
                    **(
                        {"working_directory": working_directory}
                        if working_directory != "."
                        else {}
                    ),
                }
            return

    source: dict[str, str] = {
        "scope": scope,
        "file": file,
        "package_manager": manager,
    }
    if working_directory != ".":
        source["working_directory"] = working_directory
    payload["recommended_proof_commands"].append(
        {
            "surface": "java",
            "command": command,
            "confidence": "high" if scope == "repository_command" else "medium",
            "purpose": "security",
            "executes_untrusted_code": True,
            "auto_run_allowed": False,
            "evidence": [file],
            "source": source,
        }
    )


def extend_java_dependency_security(payload: dict[str, Any], root: Path) -> None:
    manifests = _owned_java_manifests(root)
    if not manifests:
        return

    evidence: list[str] = []
    unknowns: list[str] = []

    for manifest in manifests:
        configured = _manifest_security_config(root, manifest)
        if configured is None:
            continue
        manager, _tool = configured
        evidence.append(manifest)
        workspace = Path(manifest).parent.as_posix()
        _add_security_proof_command(
            payload,
            manager=manager,
            command=_default_config_command(root, manifest, manager),
            file=manifest,
            working_directory=workspace,
            scope="build_configuration",
        )

    for path in _owned_command_files(root):
        for raw_line in _core._read_text(root, path).splitlines():
            extracted = _literal_security_command(raw_line)
            if extracted is None:
                continue
            manager, command, reason = extracted
            evidence.append(path)
            if reason:
                _append_unknown(unknowns, manager=manager, path=path, reason=reason)
                continue
            _add_security_proof_command(
                payload,
                manager=manager,
                command=command,
                file=path,
                working_directory=".",
                scope="repository_command",
            )

    if evidence:
        _merge_security_tool(payload, evidence)
    payload["review_first_unknowns"].extend(unknowns)
