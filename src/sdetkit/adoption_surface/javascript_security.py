from __future__ import annotations

from pathlib import Path
from typing import Any

from sdetkit.adoption_surface import core as _core

_COMMAND_PATTERNS = ("*.sh", "*.ps1", "*.cmd", "*.bat")
_IGNORED_TOP_LEVEL = {
    ".github",
    "build",
    "dist",
    "docs",
    "examples",
    "site",
    "templates",
    "test",
    "tests",
}
_SECURITY_PREFIXES = (
    ("yarn npm audit", "yarn"),
    ("pnpm audit", "pnpm"),
    ("npm audit", "npm"),
    ("yarn audit", "yarn"),
)
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
_IGNORED_LINE_PREFIXES = ("name:", "description:", "if:", "echo ", "printf ", "write-output ")


def _is_repository_owned(path: str) -> bool:
    parts = Path(path).parts
    if not parts:
        return False
    if parts[:2] == (".github", "workflows"):
        return True
    return len(parts) == 1 or parts[0] not in _IGNORED_TOP_LEVEL


def _owned_package_manifests(root: Path) -> list[str]:
    return [
        path
        for path in _core._recursive_files(root, "package.json")
        if _is_repository_owned(path)
    ]


def _owned_command_files(root: Path) -> list[str]:
    files = set(_core._workflow_files(root) + _core._owned_script_files(root))
    for path in (".gitlab-ci.yml", "Jenkinsfile"):
        if _core._file(root, path):
            files.add(path)
    for pattern in _COMMAND_PATTERNS:
        files.update(_core._recursive_files(root, pattern))
    return sorted(path for path in files if _is_repository_owned(path))


def _clean_line_prefix(prefix: str) -> str:
    return prefix.strip().lower().rstrip("'\"(").strip()


def _strip_command_suffix(command: str) -> str:
    if " #" in command:
        command = command.split(" #", 1)[0].rstrip()
    return command.rstrip("'\"),").strip()


def _is_dynamic_or_composite(command: str) -> bool:
    return _core._command_is_dynamic(command) or any(
        token in command for token in ("${{", "||", ";", "|")
    )


def _requests_mutation(command: str) -> bool:
    normalized = " ".join(command.lower().split())
    return normalized.startswith("npm audit fix") or "--fix" in normalized.split()


def _literal_security_command(raw_value: str) -> tuple[str, str, str] | None:
    stripped = raw_value.strip()
    if not stripped or stripped.startswith("#"):
        return None

    lowered = stripped.lower()
    matches = [
        (lowered.find(prefix), prefix, manager)
        for prefix, manager in _SECURITY_PREFIXES
        if lowered.find(prefix) >= 0
    ]
    if not matches:
        return None

    index, _prefix, manager = min(matches, key=lambda item: item[0])
    line_prefix = _clean_line_prefix(stripped[:index])
    if any(line_prefix.startswith(prefix) for prefix in _IGNORED_LINE_PREFIXES):
        return None
    if line_prefix not in _ALLOWED_LINE_PREFIXES:
        return manager, "", "unresolved"

    command = _strip_command_suffix(stripped[index:])
    if not command:
        return manager, "", "unresolved"
    if _requests_mutation(command):
        return manager, "", "mutation"
    if _is_dynamic_or_composite(command):
        return manager, "", "dynamic"
    return manager, command, ""


def _source_label(path: str, script: str = "") -> str:
    return f"{path} script {script}" if script else path


def _append_unknown(
    unknowns: list[str],
    *,
    manager: str,
    path: str,
    reason: str,
    script: str = "",
) -> None:
    source = _source_label(path, script)
    if reason == "dynamic":
        unknowns.append(
            f"JavaScript package security command for {manager} in {source} is dynamic and was not guessed"
        )
    elif reason == "mutation":
        unknowns.append(
            f"JavaScript package security command for {manager} in {source} requests dependency mutation and was not recommended"
        )
    else:
        unknowns.append(
            f"JavaScript package security command for {manager} in {source} has unresolved command context and was not guessed"
        )


