from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from sdetkit.adoption_surface import _base
from sdetkit.adoption_surface import core as _core

_BUILD_FILES = (
    "CMakeLists.txt",
    "CMakePresets.json",
    "CTestTestfile.cmake",
    "meson.build",
    "meson_options.txt",
)
_CPP_PATTERNS = ("*.cpp", "*.cc", "*.cxx", "*.hpp", "*.hh", "*.hxx")
_COMMAND_PATTERNS = ("*.sh", "*.ps1", "*.cmd", "*.bat")
_NAMED_COMMAND_FILES = ("Makefile", "Taskfile.yml", "Taskfile.yaml", "justfile", "Justfile")
_IGNORED_PARTS = {
    ".cache",
    ".git",
    ".venv",
    "_build",
    "build",
    "deps",
    "dist",
    "external",
    "extern",
    "node_modules",
    "out",
    "site",
    "subprojects",
    "third-party",
    "third_party",
    "vendor",
    "vendors",
    "vcpkg_installed",
}
_IGNORED_PREFIXES = ("cmake-build-",)
_CPP_COMMAND_RE = re.compile(r"(?<![\w.-])(?P<command>(?:cmake|ctest|meson|ninja)\s+.+)$", re.I)
_PRESET_RE = re.compile(r"--preset(?:=|\s+)(?P<name>[^\s'\";,]+)", re.I)
_DYNAMIC_TOKENS = ("$", "`", "$(", "${", "<<", ">>", "{{", "}}", "&&", "||", ";", "|")


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_ignored(relative: str) -> bool:
    for part in Path(relative).parts:
        lowered = part.lower()
        if lowered in _IGNORED_PARTS or any(lowered.startswith(prefix) for prefix in _IGNORED_PREFIXES):
            return True
    return False


def _owned_named_files(root: Path, name: str) -> list[str]:
    return sorted(
        _relative(root, path)
        for path in root.rglob(name)
        if path.is_file() and not _is_ignored(_relative(root, path))
    )


def _owned_pattern_files(root: Path, pattern: str) -> list[str]:
    return sorted(
        _relative(root, path)
        for path in root.rglob(pattern)
        if path.is_file() and not _is_ignored(_relative(root, path))
    )


def _workspace_directory(path: str) -> str:
    parent = Path(path).parent.as_posix()
    return parent if parent else "."


def _is_ancestor_workspace(ancestor: str, candidate: str) -> bool:
    if ancestor == ".":
        return candidate != "."
    ancestor_parts = Path(ancestor).parts
    candidate_parts = Path(candidate).parts
    return len(candidate_parts) > len(ancestor_parts) and candidate_parts[: len(ancestor_parts)] == ancestor_parts


def _workspace_manifests(manifests: list[str]) -> dict[str, list[str]]:
    files_by_directory: dict[str, list[str]] = {}
    for path in manifests:
        files_by_directory.setdefault(_workspace_directory(path), []).append(path)

    workspaces: dict[str, list[str]] = {}
    for directory in sorted(files_by_directory, key=lambda value: (len(Path(value).parts), value)):
        files = sorted(files_by_directory[directory])
        has_explicit_preset = any(Path(path).name == "CMakePresets.json" for path in files)
        ancestor = next(
            (
                value
                for value in sorted(workspaces, key=lambda item: len(Path(item).parts), reverse=True)
                if _is_ancestor_workspace(value, directory)
            ),
            None,
        )
        if ancestor is not None and not has_explicit_preset:
            workspaces[ancestor].extend(files)
            continue
        workspaces[directory] = files

    return {workspace: sorted(set(files)) for workspace, files in workspaces.items()}


def _source(file: str, workspace: str, **fields: str) -> dict[str, str]:
    return {
        "scope": "repository_root" if workspace == "." else "nested_workspace",
        "file": file,
        "working_directory": workspace,
        **fields,
    }


