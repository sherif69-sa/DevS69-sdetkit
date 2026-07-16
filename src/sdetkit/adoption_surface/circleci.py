from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from sdetkit.adoption_surface import core as _core

CONFIG_FILES = (".circleci/config.yml", ".circleci/config.yaml")
_BUILTIN_STEPS = {
    "add_ssh_keys",
    "attach_workspace",
    "checkout",
    "deploy",
    "persist_to_workspace",
    "restore_cache",
    "run",
    "save_cache",
    "setup_remote_docker",
    "store_artifacts",
    "store_test_results",
    "unless",
    "when",
}
_INLINE_FIELD_RE = re.compile(
    r"(?:^|,)\s*(?P<key>[A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(?P<value>[^,}]+)"
)


def _indent(raw_line: str) -> int:
    return len(raw_line) - len(raw_line.lstrip(" "))


def _yaml_key(raw_line: str) -> tuple[str, str] | None:
    stripped = raw_line.strip()
    if not stripped or stripped.startswith("#") or ":" not in stripped:
        return None
    key, value = stripped.split(":", 1)
    key = key.strip()
    return (key, value.strip()) if key else None


def _strip_scalar(value: str) -> str:
    normalized = value.strip()
    if (
        len(normalized) >= 2
        and normalized[0] == normalized[-1]
        and normalized[0] in {"'", '"'}
    ):
        return normalized[1:-1]
    return normalized


def _dynamic_command(command: str) -> bool:
    return any(token in command for token in ("<<", ">>", "$", "`", "$("))


def _literal_command(value: str) -> tuple[str | None, str | None]:
    normalized = value.strip()
    if not normalized:
        return None, "mapping"
    if normalized in {"|", ">", "|-", ">-", "|+", ">+"}:
        return None, "multiline"
    if normalized.startswith("{") and normalized.endswith("}"):
        fields = {
            match.group("key"): _strip_scalar(match.group("value"))
            for match in _INLINE_FIELD_RE.finditer(normalized[1:-1])
        }
        command = fields.get("command", "").strip()
        if not command:
            return None, "unsupported_mapping"
        return (None, "dynamic") if _dynamic_command(command) else (command, None)

    command = _strip_scalar(normalized)
    if not command:
        return None, "unsupported_mapping"
    return (None, "dynamic") if _dynamic_command(command) else (command, None)


def _context(job: str, step_name: str = "") -> str:
    suffix = f" step {step_name}" if step_name else ""
    return f"CircleCI job {job}{suffix}"


def _append_command(
    commands: list[dict[str, Any]],
    *,
    command: str,
    file: str,
    job: str,
    step_name: str = "",
) -> None:
    if _core._command_is_shell_message(command):
        return
    item: dict[str, Any] = {"command": command, "file": file, "job": job}
    if step_name:
        item["step_name"] = step_name
    commands.append(item)


def _declared_command_names(text: str) -> set[str]:
    names: set[str] = set()
    section = ""
    for raw_line in text.splitlines():
        parsed = _yaml_key(raw_line)
        if parsed is None:
            continue
        indent = _indent(raw_line)
        key, _ = parsed
        if indent == 0:
            section = key
            continue
        if section == "commands" and indent == 2:
            names.add(key)
    return names


