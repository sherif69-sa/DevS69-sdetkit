from __future__ import annotations

from pathlib import Path
from typing import Any

from sdetkit.adoption_surface import core as _core

CONFIG_FILES = ("azure-pipelines.yml", "azure-pipelines.yaml")
_DYNAMIC_TOKENS = ("${{", "$[", "$(", "template:", "extends:")
_TASK_KEYS = {"bash", "powershell", "pwsh", "script"}
_SERVICE_CONNECTION_KEYS = (
    "azureSubscription:",
    "connectedServiceName:",
    "serviceConnection:",
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
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {"'", '"'}:
        return normalized[1:-1]
    return normalized


def _dynamic(value: str) -> bool:
    return any(token in value for token in _DYNAMIC_TOKENS)


def _literal_command(value: str) -> tuple[str | None, str | None]:
    normalized = value.strip()
    if not normalized:
        return None, "mapping"
    if normalized in {"|", ">", "|-", ">-", "|+", ">+"}:
        return None, "multiline"
    command = _strip_scalar(normalized)
    if not command:
        return None, "unsupported"
    return (None, "dynamic") if _dynamic(command) else (command, None)


def _context(job: str, step_name: str = "") -> str:
    suffix = f" step {step_name}" if step_name else ""
    return f"Azure DevOps job {job}{suffix}"


def _append_command(
    commands: list[dict[str, Any]],
    *,
    command: str,
    file: str,
    job: str,
    step_name: str = "",
    task_key: str,
) -> None:
    if _core._command_is_shell_message(command):
        return
    item: dict[str, Any] = {
        "command": command,
        "file": file,
        "job": job,
        "task_key": task_key,
    }
    if step_name:
        item["step_name"] = step_name
    commands.append(item)


def _extract_config(path: Path, relative: str) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return [], []

    commands: list[dict[str, Any]] = []
    unknowns: set[str] = set()
    current_job = "pipeline"
    current_job_review_first = False
    current_step: dict[str, str] | None = None
    step_indent = -1

    def flush_step() -> None:
        nonlocal current_step
        if current_step is None:
            return
        context = _context(current_step["job"], current_step.get("name", ""))
        command = current_step.get("command", "").strip()
        reason = current_step.get("reason", "")
        if command:
            _append_command(
                commands,
                command=command,
                file=relative,
                job=current_step["job"],
                step_name=current_step.get("name", ""),
                task_key=current_step["task_key"],
            )
        elif reason == "multiline":
            unknowns.add(f"{context} has multiline script content that was not guessed")
        elif reason == "dynamic":
            unknowns.add(f"{context} has dynamic script content that was not guessed")
        else:
            unknowns.add(f"{context} has unsupported script content that was not guessed")
        current_step = None

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = _indent(raw_line)
        parsed = _yaml_key(raw_line)

        if _dynamic(stripped):
            if "template:" in stripped or "extends:" in stripped:
                unknowns.add(
                    "Azure DevOps templates or extends detected; referenced behavior was not resolved"
                )
            elif "${{" in stripped or "$[" in stripped:
                unknowns.add(
                    "Azure DevOps expressions detected; expression values were not resolved"
                )

        if indent <= step_indent and current_step is not None:
            flush_step()

        if stripped.startswith("- job:") or stripped.startswith("job:"):
            if parsed is not None:
                current_job = _strip_scalar(parsed[1]) or "unnamed"
            current_job_review_first = False
            continue
        if stripped.startswith("- deployment:") or stripped.startswith("deployment:"):
            if parsed is not None:
                current_job = _strip_scalar(parsed[1]) or "unnamed_deployment"
            current_job_review_first = True
            unknowns.add(
                f"Azure DevOps deployment job {current_job} detected; environment behavior was not resolved"
            )
            continue
        if stripped.startswith("strategy:") or stripped.startswith("matrix:"):
            current_job_review_first = True
            unknowns.add(
                f"Azure DevOps job {current_job} declares strategy or matrix behavior that was not resolved"
            )
            continue
        if stripped.startswith("variables:") or stripped.startswith("- group:"):
            unknowns.add(
                "Azure DevOps variables or variable groups detected; values were not resolved"
            )
            continue
        if stripped.startswith("resources:") or any(
            token in stripped for token in _SERVICE_CONNECTION_KEYS
        ):
            unknowns.add(
                "Azure DevOps external resources or service connections detected; behavior was not resolved"
            )
            continue

        if not stripped.startswith("- "):
            if current_step is not None and parsed is not None and indent > step_indent:
                key, value = parsed
                if key == "displayName":
                    current_step["name"] = _strip_scalar(value)
            continue

        step_text = stripped[2:].strip()
        step_parsed = _yaml_key(step_text)
        if step_parsed is None:
            continue
        task_key, value = step_parsed
        if task_key == "template":
            unknowns.add(
                f"Azure DevOps job {current_job} invokes a template; template behavior was not resolved"
            )
            continue
        if task_key == "task":
            unknowns.add(
                f"Azure DevOps job {current_job} invokes task {_strip_scalar(value)}; task behavior was not resolved"
            )
            continue
        if task_key not in _TASK_KEYS:
            continue
        if current_job_review_first:
            unknowns.add(
                f"Azure DevOps job {current_job} is dynamic or deployment-scoped; "
                "script content was not promoted"
            )
            continue

        command, reason = _literal_command(value)
        if command is not None:
            _append_command(
                commands,
                command=command,
                file=relative,
                job=current_job,
                task_key=task_key,
            )
        else:
            current_step = {
                "job": current_job,
                "task_key": task_key,
                "reason": reason or "unsupported",
            }
            step_indent = indent

    flush_step()
    return commands, sorted(unknowns)


def extend_azure_devops(payload: dict[str, Any], root: Path) -> None:
    files = sorted(relative for relative in CONFIG_FILES if (root / relative).is_file())
    if not files:
        return

    _core._add_named(payload["ci_systems"], "azure_devops", files=files)
    if len(files) > 1:
        payload["review_first_unknowns"].append(
            "Multiple Azure DevOps pipeline files detected; active pipeline was not inferred"
        )

    for relative in files:
        commands, unknowns = _extract_config(root / relative, relative)
        payload["review_first_unknowns"].extend(unknowns)
        for item in commands:
            source: dict[str, Any] = {
                "ci_system": "azure_devops",
                "file": str(item["file"]),
                "job": str(item["job"]),
                "task_key": str(item["task_key"]),
            }
            step_name = str(item.get("step_name", "")).strip()
            if step_name:
                source["step_name"] = step_name
            command = str(item["command"])
            _core._add_proof_command(
                payload["recommended_proof_commands"],
                surface="azure_devops",
                command=command,
                confidence="medium",
                purpose=_core._classify_proof_purpose(command),
                evidence=[str(item["file"])],
                source=source,
            )