def _extract_package_script_commands(
    root: Path,
) -> tuple[list[dict[str, str]], list[str]]:
    commands: list[dict[str, str]] = []
    unknowns: list[str] = []
    for manifest in _owned_package_manifests(root):
        scripts = _core._read_json(root, manifest).get("scripts")
        if not isinstance(scripts, dict):
            continue
        working_directory = Path(manifest).parent.as_posix()
        for script_name, raw_value in sorted(scripts.items()):
            if not isinstance(raw_value, str):
                continue
            extracted = _literal_security_command(raw_value)
            if extracted is None:
                if "audit" in str(script_name).lower() and any(
                    manager in raw_value.lower() for manager in ("npm", "pnpm", "yarn")
                ):
                    unknowns.append(
                        f"JavaScript package security script {script_name} in {manifest} was not a literal supported audit command"
                    )
                continue
            manager, command, reason = extracted
            if reason:
                _append_unknown(
                    unknowns,
                    manager=manager,
                    path=manifest,
                    reason=reason,
                    script=str(script_name),
                )
                continue
            commands.append(
                {
                    "manager": manager,
                    "command": command,
                    "file": manifest,
                    "script": str(script_name),
                    "working_directory": working_directory,
                }
            )
    return commands, unknowns


def _extract_command_file_commands(root: Path) -> tuple[list[dict[str, str]], list[str]]:
    commands: list[dict[str, str]] = []
    unknowns: list[str] = []
    for path in _owned_command_files(root):
        for raw_line in _core._read_text(root, path).splitlines():
            extracted = _literal_security_command(raw_line)
            if extracted is None:
                continue
            manager, command, reason = extracted
            if reason:
                _append_unknown(unknowns, manager=manager, path=path, reason=reason)
                continue
            commands.append(
                {
                    "manager": manager,
                    "command": command,
                    "file": path,
                    "script": "",
                    "working_directory": ".",
                }
            )
    return commands, unknowns


def _merge_security_tool(
    payload: dict[str, Any],
    *,
    manager: str,
    evidence: list[str],
) -> None:
    name = f"{manager}_audit"
    existing = next(
        (item for item in payload["security_tools"] if item.get("name") == name),
        None,
    )
    values = sorted(set(evidence))
    if existing is None:
        payload["security_tools"].append(
            {"name": name, "confidence": "detected", "evidence": values}
        )
        return
    current = existing.get("evidence", [])
    current_values = [str(value) for value in current] if isinstance(current, list) else []
    existing["evidence"] = sorted(set(current_values + values))


def _add_security_proof_command(payload: dict[str, Any], item: dict[str, str]) -> None:
    source: dict[str, str] = {
        "scope": "repository_command",
        "file": item["file"],
        "package_manager": item["manager"],
    }
    if item["script"]:
        source["script"] = item["script"]
    if item["working_directory"] != ".":
        source["working_directory"] = item["working_directory"]

    for existing in payload["recommended_proof_commands"]:
        existing_source = existing.get("source")
        source_payload = existing_source if isinstance(existing_source, dict) else {}
        if (
            existing.get("command") == item["command"]
            and source_payload.get("file") == item["file"]
            and source_payload.get("script", "") == item["script"]
        ):
            existing["purpose"] = "security"
            source_payload["package_manager"] = item["manager"]
            existing["source"] = source_payload
            evidence = existing.get("evidence", [])
            current = [str(value) for value in evidence] if isinstance(evidence, list) else []
            existing["evidence"] = sorted(set(current + [item["file"]]))
            return

    payload["recommended_proof_commands"].append(
        {
            "surface": "javascript_typescript",
            "command": item["command"],
            "confidence": "medium",
            "purpose": "security",
            "executes_untrusted_code": True,
            "auto_run_allowed": False,
            "evidence": [item["file"]],
            "source": source,
        }
    )


def extend_javascript_package_security(payload: dict[str, Any], root: Path) -> None:
    package_commands, package_unknowns = _extract_package_script_commands(root)
    file_commands, file_unknowns = _extract_command_file_commands(root)
    commands = package_commands + file_commands

    seen: set[tuple[str, str, str, str]] = set()
    grouped_evidence: dict[str, list[str]] = {}
    for item in commands:
        key = (item["manager"], item["command"], item["file"], item["script"])
        if key in seen:
            continue
        seen.add(key)
        grouped_evidence.setdefault(item["manager"], []).append(item["file"])
        _add_security_proof_command(payload, item)

    for manager, evidence in grouped_evidence.items():
        _merge_security_tool(payload, manager=manager, evidence=evidence)

    payload["review_first_unknowns"].extend(package_unknowns)
    payload["review_first_unknowns"].extend(file_unknowns)