def _add_proof_command(
    payload: dict[str, Any],
    *,
    command: str,
    confidence: str,
    purpose: str,
    file: str,
    workspace: str,
    source_fields: dict[str, str] | None = None,
) -> None:
    source = _source(file, workspace, **(source_fields or {}))
    for existing in payload["recommended_proof_commands"]:
        existing_source = existing.get("source")
        if not isinstance(existing_source, dict):
            continue
        if (
            existing.get("surface") == "cpp"
            and existing.get("command") == command
            and existing_source.get("working_directory") == workspace
        ):
            return

    payload["recommended_proof_commands"].append(
        {
            "surface": "cpp",
            "command": command,
            "confidence": confidence,
            "purpose": purpose,
            "executes_untrusted_code": True,
            "auto_run_allowed": False,
            "evidence": [file],
            "source": source,
        }
    )

    if purpose == "test":
        runner = "ctest" if command.lower().startswith("ctest ") else "meson_test"
        _base._merge_named_list(
            payload["test_runners"],
            runner,
            list_field="commands",
            values=[command],
            confidence="high" if confidence == "high" else "medium",
        )


def _preset_entries(payload: dict[str, Any], key: str) -> tuple[list[dict[str, Any]], bool]:
    raw = payload.get(key)
    if raw is None:
        return [], False
    if not isinstance(raw, list):
        return [], True
    entries = [item for item in raw if isinstance(item, dict)]
    return entries, len(entries) != len(raw)


def _dynamic_name(name: str) -> bool:
    return not name or any(token in name for token in _DYNAMIC_TOKENS)


def _extend_cmake_presets(
    payload: dict[str, Any],
    *,
    root: Path,
    path: str,
    workspace: str,
) -> set[str]:
    document = _core._read_json(root, path)
    if not document:
        payload["review_first_unknowns"].append(
            f"CMake preset file {path} is malformed and was not used for proof commands"
        )
        return set()

    commands: set[str] = set()
    kinds = (
        ("configurePresets", "configure", "cmake --preset {name}"),
        ("buildPresets", "build", "cmake --build --preset {name}"),
        ("testPresets", "test", "ctest --preset {name}"),
    )
    for key, purpose, template in kinds:
        entries, malformed = _preset_entries(document, key)
        if malformed:
            payload["review_first_unknowns"].append(
                f"CMake preset file {path} has malformed {key} entries that were not guessed"
            )
        for entry in entries:
            if entry.get("hidden") is True:
                continue
            name = str(entry.get("name", "")).strip()
            if _dynamic_name(name):
                payload["review_first_unknowns"].append(
                    f"CMake preset file {path} has unnamed or dynamic {key} entry that was not guessed"
                )
                continue
            command = template.format(name=name)
            _add_proof_command(
                payload,
                command=command,
                confidence="high",
                purpose=purpose,
                file=path,
                workspace=workspace,
                source_fields={"preset_kind": key, "preset_name": name},
            )
            commands.add(command)
    return commands


def _command_purpose(command: str) -> str:
    normalized = " ".join(command.lower().split())
    if normalized.startswith("ctest ") or normalized.startswith("meson test "):
        return "test"
    if normalized.startswith("ninja test"):
        return "test"
    if normalized.startswith("cmake --build ") or normalized.startswith("cmake --install "):
        return "build"
    if normalized.startswith("meson compile ") or normalized.startswith("ninja "):
        return "build"
    if normalized.startswith("cmake --preset ") or normalized.startswith("cmake -s "):
        return "configure"
    if normalized.startswith("meson setup "):
        return "configure"
    return "unknown"


def _literal_cpp_command(raw_line: str) -> tuple[str, str]:
    stripped = raw_line.strip()
    if not stripped or stripped.startswith(("#", "//")):
        return "", ""

    match = _CPP_COMMAND_RE.search(stripped)
    if match is None:
        return "", ""
    prefix = stripped[: match.start()].lower()
    if "echo " in prefix or "print(" in prefix:
        return "", ""

    command = match.group("command").strip().rstrip("'\"},]")
    if " #" in command:
        command = command.split(" #", 1)[0].rstrip()
    normalized = command.lower()
    if "--version" in normalized or "--help" in normalized:
        return "", ""
    if any(token in command for token in _DYNAMIC_TOKENS):
        return "", "dynamic"
    purpose = _command_purpose(command)
    return (command, purpose) if purpose != "unknown" else ("", "unsupported")