def _extract_config(path: Path, relative: str) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return [], []

    commands: list[dict[str, Any]] = []
    unknowns: set[str] = set()
    declared_commands = _declared_command_names(text)
    section = ""
    current_job = ""
    in_steps = False
    pending_run: dict[str, str] | None = None

    def flush_pending() -> None:
        nonlocal pending_run
        if pending_run is None:
            return
        context = _context(pending_run["job"], pending_run.get("name", ""))
        command = pending_run.get("command", "").strip()
        reason = pending_run.get("reason", "")
        if command:
            _append_command(
                commands,
                command=command,
                file=relative,
                job=pending_run["job"],
                step_name=pending_run.get("name", ""),
            )
        elif reason == "multiline":
            unknowns.add(f"{context} has multiline run content that was not guessed")
        elif reason == "dynamic":
            unknowns.add(f"{context} has dynamic run content that was not guessed")
        else:
            unknowns.add(f"{context} has unsupported run content that was not guessed")
        pending_run = None

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = _indent(raw_line)
        parsed = _yaml_key(raw_line)

        if indent == 0 and parsed is not None:
            flush_pending()
            section, value = parsed
            current_job = ""
            in_steps = False
            if section == "setup" and value.lower() == "true":
                unknowns.add(
                    "CircleCI dynamic configuration detected; continuation behavior was not resolved"
                )
            elif section == "orbs":
                unknowns.add("CircleCI orbs detected; orb behavior was not resolved")
            elif section == "commands":
                unknowns.add(
                    "CircleCI reusable commands detected; command bodies were not expanded"
                )
            elif section == "parameters":
                unknowns.add(
                    "CircleCI pipeline parameters detected; parameter values were not resolved"
                )
            continue

        if section != "jobs":
            continue
        if indent == 2 and parsed is not None:
            flush_pending()
            current_job = parsed[0]
            in_steps = False
            continue
        if not current_job:
            continue
        if indent == 4 and parsed is not None:
            flush_pending()
            in_steps = parsed[0] == "steps"
            if parsed[0] == "parameters":
                unknowns.add(
                    f"CircleCI job {current_job} declares parameters that were not resolved"
                )
            continue
        if not in_steps:
            continue

        if indent == 6 and stripped.startswith("- "):
            flush_pending()
            step = stripped[2:].strip()
            if not step:
                continue
            step_parsed = _yaml_key(step)
            if step_parsed is None:
                step_name = step
                if step_name in declared_commands:
                    unknowns.add(
                        f"CircleCI job {current_job} invokes reusable command {step_name}; "
                        "behavior was not expanded"
                    )
                elif "/" in step_name:
                    unknowns.add(
                        f"CircleCI job {current_job} invokes orb step {step_name}; "
                        "behavior was not resolved"
                    )
                elif step_name not in _BUILTIN_STEPS:
                    unknowns.add(
                        f"CircleCI job {current_job} invokes custom step {step_name}; "
                        "behavior was not resolved"
                    )
                continue

            step_key, value = step_parsed
            if step_key != "run":
                if step_key in declared_commands:
                    unknowns.add(
                        f"CircleCI job {current_job} invokes reusable command {step_key}; "
                        "behavior was not expanded"
                    )
                elif "/" in step_key:
                    unknowns.add(
                        f"CircleCI job {current_job} invokes orb step {step_key}; "
                        "behavior was not resolved"
                    )
                elif step_key not in _BUILTIN_STEPS:
                    unknowns.add(
                        f"CircleCI job {current_job} invokes custom step {step_key}; "
                        "behavior was not resolved"
                    )
                continue

            command, reason = _literal_command(value)
            if command is not None:
                step_name = ""
                if value.startswith("{"):
                    fields = {
                        match.group("key"): _strip_scalar(match.group("value"))
                        for match in _INLINE_FIELD_RE.finditer(value[1:-1])
                    }
                    step_name = fields.get("name", "").strip()
                _append_command(
                    commands,
                    command=command,
                    file=relative,
                    job=current_job,
                    step_name=step_name,
                )
            elif reason == "mapping":
                pending_run = {"job": current_job}
            elif reason == "multiline":
                unknowns.add(
                    f"CircleCI job {current_job} has multiline run content that was not guessed"
                )
            elif reason == "dynamic":
                unknowns.add(
                    f"CircleCI job {current_job} has dynamic run content that was not guessed"
                )
            else:
                unknowns.add(
                    f"CircleCI job {current_job} has unsupported run content that was not guessed"
                )
            continue

        if pending_run is not None and indent >= 8 and parsed is not None:
            key, value = parsed
            if key == "name":
                pending_run["name"] = _strip_scalar(value)
            elif key == "command":
                command, reason = _literal_command(value)
                if command is not None:
                    pending_run["command"] = command
                elif reason:
                    pending_run["reason"] = reason
            continue

        if indent <= 6:
            flush_pending()

    flush_pending()
    return commands, sorted(unknowns)


def extend_circleci(payload: dict[str, Any], root: Path) -> None:
    files = [relative for relative in CONFIG_FILES if (root / relative).is_file()]
    if not files:
        return

    _core._add_named(payload["ci_systems"], "circleci", files=files)
    if len(files) > 1:
        payload["review_first_unknowns"].append(
            "Multiple CircleCI config files detected; active configuration was not inferred"
        )

    for relative in files:
        commands, unknowns = _extract_config(root / relative, relative)
        payload["review_first_unknowns"].extend(unknowns)
        for item in commands:
            source: dict[str, Any] = {
                "ci_system": "circleci",
                "file": str(item["file"]),
                "job": str(item["job"]),
            }
            step_name = str(item.get("step_name", "")).strip()
            if step_name:
                source["step_name"] = step_name
            command = str(item["command"])
            _core._add_proof_command(
                payload["recommended_proof_commands"],
                surface="circleci",
                command=command,
                confidence="medium",
                purpose=_core._classify_proof_purpose(command),
                evidence=[str(item["file"])],
                source=source,
            )
