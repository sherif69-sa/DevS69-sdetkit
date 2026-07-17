from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from sdetkit.adoption_surface import _base
from sdetkit.adoption_surface import core as _core
from sdetkit.adoption_surface import cpp as _cpp

_TOOL_COMMAND_RE = re.compile(
    r"(?<![\w.-])(?P<tool>clang-tidy|cppcheck|clang-format)(?=\s|$)",
    re.IGNORECASE,
)
_SANITIZER_RE = re.compile(
    r"(?:-f|/f)sanitize=(?P<values>[A-Za-z0-9_,+-]+)",
    re.IGNORECASE,
)
_CLANG_TIDY_CONFIG_RE = re.compile(
    r"\b(?:CMAKE_(?:C|CXX)_CLANG_TIDY|(?:C|CXX)_CLANG_TIDY)\b",
    re.IGNORECASE,
)
_COMPILE_DATABASE_CONFIG_RE = re.compile(
    r"\bCMAKE_EXPORT_COMPILE_COMMANDS\b",
    re.IGNORECASE,
)
_COMPILE_DATABASE_TRUE_RE = re.compile(
    r"(?:CMAKE_EXPORT_COMPILE_COMMANDS(?:=|\s+|\s*\)\s*)"
    r"(?:ON|TRUE|YES|1)\b)",
    re.IGNORECASE,
)
_ALLOWED_LINE_PREFIXES = {
    "",
    "-",
    "run:",
    "- run:",
    "script:",
    "- script:",
    "command:",
    "- command:",
    "sh",
    "bat",
    "powershell",
    "pwsh",
}
_METADATA_PREFIXES = ("name:", "description:", "if:", "displayname:")
_SHELL_MESSAGE_COMMANDS = ("echo", "printf", "write-output")
_MUTATING_FLAGS = {
    "clang-tidy": ("-fix", "--fix", "-fix-errors", "--fix-errors"),
    "clang-format": ("-i", "--in-place"),
}
_DYNAMIC_TOKENS = ("$", "`", "${{", "&&", "||", ";", "|")
_SANITIZER_TO_TOOL = {
    "address": "address_sanitizer",
    "undefined": "undefined_behavior_sanitizer",
    "thread": "thread_sanitizer",
    "memory": "memory_sanitizer",
    "leak": "leak_sanitizer",
}
_BUILD_CONFIG_NAMES = (
    "CMakeLists.txt",
    "CMakePresets.json",
    "meson.build",
    "meson_options.txt",
    "CTestTestfile.cmake",
)
_TOOL_CONFIG_PATTERNS = (".clang-tidy", ".clang-format")
_COMPILE_DATABASE_NAME = "compile_commands.json"


def _has_cpp(payload: dict[str, Any]) -> bool:
    languages = payload.get("detected_languages")
    if not isinstance(languages, list):
        return False
    return any(
        isinstance(item, dict) and item.get("name") == "cpp" for item in languages
    )


def _active_lines(text: str) -> list[str]:
    without_blocks = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    lines: list[str] = []
    for raw_line in without_blocks.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", "//")):
            continue
        for marker in (" #", " //"):
            if marker in line:
                line = line.split(marker, 1)[0].rstrip()
        if line:
            lines.append(line)
    return lines


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
    return command.rstrip("'\"),]").strip()


def _is_dynamic_or_composite(command: str) -> bool:
    return _core._command_is_dynamic(command) or any(
        token in command for token in _DYNAMIC_TOKENS
    )


def _config_is_dynamic(value: str) -> bool:
    return any(token in value for token in ("$", "`", "${{", "&&", "||", "|"))


def _requests_mutation(tool: str, command: str) -> bool:
    tokens = " ".join(command.lower().split()).split()
    return any(
        token == flag or token.startswith(f"{flag}=")
        for token in tokens
        for flag in _MUTATING_FLAGS.get(tool, ())
    )


def _literal_tool_command(raw_value: str) -> tuple[str, str, str] | None:
    stripped = raw_value.strip()
    if not stripped or stripped.startswith(("#", "//")):
        return None

    match = _TOOL_COMMAND_RE.search(stripped)
    if match is None:
        return None

    tool = match.group("tool").lower()
    prefix = _clean_line_prefix(stripped[: match.start()])
    if _line_prefix_is_descriptive(prefix):
        return None
    if prefix not in _ALLOWED_LINE_PREFIXES:
        return tool, "", "unresolved"

    command = _strip_command_suffix(stripped[match.start() :])
    if not command:
        return tool, "", "unresolved"
    if _requests_mutation(tool, command):
        return tool, "", "mutation"
    if _is_dynamic_or_composite(command):
        return tool, "", "dynamic"
    return tool, command, ""


