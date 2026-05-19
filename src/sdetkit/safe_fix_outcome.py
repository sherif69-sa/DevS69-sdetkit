from __future__ import annotations

import json
from pathlib import Path
from typing import Any

JsonObject = dict[str, Any]
SCHEMA_VERSION = ".".join(("sdetkit", "safe", "fix", "outcome", "v1"))


def _load_json(path: Path) -> JsonObject:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _string_list(value: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in _as_list(value):
        text = _string(item)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _first_nonempty(*values: Any) -> str:
    for value in values:
        text = _string(value)
        if text and text.lower() not in {"none", "null", "unknown"}:
            return text
    return ""


def _existing_artifact(artifacts_dir: Path, name: str) -> str:
    path = artifacts_dir / name
    return path.as_posix() if path.exists() else ""


def _files_from_sources(*sources: Any) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for source in sources:
        for item in _as_list(source):
            text = _string(item)
            if not text or text in seen:
                continue
            seen.add(text)
            values.append(text)
    return values


def _command_results(remediation_result: JsonObject) -> list[JsonObject]:
    values: list[JsonObject] = []
    for item in _as_list(remediation_result.get("commands")):
        if not isinstance(item, dict):
            continue
        command = _string(item.get("command"))
        if not command:
            continue
        values.append(
            {
                "command": command,
                "ok": _truthy(item.get("ok")),
                "returncode": item.get("returncode", item.get("exit_code", "")),
            }
        )
    return values


def build_outcome(artifacts_dir: Path) -> JsonObject:
    artifacts_dir = Path(artifacts_dir)
    bridge = _load_json(artifacts_dir / "pr-quality-safe-remediation-bridge.json")
    plan = _load_json(artifacts_dir / "safe-fix-plan.json")
    remediation = _load_json(artifacts_dir / "adaptive-safe-remediation-result.json")
    commit = _load_json(artifacts_dir / "adaptive-safe-commit-result.json")

    attempted = (
        _truthy(bridge.get("attempted"))
        or _truthy(remediation.get("attempted"))
        or bool(remediation)
        or _truthy(commit.get("attempted"))
    )
    remediation_ok = _truthy(bridge.get("remediation_ok")) or _truthy(remediation.get("ok"))

    commit_sha = _first_nonempty(
        bridge.get("commit_sha"),
        commit.get("commit_sha"),
        commit.get("sha"),
        commit.get("commit"),
    )
    committed = (
        _truthy(bridge.get("commit_ok")) or _truthy(commit.get("committed")) or bool(commit_sha)
    )
    pushed = _truthy(bridge.get("commit_pushed")) or _truthy(commit.get("pushed"))

    if not attempted:
        status = "not_attempted"
    elif pushed:
        status = "pushed"
    elif committed:
        status = "committed_not_pushed"
    elif remediation_ok:
        status = "remediated_not_committed"
    else:
        status = "attempted_without_success"

    affected_files = _files_from_sources(
        bridge.get("affected_files"),
        plan.get("affected_files"),
        commit.get("affected_files"),
        commit.get("files"),
        remediation.get("affected_files"),
        remediation.get("changed_files"),
    )

    proof_commands = _string_list(plan.get("proof_commands"))

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "attempted": attempted,
        "remediation_ok": remediation_ok,
        "committed": committed,
        "pushed": pushed,
        "commit_sha": commit_sha or "none",
        "affected_files": affected_files,
        "reason": _first_nonempty(
            bridge.get("reason"),
            commit.get("reason"),
            remediation.get("reason"),
            plan.get("reason"),
            "no safe-fix outcome recorded",
        ),
        "safe_to_auto_fix": _truthy(plan.get("safe_to_auto_fix")),
        "fix_type": _string(plan.get("fix_type"), "unknown"),
        "proof_commands": proof_commands,
        "command_results": _command_results(remediation),
        "artifacts": {
            "bridge": _existing_artifact(
                artifacts_dir,
                "pr-quality-safe-remediation-bridge.json",
            ),
            "plan": _existing_artifact(artifacts_dir, "safe-fix-plan.json"),
            "remediation": _existing_artifact(
                artifacts_dir,
                "adaptive-safe-remediation-result.json",
            ),
            "commit": _existing_artifact(
                artifacts_dir,
                "adaptive-safe-commit-result.json",
            ),
        },
    }


def render_markdown(outcome: JsonObject) -> str:
    files = _string_list(outcome.get("affected_files"))
    proof_commands = _string_list(outcome.get("proof_commands"))
    command_results = [
        item for item in _as_list(outcome.get("command_results")) if isinstance(item, dict)
    ]

    lines = [
        "# Safe fix outcome",
        "",
        f"- Status: `{_string(outcome.get('status'), 'unknown')}`",
        f"- Attempted: `{str(_truthy(outcome.get('attempted'))).lower()}`",
        f"- Remediation OK: `{str(_truthy(outcome.get('remediation_ok'))).lower()}`",
        f"- Committed: `{str(_truthy(outcome.get('committed'))).lower()}`",
        f"- Pushed: `{str(_truthy(outcome.get('pushed'))).lower()}`",
        f"- Commit SHA: `{_string(outcome.get('commit_sha'), 'none')}`",
        f"- Fix type: `{_string(outcome.get('fix_type'), 'unknown')}`",
        f"- Reason: {_string(outcome.get('reason'), 'none')}",
        "- Files: " + (", ".join(f"`{item}`" for item in files) if files else "`none`"),
        "",
        "## Proof after fix",
        "",
    ]

    if proof_commands:
        lines.extend(f"- `{item}`" for item in proof_commands)
    elif command_results:
        for item in command_results:
            command = _string(item.get("command"))
            ok = str(_truthy(item.get("ok"))).lower()
            lines.append(f"- `{command}` -> ok=`{ok}`")
    else:
        lines.append("- none")

    return "\n".join(lines).rstrip() + "\n"


def write_outcome(artifacts_dir: Path) -> JsonObject:
    artifacts_dir = Path(artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    outcome = build_outcome(artifacts_dir)
    (artifacts_dir / "safe-fix-outcome.json").write_text(
        json.dumps(outcome, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (artifacts_dir / "safe-fix-outcome.md").write_text(
        render_markdown(outcome),
        encoding="utf-8",
    )
    return outcome