def _command_files(root: Path) -> list[str]:
    files = set(_core._workflow_files(root) + _core._owned_script_files(root))
    for path in (".gitlab-ci.yml", "Jenkinsfile", ".circleci/config.yml", ".circleci/config.yaml"):
        if _core._file(root, path):
            files.add(path)
    for name in _NAMED_COMMAND_FILES:
        files.update(_owned_named_files(root, name))
    for pattern in _COMMAND_PATTERNS:
        files.update(_owned_pattern_files(root, pattern))
    return sorted(path for path in files if not _is_ignored(path))


def _workspace_for_source(path: str, workspaces: dict[str, list[str]]) -> str:
    source_parts = Path(path).parts
    candidates = [
        workspace
        for workspace in workspaces
        if workspace != "." and source_parts[: len(Path(workspace).parts)] == Path(workspace).parts
    ]
    if not candidates:
        return "."
    return max(candidates, key=lambda value: len(Path(value).parts))


def _preset_workspace(command: str, presets: dict[str, set[str]]) -> str | None:
    match = _PRESET_RE.search(command)
    if match is None:
        return None
    candidates = presets.get(match.group("name"), set())
    return next(iter(candidates)) if len(candidates) == 1 else None


def _extend_literal_commands(
    payload: dict[str, Any],
    *,
    root: Path,
    workspaces: dict[str, list[str]],
    preset_workspaces: dict[str, set[str]],
) -> set[str]:
    evidence: set[str] = set()
    for path in _command_files(root):
        for raw_line in _core._read_text(root, path).splitlines():
            command, classification = _literal_cpp_command(raw_line)
            if classification == "dynamic":
                payload["review_first_unknowns"].append(
                    f"C++ command in {path} is dynamic or compound and was not guessed"
                )
                evidence.add(path)
                continue
            if classification == "unsupported":
                payload["review_first_unknowns"].append(
                    f"C++ command in {path} has unsupported purpose and was not guessed"
                )
                evidence.add(path)
                continue
            if not command:
                continue

            workspace = _preset_workspace(command, preset_workspaces) or _workspace_for_source(
                path, workspaces
            )
            _add_proof_command(
                payload,
                command=command,
                confidence="medium",
                purpose=classification,
                file=path,
                workspace=workspace,
            )
            evidence.add(path)
    return evidence


def extend_cpp(payload: dict[str, Any], root: Path) -> None:
    manifests = sorted(
        {path for name in _BUILD_FILES for path in _owned_named_files(root, name)}
    )
    source_files = sorted(
        {path for pattern in _CPP_PATTERNS for path in _owned_pattern_files(root, pattern)}
    )
    workspaces = _workspace_manifests(manifests)

    preset_workspaces: dict[str, set[str]] = {}
    commands_before = len(payload["recommended_proof_commands"])
    for workspace, files in sorted(workspaces.items()):
        for path in files:
            if Path(path).name != "CMakePresets.json":
                continue
            commands = _extend_cmake_presets(
                payload,
                root=root,
                path=path,
                workspace=workspace,
            )
            for command in commands:
                match = _PRESET_RE.search(command)
                if match is not None:
                    preset_workspaces.setdefault(match.group("name"), set()).add(workspace)

    command_evidence = _extend_literal_commands(
        payload,
        root=root,
        workspaces=workspaces,
        preset_workspaces=preset_workspaces,
    )
    evidence = sorted(set(manifests + source_files + list(command_evidence)))
    if not evidence:
        return

    _base._merge_named_list(
        payload["detected_languages"],
        "cpp",
        list_field="evidence",
        values=evidence,
        confidence="high" if manifests else "medium",
    )

    cpp_commands = [
        item
        for item in payload["recommended_proof_commands"][commands_before:]
        if item.get("surface") == "cpp"
    ]
    command_workspaces = {
        str(item.get("source", {}).get("working_directory", "."))
        for item in cpp_commands
        if isinstance(item.get("source"), dict)
    }
    for workspace in sorted(workspaces):
        if workspace not in command_workspaces:
            payload["review_first_unknowns"].append(
                f"C++ workspace {workspace} detected but configure/build/test command is not proven"
            )
    if source_files and not manifests and not cpp_commands:
        payload["review_first_unknowns"].append(
            "C++ source files detected but build or test command is not proven"
        )