def _sanitizer_tools(text: str) -> set[str]:
    tools: set[str] = set()
    for match in _SANITIZER_RE.finditer(text):
        values = match.group("values").lower().replace("+", ",").split(",")
        for value in values:
            tool = _SANITIZER_TO_TOOL.get(value.strip())
            if tool:
                tools.add(tool)
    return tools


def _truthy(value: object) -> bool:
    if value is True:
        return True
    return str(value).strip().lower() in {"1", "on", "true", "yes"}


def _iter_string_values(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        values: list[str] = []
        for item in value.values():
            values.extend(_iter_string_values(item))
        return values
    if isinstance(value, list):
        values = []
        for item in value:
            values.extend(_iter_string_values(item))
        return values
    return []


def _preset_evidence(
    root: Path, path: str
) -> tuple[set[str], set[str], bool, list[str]]:
    document = _core._read_json(root, path)
    if not document:
        return set(), set(), False, []

    tools: set[str] = set()
    sanitizers: set[str] = set()
    compile_database = False
    unknowns: list[str] = []
    configure_presets = document.get("configurePresets")
    if not isinstance(configure_presets, list):
        configure_presets = []

    for preset in configure_presets:
        if not isinstance(preset, dict):
            continue
        cache = preset.get("cacheVariables")
        if not isinstance(cache, dict):
            cache = {}
        for raw_key, raw_value in cache.items():
            key = str(raw_key).strip().upper()
            text = " ".join(_iter_string_values(raw_value))
            if key in {"CMAKE_C_CLANG_TIDY", "CMAKE_CXX_CLANG_TIDY"}:
                normalized = text.strip().lower()
                if normalized in {"", "0", "false", "off"}:
                    pass
                elif "clang-tidy" in normalized and not _config_is_dynamic(text):
                    tools.add("clang_tidy")
                else:
                    unknowns.append(
                        f"C++ clang-tidy configuration in {path} is dynamic or unresolved and was not guessed"
                    )
            if key == "CMAKE_EXPORT_COMPILE_COMMANDS" and _truthy(raw_value):
                compile_database = True
            sanitizers.update(_sanitizer_tools(text))

        for text in _iter_string_values(preset):
            sanitizers.update(_sanitizer_tools(text))
            if re.search(
                r"-DCMAKE_EXPORT_COMPILE_COMMANDS=(?:ON|TRUE|YES|1)\b",
                text,
                flags=re.IGNORECASE,
            ):
                compile_database = True

    return tools, sanitizers, compile_database, unknowns


def _text_config_evidence(
    path: str, text: str
) -> tuple[set[str], set[str], bool, bool]:
    active = "\n".join(_active_lines(text))
    tools: set[str] = set()
    if Path(path).name == ".clang-tidy":
        tools.add("clang_tidy")
    if _CLANG_TIDY_CONFIG_RE.search(active) and "clang-tidy" in active.lower():
        tools.add("clang_tidy")
    if re.search(r"(?<![\w.-])cppcheck(?=\s|$)", active, flags=re.IGNORECASE):
        tools.add("cppcheck")

    compile_database = bool(
        _COMPILE_DATABASE_CONFIG_RE.search(active)
        and (
            _COMPILE_DATABASE_TRUE_RE.search(active)
            or re.search(
                r"-DCMAKE_EXPORT_COMPILE_COMMANDS=(?:ON|TRUE|YES|1)\b",
                active,
                flags=re.IGNORECASE,
            )
        )
    )
    clang_format_config = Path(path).name == ".clang-format"
    return tools, _sanitizer_tools(active), compile_database, clang_format_config


def _is_executable_evidence_line(raw_line: str) -> bool:
    stripped = raw_line.strip()
    if not stripped or stripped.startswith(("#", "//")):
        return False
    normalized = stripped.lstrip("- ").strip().lower()
    if normalized.startswith(_METADATA_PREFIXES):
        return False
    return not any(
        normalized == command or normalized.startswith(f"{command} ")
        for command in _SHELL_MESSAGE_COMMANDS
    )


def _command_has_compile_database(command: str) -> bool:
    normalized = " ".join(command.lower().split())
    if "compile_commands.json" in normalized:
        return True
    if normalized.startswith("cppcheck "):
        return "--project=" in normalized
    return normalized.startswith("clang-tidy ") and bool(
        re.search(r"(?:^|\s)-p(?:=|\s+)\S+", normalized)
    )


def _workspace_maps(root: Path) -> dict[str, list[str]]:
    manifests = sorted(
        {
            path
            for name in _BUILD_CONFIG_NAMES
            for path in _cpp._owned_named_files(root, name)
        }
    )
    return _cpp._workspace_manifests(manifests)


def _working_directory(path: str, workspaces: dict[str, list[str]]) -> str:
    return _cpp._workspace_for_source(path, workspaces)


def _merge_security_tool(
    payload: dict[str, Any], name: str, evidence: list[str]
) -> None:
    _base._merge_named_list(
        payload["security_tools"],
        name,
        list_field="evidence",
        values=evidence,
        confidence="detected",
    )


def _merge_artifact_surface(
    payload: dict[str, Any], name: str, paths: list[str]
) -> None:
    _base._merge_named_list(
        payload["artifact_surfaces"],
        name,
        list_field="paths",
        values=paths,
        confidence="detected",
    )


def _add_proof_command(
    payload: dict[str, Any],
    *,
    tool: str,
    command: str,
    file: str,
    working_directory: str,
) -> None:
    for existing in payload["recommended_proof_commands"]:
        existing_source = existing.get("source")
        source_payload = existing_source if isinstance(existing_source, dict) else {}
        if (
            existing.get("surface") == "cpp"
            and existing.get("command") == command
            and str(source_payload.get("working_directory", ".")) == working_directory
        ):
            return

    source: dict[str, str] = {
        "scope": "repository_command",
        "file": file,
        "tool": tool,
        "working_directory": working_directory,
    }
    payload["recommended_proof_commands"].append(
        {
            "surface": "cpp",
            "command": command,
            "confidence": "high",
            "purpose": "quality" if tool == "clang-format" else "lint",
            "executes_untrusted_code": True,
            "auto_run_allowed": False,
            "evidence": [file],
            "source": source,
        }
    )


def _append_command_unknown(
    unknowns: list[str],
    *,
    tool: str,
    path: str,
    reason: str,
) -> None:
    display = tool.replace("-", " ")
    if reason == "dynamic":
        unknowns.append(
            f"C++ {display} command in {path} is dynamic or composite and was not guessed"
        )
    elif reason == "mutation":
        unknowns.append(
            f"C++ {display} command in {path} requests source mutation and was not recommended"
        )
    else:
        unknowns.append(
            f"C++ {display} command in {path} has unresolved command context and was not guessed"
        )


def _command_evidence(
    payload: dict[str, Any],
    *,
    root: Path,
    workspaces: dict[str, list[str]],
) -> tuple[dict[str, set[str]], set[str], set[str], list[str]]:
    tool_evidence: dict[str, set[str]] = {}
    clang_format_evidence: set[str] = set()
    compile_database_evidence: set[str] = set()
    unknowns: list[str] = []
    config_files = {
        path
        for name in ("CMakeLists.txt", "meson.build")
        for path in _cpp._owned_named_files(root, name)
    }
    command_files = sorted(set(_cpp._command_files(root)) | config_files)

    for path in command_files:
        for raw_line in _core._read_text(root, path).splitlines():
            if not _is_executable_evidence_line(raw_line):
                continue
            active = raw_line.strip()
            sanitizer_tools = _sanitizer_tools(active)
            if sanitizer_tools:
                if _is_dynamic_or_composite(active):
                    unknowns.append(
                        f"C++ sanitizer configuration in {path} is dynamic or composite and was not guessed"
                    )
                else:
                    for tool in sanitizer_tools:
                        tool_evidence.setdefault(tool, set()).add(path)

            extracted = _literal_tool_command(raw_line)
            if extracted is None:
                continue
            tool, command, reason = extracted
            normalized_tool = tool.replace("-", "_")
            if normalized_tool == "clang_format":
                clang_format_evidence.add(path)
            else:
                tool_evidence.setdefault(normalized_tool, set()).add(path)
            if reason:
                _append_command_unknown(unknowns, tool=tool, path=path, reason=reason)
                continue
            workspace = _working_directory(path, workspaces)
            _add_proof_command(
                payload,
                tool=tool,
                command=command,
                file=path,
                working_directory=workspace,
            )
            if _command_has_compile_database(command):
                compile_database_evidence.add(path)

    return tool_evidence, clang_format_evidence, compile_database_evidence, unknowns


def _codeql_cpp_workflows(root: Path) -> tuple[list[str], list[str]]:
    evidence: list[str] = []
    unknowns: list[str] = []
    for path in _core._workflow_files(root):
        active_lines = _active_lines(_core._read_text(root, path))
        lowered = "\n".join(active_lines).lower()
        if "github/codeql-action/init@" not in lowered:
            continue

        language_values = [
            line.split(":", 1)[1].strip()
            for line in active_lines
            if line.lstrip("- ").lower().startswith("languages:") and ":" in line
        ]
        if any(
            "c-cpp" in value.lower() and "${{" not in value for value in language_values
        ):
            evidence.append(path)
        elif language_values:
            unknowns.append(
                f"CodeQL workflow {path} uses dynamic or non-C/C++ language evidence and was not claimed as C++"
            )
    return sorted(set(evidence)), sorted(set(unknowns))


def extend_cpp_quality_security(payload: dict[str, Any], root: Path) -> None:
    if not _has_cpp(payload):
        return

    workspaces = _workspace_maps(root)
    tool_evidence: dict[str, set[str]] = {}
    sanitizer_evidence: dict[str, set[str]] = {}
    compile_database_evidence: set[str] = set()
    clang_format_configs: set[str] = set()
    unknowns: list[str] = []

    config_files = {
        path
        for name in _BUILD_CONFIG_NAMES
        for path in _cpp._owned_named_files(root, name)
    }
    for pattern in _TOOL_CONFIG_PATTERNS:
        config_files.update(_cpp._owned_pattern_files(root, pattern))

    for path in sorted(config_files):
        if Path(path).name == "CMakePresets.json":
            tools, sanitizers, compile_database, preset_unknowns = _preset_evidence(
                root, path
            )
            for tool in tools:
                tool_evidence.setdefault(tool, set()).add(path)
            for tool in sanitizers:
                sanitizer_evidence.setdefault(tool, set()).add(path)
            if compile_database:
                compile_database_evidence.add(path)
            unknowns.extend(preset_unknowns)
            continue

        tools, sanitizers, compile_database, clang_format_config = (
            _text_config_evidence(
                path,
                _core._read_text(root, path),
            )
        )
        for tool in tools:
            tool_evidence.setdefault(tool, set()).add(path)
        for tool in sanitizers:
            sanitizer_evidence.setdefault(tool, set()).add(path)
        if compile_database:
            compile_database_evidence.add(path)
        if clang_format_config:
            clang_format_configs.add(path)

    (
        command_tools,
        command_clang_format,
        command_compile_database,
        command_unknowns,
    ) = _command_evidence(
        payload,
        root=root,
        workspaces=workspaces,
    )
    for tool, paths in command_tools.items():
        tool_evidence.setdefault(tool, set()).update(paths)
    clang_format_configs.update(command_clang_format)
    compile_database_evidence.update(command_compile_database)
    unknowns.extend(command_unknowns)

    committed_databases = _cpp._owned_named_files(root, _COMPILE_DATABASE_NAME)
    compile_database_evidence.update(committed_databases)

    codeql_evidence, codeql_unknowns = _codeql_cpp_workflows(root)
    if codeql_evidence:
        tool_evidence.setdefault("codeql_cpp", set()).update(codeql_evidence)
    unknowns.extend(codeql_unknowns)

    for tool in sorted(set(tool_evidence) | set(sanitizer_evidence)):
        combined = set(tool_evidence.get(tool, set())) | set(
            sanitizer_evidence.get(tool, set())
        )
        if combined:
            _merge_security_tool(payload, tool, sorted(combined))

    if clang_format_configs:
        _merge_artifact_surface(
            payload,
            "clang_format_evidence",
            sorted(clang_format_configs),
        )
    if compile_database_evidence:
        _merge_artifact_surface(
            payload,
            "cpp_compile_database_contract",
            sorted(compile_database_evidence),
        )

    payload["review_first_unknowns"].extend(unknowns)
