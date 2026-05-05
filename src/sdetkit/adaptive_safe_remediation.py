from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.adaptive_safe_remediation.v1"
PLAN_SCHEMA_VERSION = "sdetkit.adaptive_safe_fix.v1"
ALLOWED_PREFIXES = (
    ("PYTHONPATH=src", "python", "-m", "ruff", "format"),
    ("PYTHONPATH=src", "python", "-m", "ruff", "check"),
    ("PYTHONPATH=src", "python", "-m", "pytest", "-q"),
)
BLOCKED_TOKENS = {"git", "gh", "hub", "twine"}

CommandRunner = Callable[[list[str], Path], dict[str, Any]]


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _load_plan(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    if payload.get("schema_version") != PLAN_SCHEMA_VERSION:
        raise ValueError(f"unsupported safe fix plan schema in {path}")
    return payload


def _has_placeholder(command: str) -> bool:
    return "<" in command or ">" in command


def _split_command(command: str) -> list[str]:
    return shlex.split(command)


def _is_allowed_command(command: str) -> tuple[bool, str]:
    if _has_placeholder(command):
        return False, "command contains unresolved placeholder"
    try:
        parts = _split_command(command)
    except ValueError as exc:
        return False, f"command could not be parsed: {exc}"
    if not parts:
        return False, "command is empty"
    if any(part in BLOCKED_TOKENS for part in parts):
        return False, "command contains blocked mutation token"
    for prefix in ALLOWED_PREFIXES:
        if tuple(parts[: len(prefix)]) == prefix:
            return True, "allowed"
    return False, "command is outside the safe remediation allowlist"


def validate_plan(plan: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if plan.get("schema_version") != PLAN_SCHEMA_VERSION:
        reasons.append("unsupported schema_version")
    if plan.get("safe_to_auto_fix") is not True:
        reasons.append("safe_to_auto_fix is not true")
    if plan.get("fix_type") != "format_only":
        reasons.append("fix_type is not format_only")
    if plan.get("requires_human_review") is not False:
        reasons.append("requires_human_review is not false")
    commands = [str(command) for command in _as_list(plan.get("commands"))]
    if not commands:
        reasons.append("no commands to run")
    for command in commands:
        ok, reason = _is_allowed_command(command)
        if not ok:
            reasons.append(f"unsafe command `{command}`: {reason}")
    return not reasons, reasons


def _default_runner(parts: list[str], cwd: Path) -> dict[str, Any]:
    env_prefix: dict[str, str] = {}
    while parts and "=" in parts[0] and not parts[0].startswith("-"):
        key, value = parts.pop(0).split("=", 1)
        env_prefix[key] = value
    import os

    env = {**os.environ, **env_prefix}
    proc = subprocess.run(parts, cwd=cwd, env=env, capture_output=True, text=True, check=False)
    return {
        "cmd": parts,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "ok": proc.returncode == 0,
    }


def _run_commands(
    commands: Sequence[str], cwd: Path, command_runner: CommandRunner
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for command in commands:
        parts = _split_command(command)
        result = command_runner(parts, cwd)
        result["command"] = command
        result["ok"] = bool(result.get("ok", False))
        result["returncode"] = int(result.get("returncode", 1) or 0)
        results.append(result)
        if not result["ok"]:
            break
    return results


def build_result(
    plan: dict[str, Any], command_results: list[dict[str, Any]], validation_errors: list[str]
) -> dict[str, Any]:
    attempted = not validation_errors
    ok = attempted and all(bool(item.get("ok", False)) for item in command_results)
    status = "success" if ok else "blocked" if validation_errors else "failed"
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": ok,
        "status": status,
        "attempted": attempted,
        "safe_to_auto_fix": bool(plan.get("safe_to_auto_fix", False)),
        "fix_type": str(plan.get("fix_type", "unknown")),
        "source_code": str(plan.get("source_code", "UNKNOWN")),
        "validation_errors": validation_errors,
        "command_count": len(command_results),
        "commands": [
            {
                "command": str(item.get("command", "")),
                "returncode": int(item.get("returncode", 1)),
                "ok": bool(item.get("ok", False)),
                "stdout": str(item.get("stdout", ""))[-2000:],
                "stderr": str(item.get("stderr", ""))[-2000:],
            }
            for item in command_results
        ],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Adaptive Safe Remediation Result",
        "",
        f"- Status: `{result.get('status', 'unknown')}`",
        f"- OK: `{str(result.get('ok', False)).lower()}`",
        f"- Attempted: `{str(result.get('attempted', False)).lower()}`",
        f"- Fix type: `{result.get('fix_type', 'unknown')}`",
        f"- Source code: `{result.get('source_code', 'UNKNOWN')}`",
        "",
    ]
    errors = _as_list(result.get("validation_errors"))
    if errors:
        lines.append("## Validation errors")
        lines.extend(f"- {error}" for error in errors)
        lines.append("")
    commands = _as_list(result.get("commands"))
    if commands:
        lines.append("## Commands")
        for item in commands:
            row = _as_dict(item)
            lines.append(
                f"- `{row.get('command', '')}` → ok={row.get('ok')} rc={row.get('returncode')}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def run_plan(
    plan: dict[str, Any],
    *,
    cwd: Path | None = None,
    command_runner: CommandRunner = _default_runner,
) -> dict[str, Any]:
    valid, validation_errors = validate_plan(plan)
    command_results: list[dict[str, Any]] = []
    if valid:
        command_results = _run_commands(
            [str(command) for command in _as_list(plan.get("commands"))],
            cwd or Path.cwd(),
            command_runner,
        )
    return build_result(plan, command_results, validation_errors)


def run_plan_file(
    plan_path: Path,
    *,
    out_json: Path | None = None,
    out_md: Path | None = None,
    cwd: Path | None = None,
    command_runner: CommandRunner = _default_runner,
) -> dict[str, Any]:
    plan = _load_plan(plan_path)
    result = run_plan(plan, cwd=cwd, command_runner=command_runner)
    result["plan_path"] = plan_path.as_posix()
    if out_json is not None:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if out_md is not None:
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(render_markdown(result), encoding="utf-8")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.adaptive_safe_remediation")
    parser.add_argument("safe_fix_plan_json")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    parser.add_argument("--cwd", default="")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_plan_file(
            Path(args.safe_fix_plan_json),
            out_json=Path(args.out_json) if args.out_json else None,
            out_md=Path(args.out_md) if args.out_md else None,
            cwd=Path(args.cwd) if args.cwd else None,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"status: {result['status']}")
        print(f"ok: {str(result['ok']).lower()}")
        print(f"attempted: {str(result['attempted']).lower()}")
        for error in result.get("validation_errors", []):
            print(f"validation_error: {error}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
