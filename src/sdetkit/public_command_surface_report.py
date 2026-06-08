from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.public_command_surface_report.v1"
DEFAULT_OUT = "build/sdetkit/public-command-surface-report.json"
LEGACY_CLI_PATH = "src/sdetkit/_legacy_cli.py"

AUTHORITY_FIELDS = (
    "automation_allowed",
    "patch_application_allowed",
    "merge_authorized",
    "semantic_equivalence_proven",
)

PUBLIC_STABLE_MARKER = "[Public / stable]"
ADVANCED_SUPPORTED_MARKER = "[Advanced but supported]"


def _authority_boundary() -> dict[str, bool]:
    return {field: False for field in AUTHORITY_FIELDS}


def _literal_string(node: ast.AST | None) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ""


def _keyword(call: ast.Call, name: str) -> ast.AST | None:
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _is_argparse_suppress(node: ast.AST | None) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "SUPPRESS"
        and isinstance(node.value, ast.Name)
        and node.value.id == "argparse"
    )


def _command_tier(command: str, help_text: str, *, hidden: bool, registration: str) -> str:
    if hidden:
        return "hidden_internal"
    if PUBLIC_STABLE_MARKER in help_text:
        return "public_stable"
    if ADVANCED_SUPPORTED_MARKER in help_text:
        return "advanced_supported"
    if registration == "passthrough":
        return "compatibility_passthrough"
    if any(
        token in command
        for token in (
            "phase",
            "closeout",
            "continuous-upgrade",
            "demo-asset",
            "example-asset",
        )
    ):
        return "legacy_compatibility"
    return "best_effort_supported"


def _record(
    *,
    command: str,
    help_text: str,
    hidden: bool,
    registration: str,
) -> dict[str, Any]:
    tier = _command_tier(
        command,
        help_text,
        hidden=hidden,
        registration=registration,
    )
    return {
        "command": command,
        "tier": tier,
        "registration": registration,
        "help_text": "" if hidden else help_text,
        "hidden_from_default_help": hidden,
        "stable_public": tier == "public_stable",
        "advanced_supported": tier == "advanced_supported",
        "review_first": True,
        "safe_to_patch": False,
    }


def _extract_commands_from_legacy_cli(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)

    records: dict[str, dict[str, Any]] = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        # Root parser registrations: sub.add_parser("command", help=...)
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_parser"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "sub"
            and node.args
        ):
            command = _literal_string(node.args[0])
            if not command:
                continue
            help_node = _keyword(node, "help")
            hidden = _is_argparse_suppress(help_node)
            help_text = "" if hidden else _literal_string(help_node)
            records.setdefault(
                command,
                _record(
                    command=command,
                    help_text=help_text,
                    hidden=hidden,
                    registration="root_parser",
                ),
            )

        # Compatibility/passthrough root registrations.
        if isinstance(node.func, ast.Name) and node.func.id == "_add_passthrough_subcommand":
            if len(node.args) < 2:
                continue
            command = _literal_string(node.args[1])
            if not command:
                continue
            help_node = _keyword(node, "help_text")
            hidden = _is_argparse_suppress(help_node)
            help_text = "" if hidden else _literal_string(help_node)
            records.setdefault(
                command,
                _record(
                    command=command,
                    help_text=help_text,
                    hidden=hidden,
                    registration="passthrough",
                ),
            )

    return [records[name] for name in sorted(records)]


def build_public_command_surface_report(root: str | Path = ".") -> dict[str, Any]:
    repo_root = Path(root).resolve()
    cli_path = repo_root / LEGACY_CLI_PATH
    commands = _extract_commands_from_legacy_cli(cli_path)
    counts = Counter(command["tier"] for command in commands)

    stable_commands = [
        command["command"] for command in commands if command["tier"] == "public_stable"
    ]
    hidden_commands = [
        command["command"] for command in commands if command["tier"] == "hidden_internal"
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "report_status": "review_required",
        "source_file": LEGACY_CLI_PATH,
        "command_count": len(commands),
        "stable_command_count": len(stable_commands),
        "hidden_command_count": len(hidden_commands),
        "tier_counts": dict(sorted(counts.items())),
        "stable_commands": stable_commands,
        "hidden_commands": hidden_commands,
        "commands": commands,
        "operator_summary": {
            "stable_surface_visible": bool(stable_commands),
            "hidden_surface_visible_with_show_hidden": bool(hidden_commands),
            "classification_source": "root argparse registration help text",
            "review_first": True,
            "safe_to_patch": False,
        },
        "rules": {
            "read_only": True,
            "public_behavior_changed": False,
            "hidden_commands_exposed": False,
            "review_first": True,
            "safe_to_patch": False,
        },
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "authority_boundary": _authority_boundary(),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# SDETKit public command surface report",
        "",
        f"- report_status: {payload['report_status']}",
        f"- command_count: {payload['command_count']}",
        f"- stable_command_count: {payload['stable_command_count']}",
        f"- hidden_command_count: {payload['hidden_command_count']}",
        "- review_first: true",
        "- safe_to_patch: false",
        "",
        "## Tier counts",
        "",
    ]

    tier_counts = payload.get("tier_counts")
    if isinstance(tier_counts, dict):
        for tier, count in sorted(tier_counts.items()):
            lines.append(f"- {tier}: {count}")

    lines.extend(["", "## Stable public commands", ""])
    stable = payload.get("stable_commands")
    if isinstance(stable, list) and stable:
        for command in stable:
            lines.append(f"- `{command}`")
    else:
        lines.append("- none")

    lines.extend(["", "## Hidden/internal commands", ""])
    hidden = payload.get("hidden_commands")
    if isinstance(hidden, list) and hidden:
        for command in hidden:
            lines.append(f"- `{command}`")
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Authority boundary",
            "",
            "- automation_allowed: false",
            "- patch_application_allowed: false",
            "- merge_authorized: false",
            "- semantic_equivalence_proven: false",
            "",
        ]
    )
    return "\n".join(lines)


def write_artifacts(
    *,
    root: str | Path = ".",
    out: str | Path = DEFAULT_OUT,
    markdown_out: str | Path | None = None,
) -> dict[str, Any]:
    payload = build_public_command_surface_report(root=root)
    out_path = Path(out)
    markdown_path = Path(markdown_out) if markdown_out else out_path.with_suffix(".md")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)

    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(payload) + "\n", encoding="utf-8")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit public-command-surface-report",
        description="Build a read-only stable/hidden command surface report.",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--markdown-out", default="")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    payload = write_artifacts(
        root=ns.root,
        out=ns.out,
        markdown_out=ns.markdown_out or None,
    )

    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_markdown(payload) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
