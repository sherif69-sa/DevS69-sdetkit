from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.public_command_surface_report.v2"
DEFAULT_OUT = "build/sdetkit/public-command-surface-report.json"
LEGACY_CLI_PATH = "src/sdetkit/_legacy_cli.py"

INPUT_DIGEST_ALGORITHM = "sha256"
GENERATOR_SOURCE_LABEL = "src/sdetkit/public_command_surface_report.py"


def _update_input_digest(hasher: Any, label: str, content: bytes) -> None:
    label_bytes = label.encode("utf-8")
    hasher.update(len(label_bytes).to_bytes(8, "big"))
    hasher.update(label_bytes)
    hasher.update(len(content).to_bytes(8, "big"))
    hasher.update(content)


def public_command_surface_input_provenance(
    root: str | Path = ".",
    *,
    generator_path: str | Path | None = None,
) -> dict[str, Any]:
    repo_root = Path(root).resolve()
    generator = (
        Path(generator_path).resolve() if generator_path is not None else Path(__file__).resolve()
    )
    command_source = repo_root / LEGACY_CLI_PATH

    inputs: list[tuple[str, bytes]] = [
        ("schema_version", SCHEMA_VERSION.encode("utf-8")),
        (GENERATOR_SOURCE_LABEL, generator.read_bytes()),
        (LEGACY_CLI_PATH, command_source.read_bytes()),
    ]

    hasher = hashlib.sha256()
    for label, content in sorted(inputs, key=lambda item: item[0]):
        _update_input_digest(hasher, label, content)

    return {
        "digest_algorithm": INPUT_DIGEST_ALGORITHM,
        "input_digest": hasher.hexdigest(),
        "input_count": len(inputs),
        "source_file_count": 1,
        "generator_schema_version": SCHEMA_VERSION,
        "generator_source": GENERATOR_SOURCE_LABEL,
        "source_file": LEGACY_CLI_PATH,
    }


def validate_public_command_surface_report_freshness(
    root: str | Path,
    payload: dict[str, Any],
    *,
    generator_path: str | Path | None = None,
) -> dict[str, Any]:
    current = public_command_surface_input_provenance(
        root,
        generator_path=generator_path,
    )
    recorded = payload.get("input_provenance")
    reasons: list[str] = []

    if not isinstance(recorded, dict):
        recorded = {}
        reasons.append("missing_input_provenance")

    for field in (
        "digest_algorithm",
        "input_digest",
        "input_count",
        "source_file_count",
        "generator_schema_version",
        "generator_source",
        "source_file",
    ):
        if recorded.get(field) != current.get(field):
            reasons.append(f"{field}_mismatch")

    reasons = sorted(set(reasons))
    fresh = not reasons
    return {
        "status": "fresh" if fresh else "stale",
        "fresh": fresh,
        "reasons": reasons,
        "recorded_input_digest": recorded.get("input_digest", ""),
        "current_input_digest": current["input_digest"],
        "reporting_only": True,
        "repo_mutation": False,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def check_public_command_surface_report_freshness(
    *,
    root: str | Path,
    report_path: str | Path,
    generator_path: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(report_path)
    if not path.is_file():
        result = validate_public_command_surface_report_freshness(
            root,
            {},
            generator_path=generator_path,
        )
        result["reasons"] = sorted(set([*result["reasons"], "report_missing"]))
        result["status"] = "stale"
        result["fresh"] = False
        return result

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        result = validate_public_command_surface_report_freshness(
            root,
            {},
            generator_path=generator_path,
        )
        result["reasons"] = sorted(set([*result["reasons"], "report_invalid_json"]))
        result["status"] = "stale"
        result["fresh"] = False
        return result

    if not isinstance(payload, dict):
        payload = {}
    return validate_public_command_surface_report_freshness(
        root,
        payload,
        generator_path=generator_path,
    )


def render_public_command_surface_freshness_text(payload: dict[str, Any]) -> str:
    reasons = payload.get("reasons", [])
    reason_text = ",".join(str(reason) for reason in reasons) if reasons else "none"
    return "\n".join(
        [
            f"freshness_status={payload.get('status', 'stale')}",
            f"fresh={str(bool(payload.get('fresh', False))).lower()}",
            f"freshness_reasons={reason_text}",
            f"recorded_input_digest={payload.get('recorded_input_digest', '')}",
            f"current_input_digest={payload.get('current_input_digest', '')}",
            "reporting_only=true",
            "repo_mutation=false",
            "automation_allowed=false",
            "patch_application_allowed=false",
            "merge_authorized=false",
            "semantic_equivalence_proven=false",
        ]
    )


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
        "input_provenance": public_command_surface_input_provenance(repo_root),
        "command_count": len(commands),
        "stable_command_count": len(stable_commands),
        "hidden_command_count": len(hidden_commands),
        "tier_counts": dict(sorted(counts.items())),
        "stable_public_commands": stable_commands,
        "hidden_internal_commands": hidden_commands,
        "stable_commands": stable_commands,
        "hidden_commands": hidden_commands,
        "commands": commands,
        "review_first": True,
        "safe_to_patch": False,
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
    provenance = payload.get("input_provenance", {})
    if not isinstance(provenance, dict):
        provenance = {}

    lines = [
        "# SDETKit public command surface report",
        "",
        f"- report_status: {payload['report_status']}",
        f"- command_count: {payload['command_count']}",
        f"- stable_command_count: {payload['stable_command_count']}",
        f"- hidden_command_count: {payload['hidden_command_count']}",
        f"- input_digest: `{provenance.get('input_digest', '')}`",
        f"- digest_algorithm: `{provenance.get('digest_algorithm', '')}`",
        f"- input_count: {provenance.get('input_count', 0)}",
        f"- generator_source: `{provenance.get('generator_source', '')}`",
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
    parser.add_argument(
        "--check-freshness",
        action="store_true",
        help="Check the existing report against current deterministic inputs without rewriting it.",
    )
    ns = parser.parse_args(list(argv) if argv is not None else None)

    if ns.check_freshness:
        freshness = check_public_command_surface_report_freshness(
            root=ns.root,
            report_path=ns.out,
        )
        if ns.format == "json":
            sys.stdout.write(json.dumps(freshness, indent=2, sort_keys=True) + "\n")
        else:
            sys.stdout.write(render_public_command_surface_freshness_text(freshness) + "\n")
        return 0 if freshness["fresh"] else 1

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
