from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from .adoption_proof_recommendations import (
    SCHEMA_VERSION as PROOF_RECOMMENDATIONS_SCHEMA_VERSION,
)
from .adoption_proof_recommendations import build_proof_recommendations_payload
from .adoption_repo_topology import SCHEMA_VERSION as REPO_TOPOLOGY_SCHEMA_VERSION
from .adoption_repo_topology import build_repo_topology_payload
from .adoption_surface import SCHEMA_VERSION as ADOPTION_SURFACE_SCHEMA_VERSION
from .adoption_surface import discover_adoption_surface, validate_adoption_surface_payload

SCHEMA_VERSION = "sdetkit.diagnostic_execution_plan.v1"
DEFAULT_OUT = "build/sdetkit/diagnostic-execution-plan.json"
DEFAULT_TIMEOUT_SECONDS = 180
TEST_TIMEOUT_SECONDS = 300

AUTHORITY_FIELDS = (
    "execution_allowed",
    "automation_allowed",
    "patch_application_allowed",
    "merge_authorized",
    "semantic_equivalence_proven",
)

SOURCE_AUTHORITY_FIELDS = (
    "automation_allowed",
    "patch_application_allowed",
    "merge_authorized",
    "semantic_equivalence_proven",
)

ENV_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$", re.DOTALL)
SHELL_CONTROL_TOKENS = ("&&", "||", ";", "|", ">", "<", "`", "$(")

JsonObject = dict[str, Any]


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def _authority_boundary() -> dict[str, bool]:
    return {field: False for field in AUTHORITY_FIELDS}


def _read_json_object(path: str | Path | None) -> JsonObject | None:
    if not path:
        return None
    loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return loaded


def _assert_false_authority(payload: Mapping[str, Any], *, source: str) -> None:
    expanded = [field for field in SOURCE_AUTHORITY_FIELDS if _bool(payload.get(field))]
    if expanded:
        raise ValueError(f"{source} expands authority: " + ", ".join(expanded))


def _validate_sources(
    surface: Mapping[str, Any],
    proof: Mapping[str, Any],
    topology: Mapping[str, Any],
) -> None:
    surface_errors = validate_adoption_surface_payload(surface)
    if surface_errors:
        raise ValueError("invalid adoption surface payload: " + "; ".join(surface_errors))

    if _string(proof.get("schema_version")) != PROOF_RECOMMENDATIONS_SCHEMA_VERSION:
        raise ValueError("adoption proof recommendations schema is not supported")
    if not isinstance(proof.get("proof_recommendations"), list):
        raise ValueError("adoption proof recommendations must contain a recommendation list")
    if not isinstance(proof.get("review_first_items"), list):
        raise ValueError("adoption proof recommendations must contain review-first items")

    if _string(topology.get("schema_version")) != REPO_TOPOLOGY_SCHEMA_VERSION:
        raise ValueError("adoption repository topology schema is not supported")
    if not isinstance(topology.get("manual_proof_sequence"), list):
        raise ValueError("adoption repository topology must contain a manual proof sequence")

    _assert_false_authority(surface, source="adoption surface")
    _assert_false_authority(proof, source="adoption proof recommendations")
    _assert_false_authority(topology, source="adoption repository topology")

    surface_identity = _as_dict(surface.get("repo_identity"))
    if _as_dict(proof.get("repo_identity")) != surface_identity:
        raise ValueError("adoption proof recommendations repo identity does not match surface")
    if _as_dict(topology.get("repo_identity")) != surface_identity:
        raise ValueError("adoption repository topology repo identity does not match surface")

    proof_keys = {
        (
            _string(item.get("command")),
            _string(item.get("surface")) or "unknown",
            _string(item.get("purpose")) or "unknown",
        )
        for item in (_as_dict(value) for value in _as_list(proof.get("proof_recommendations")))
        if _string(item.get("command"))
    }
    topology_keys = {
        (
            _string(item.get("command")),
            _string(item.get("surface")) or "unknown",
            _string(item.get("purpose")) or "unknown",
        )
        for item in (_as_dict(value) for value in _as_list(topology.get("manual_proof_sequence")))
        if _string(item.get("command"))
    }
    unknown = sorted(topology_keys - proof_keys)
    if unknown:
        raise ValueError(
            "adoption repository topology contains commands absent from proof recommendations"
        )


def _items(payload: Mapping[str, Any], field: str) -> list[JsonObject]:
    return [_as_dict(item) for item in _as_list(payload.get(field)) if _as_dict(item)]


def _named_item(payload: Mapping[str, Any], field: str, name: str) -> JsonObject:
    return next(
        (item for item in _items(payload, field) if _string(item.get("name")) == name),
        {},
    )


def _surface_item(surface_payload: Mapping[str, Any], surface: str, command: str) -> JsonObject:
    if surface == "docs":
        tool = "sphinx" if "sphinx" in command else "mkdocs" if "mkdocs" in command else ""
        return _named_item(surface_payload, "docs_tools", tool) if tool else {}
    if surface == "quality":
        return {}
    if surface == "javascript_typescript":
        return _named_item(surface_payload, "detected_languages", "javascript_typescript")
    return _named_item(surface_payload, "detected_languages", surface)


def _surface_evidence(surface_payload: Mapping[str, Any], surface: str, command: str) -> list[str]:
    item = _surface_item(surface_payload, surface, command)
    paths: set[str] = set()
    for field in ("evidence", "files", "paths"):
        for value in _as_list(item.get(field)):
            text = _string(value)
            if text:
                paths.add(text)

    if surface == "quality" and command == "make proof-after-format":
        paths.add("Makefile")
    elif surface == "quality" and "pre_commit" in command:
        paths.add(".pre-commit-config.yaml")

    return sorted(paths)


def _surface_confidence(surface_payload: Mapping[str, Any], surface: str, command: str) -> str:
    value = _string(_surface_item(surface_payload, surface, command).get("confidence")).lower()
    return value if value in {"high", "medium", "low"} else "unknown"


def _command_confidence(recommendation: Mapping[str, Any]) -> str:
    value = _string(recommendation.get("confidence")).lower()
    return value if value in {"high", "medium", "low"} else "unknown"


def _safe_relative_cwd(value: str) -> bool:
    if value == ".":
        return True
    path = PurePosixPath(value)
    return (
        bool(value)
        and not path.is_absolute()
        and ".." not in path.parts
        and value == path.as_posix()
    )


def _dotnet_cwd(surface_payload: Mapping[str, Any]) -> tuple[str, str, str]:
    evidence = _surface_evidence(surface_payload, "dotnet", "dotnet test")
    parents = sorted({PurePosixPath(path).parent.as_posix() for path in evidence})
    if "." in parents:
        return ".", "high", "root-level .NET project or solution evidence"
    if len(parents) == 1:
        return parents[0], "high", "single .NET workspace inferred from discovered project files"
    return ".", "unknown", "multiple .NET workspace roots detected; command cwd is not proven"


def _command_cwd(
    recommendation: Mapping[str, Any],
    *,
    surface_payload: Mapping[str, Any],
    surface: str,
) -> tuple[str, str, str]:
    explicit = _string(recommendation.get("cwd"))
    if explicit:
        if _safe_relative_cwd(explicit):
            return explicit, "high", "cwd declared by proof recommendation"
        return ".", "unknown", "declared command cwd is not a safe repository-relative path"
    if surface == "dotnet":
        return _dotnet_cwd(surface_payload)
    return ".", "high", "command is grounded by repository-root discovery"


def _parse_command(command: str) -> tuple[list[str], dict[str, str], str]:
    if any(token in command for token in SHELL_CONTROL_TOKENS):
        return [], {}, "shell control syntax is not eligible for structured execution planning"

    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return [], {}, "command could not be parsed into argv"

    environment: dict[str, str] = {}
    while tokens and ENV_ASSIGNMENT_RE.match(tokens[0]):
        key, value = tokens.pop(0).split("=", 1)
        environment[key] = value

    if not tokens:
        return [], environment, "command does not contain an executable argv"
    return tokens, dict(sorted(environment.items())), ""


def _expected_artifacts(command: str, purpose: str) -> list[JsonObject]:
    artifacts: list[JsonObject] = [
        {
            "kind": "command_result",
            "locator": "captured://stdout-stderr-exit-code",
            "required": True,
        }
    ]
    if purpose == "docs" and "sphinx" in command:
        artifacts.append(
            {
                "kind": "directory",
                "path": "docs/_build/html",
                "required_on_success": True,
            }
        )
    elif purpose == "docs" and "mkdocs" in command:
        artifacts.append(
            {
                "kind": "directory",
                "path": "site",
                "required_on_success": True,
            }
        )
    return artifacts


def _timeout_seconds(purpose: str) -> int:
    return TEST_TIMEOUT_SECONDS if purpose == "test" else DEFAULT_TIMEOUT_SECONDS


def _command_id(command: str, cwd: str) -> str:
    digest = hashlib.sha256(f"{cwd}\0{command}".encode()).hexdigest()[:16]
    return f"command-{digest}"


def _proof_by_key(proof_payload: Mapping[str, Any]) -> dict[tuple[str, str, str], JsonObject]:
    result: dict[tuple[str, str, str], JsonObject] = {}
    for item in _items(proof_payload, "proof_recommendations"):
        command = _string(item.get("command"))
        if not command:
            continue
        key = (
            command,
            _string(item.get("surface")) or "unknown",
            _string(item.get("purpose")) or "unknown",
        )
        result.setdefault(key, item)
    return result


def _evidence_references(
    *,
    surface_payload: Mapping[str, Any],
    proof_payload: Mapping[str, Any],
    topology_payload: Mapping[str, Any],
    recommendation: Mapping[str, Any],
    sequence_index: int,
    surface: str,
    command: str,
) -> list[JsonObject]:
    references: list[JsonObject] = [
        {
            "source": "adoption_proof_recommendations",
            "schema_version": _string(proof_payload.get("schema_version")),
            "location": (
                f"proof_recommendations[index={int(recommendation.get('index', 0) or 0)}]"
            ),
        },
        {
            "source": "adoption_repo_topology",
            "schema_version": _string(topology_payload.get("schema_version")),
            "location": f"manual_proof_sequence[{sequence_index}]",
        },
    ]
    paths = _surface_evidence(surface_payload, surface, command)
    if paths:
        references.append(
            {
                "source": "adoption_surface",
                "schema_version": _string(surface_payload.get("schema_version")),
                "paths": paths,
            }
        )
    return references


def _command_entry(
    *,
    step: int,
    sequence_index: int,
    sequence_item: Mapping[str, Any],
    recommendation: Mapping[str, Any],
    surface_payload: Mapping[str, Any],
    proof_payload: Mapping[str, Any],
    topology_payload: Mapping[str, Any],
) -> JsonObject:
    command = _string(sequence_item.get("command"))
    surface = _string(sequence_item.get("surface")) or "unknown"
    purpose = _string(sequence_item.get("purpose")) or "unknown"
    operator_level = _string(sequence_item.get("operator_level")) or "review_first"
    cwd, cwd_confidence, cwd_reason = _command_cwd(
        recommendation,
        surface_payload=surface_payload,
        surface=surface,
    )
    argv, environment, parse_reason = _parse_command(command)

    review_reasons: list[str] = []
    if operator_level == "review_first":
        review_reasons.append("source recommendation is review-first")
    if parse_reason:
        review_reasons.append(parse_reason)
    if cwd_confidence == "unknown":
        review_reasons.append(cwd_reason)
    if _command_confidence(recommendation) in {"low", "unknown"}:
        review_reasons.append("command confidence requires operator review")

    return {
        "step": step,
        "command_id": _command_id(command, cwd),
        "display_command": command,
        "argv": argv,
        "environment": environment,
        "cwd": cwd,
        "cwd_confidence": cwd_confidence,
        "cwd_reason": cwd_reason,
        "surface": surface,
        "purpose": purpose,
        "operator_level": operator_level,
        "surface_confidence": _surface_confidence(surface_payload, surface, command),
        "command_confidence": _command_confidence(recommendation),
        "evidence": _evidence_references(
            surface_payload=surface_payload,
            proof_payload=proof_payload,
            topology_payload=topology_payload,
            recommendation=recommendation,
            sequence_index=sequence_index,
            surface=surface,
            command=command,
        ),
        "expected_artifacts": _expected_artifacts(command, purpose),
        "timeout_seconds": _timeout_seconds(purpose),
        "policies": {
            "workspace": "isolated_copy_required",
            "network": "deny_by_default",
            "dependency_install": "forbidden",
            "source_target_mutation": "forbidden",
            "isolated_workspace_writes": "capture_and_review",
        },
        "review_required": bool(review_reasons),
        "review_reasons": review_reasons,
        "execution_allowed": False,
    }


def _review_first_items(
    surface_payload: Mapping[str, Any],
    proof_payload: Mapping[str, Any],
    commands: list[JsonObject],
) -> list[JsonObject]:
    rows: list[JsonObject] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, description: str, *, command_id: str = "") -> None:
        normalized = _string(description)
        key = (kind, f"{command_id}\0{normalized}")
        if not normalized or key in seen:
            return
        seen.add(key)
        row: JsonObject = {"kind": kind, "description": normalized}
        if command_id:
            row["command_id"] = command_id
        rows.append(row)

    for item in _as_list(surface_payload.get("review_first_unknowns")):
        add("repository_unknown", _string(item))
    for item in _items(proof_payload, "review_first_items"):
        add("proof_unknown", _string(item.get("description")))
    for command in commands:
        for reason in _as_list(command.get("review_reasons")):
            add("command_review", _string(reason), command_id=_string(command.get("command_id")))

    return rows


def build_diagnostic_execution_plan(
    repo_root: str | Path = ".",
    *,
    surface_payload: JsonObject | None = None,
    proof_payload: JsonObject | None = None,
    topology_payload: JsonObject | None = None,
) -> JsonObject:
    surface = (
        surface_payload if surface_payload is not None else discover_adoption_surface(repo_root)
    )
    proof = (
        proof_payload
        if proof_payload is not None
        else build_proof_recommendations_payload(repo_root, surface_payload=surface)
    )
    topology = (
        topology_payload
        if topology_payload is not None
        else build_repo_topology_payload(
            repo_root,
            surface_payload=surface,
            proof_payload=proof,
        )
    )
    _validate_sources(surface, proof, topology)

    recommendations = _proof_by_key(proof)
    commands: list[JsonObject] = []
    seen_commands: set[tuple[str, str]] = set()

    for sequence_index, raw_item in enumerate(_as_list(topology.get("manual_proof_sequence"))):
        sequence_item = _as_dict(raw_item)
        command = _string(sequence_item.get("command"))
        if not command:
            continue
        key = (
            command,
            _string(sequence_item.get("surface")) or "unknown",
            _string(sequence_item.get("purpose")) or "unknown",
        )
        recommendation = recommendations[key]
        cwd, _, _ = _command_cwd(
            recommendation,
            surface_payload=surface,
            surface=key[1],
        )
        dedupe_key = (command, cwd)
        if dedupe_key in seen_commands:
            continue
        seen_commands.add(dedupe_key)
        commands.append(
            _command_entry(
                step=len(commands) + 1,
                sequence_index=sequence_index,
                sequence_item=sequence_item,
                recommendation=recommendation,
                surface_payload=surface,
                proof_payload=proof,
                topology_payload=topology,
            )
        )

    review_first = _review_first_items(surface, proof, commands)
    required_count = sum(item["operator_level"] == "required" for item in commands)
    recommended_count = sum(item["operator_level"] == "recommended" for item in commands)
    review_command_count = sum(item["review_required"] is True for item in commands)

    return {
        "schema_version": SCHEMA_VERSION,
        "plan_status": "generated",
        "repo_root": Path(repo_root).as_posix(),
        "repo_identity": surface.get("repo_identity", {}),
        "source_artifacts": {
            "adoption_surface": ADOPTION_SURFACE_SCHEMA_VERSION,
            "adoption_proof_recommendations": PROOF_RECOMMENDATIONS_SCHEMA_VERSION,
            "adoption_repo_topology": REPO_TOPOLOGY_SCHEMA_VERSION,
        },
        "summary": {
            "command_count": len(commands),
            "required_count": required_count,
            "recommended_count": recommended_count,
            "review_command_count": review_command_count,
            "review_first_item_count": len(review_first),
            "recommended_next_action": "review_plan_before_execution",
        },
        "commands": commands,
        "review_first_items": review_first,
        "policies": {
            "execution_default": "deny",
            "explicit_execution_authorization_required": True,
            "workspace_mode": "isolated_copy_required",
            "source_target_used_as_command_cwd": False,
            "network_default": "deny",
            "automatic_dependency_install_allowed": False,
            "source_target_mutation_allowed": False,
        },
        "rules": {
            "plan_only": True,
            "read_only": True,
            "no_command_execution": True,
            "no_dependency_install": True,
            "no_target_repo_mutation": True,
            "no_patch_application": True,
        },
        "execution_allowed": False,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "authority_boundary": _authority_boundary(),
    }


def validate_diagnostic_execution_plan(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return ["payload must be a JSON object"]

    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if not isinstance(payload.get("commands"), list):
        errors.append("commands must be a list")
    if not isinstance(payload.get("review_first_items"), list):
        errors.append("review_first_items must be a list")
    if not isinstance(payload.get("summary"), dict):
        errors.append("summary must be an object")
    if not isinstance(payload.get("policies"), dict):
        errors.append("policies must be an object")

    for field in AUTHORITY_FIELDS:
        if payload.get(field) is not False:
            errors.append(f"{field} must be false")

    seen_ids: set[str] = set()
    for index, raw_item in enumerate(_as_list(payload.get("commands")), start=1):
        item = _as_dict(raw_item)
        if not item:
            errors.append(f"commands[{index}] must be an object")
            continue
        command_id = _string(item.get("command_id"))
        if not command_id:
            errors.append(f"commands[{index}].command_id is required")
        elif command_id in seen_ids:
            errors.append(f"duplicate command_id: {command_id}")
        seen_ids.add(command_id)
        if not _string(item.get("display_command")):
            errors.append(f"commands[{index}].display_command is required")
        if not isinstance(item.get("argv"), list):
            errors.append(f"commands[{index}].argv must be a list")
        cwd = _string(item.get("cwd"))
        if not _safe_relative_cwd(cwd):
            errors.append(f"commands[{index}].cwd must be a safe repository-relative path")
        if item.get("execution_allowed") is not False:
            errors.append(f"commands[{index}].execution_allowed must be false")

    boundary = _as_dict(payload.get("authority_boundary"))
    for field in AUTHORITY_FIELDS:
        if boundary.get(field) is not False:
            errors.append(f"authority_boundary.{field} must be false")
    return errors


def write_diagnostic_execution_plan_artifact(
    *,
    repo_root: str | Path = ".",
    surface_json: str | Path | None = None,
    proof_json: str | Path | None = None,
    topology_json: str | Path | None = None,
    out: str | Path = DEFAULT_OUT,
) -> JsonObject:
    payload = build_diagnostic_execution_plan(
        repo_root,
        surface_payload=_read_json_object(surface_json),
        proof_payload=_read_json_object(proof_json),
        topology_payload=_read_json_object(topology_json),
    )
    errors = validate_diagnostic_execution_plan(payload)
    if errors:
        raise ValueError("invalid diagnostic execution plan: " + "; ".join(errors))
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def render_diagnostic_execution_plan_text(payload: Mapping[str, Any]) -> str:
    summary = _as_dict(payload.get("summary"))
    lines = [
        "diagnostic_execution_plan_status=generated",
        f"command_count={int(summary.get('command_count', 0) or 0)}",
        f"required_count={int(summary.get('required_count', 0) or 0)}",
        f"recommended_count={int(summary.get('recommended_count', 0) or 0)}",
        f"review_command_count={int(summary.get('review_command_count', 0) or 0)}",
        f"review_first_item_count={int(summary.get('review_first_item_count', 0) or 0)}",
        "commands:",
    ]
    commands = [_as_dict(item) for item in _as_list(payload.get("commands")) if _as_dict(item)]
    if commands:
        for item in commands:
            lines.append(
                "- "
                f"step={item['step']}; "
                f"level={item['operator_level']}; "
                f"surface={item['surface']}; "
                f"cwd={item['cwd']}; "
                f"execution_allowed=false; "
                f"command={item['display_command']}"
            )
    else:
        lines.append("- none")
    lines.append("authority_boundary:")
    boundary = _as_dict(payload.get("authority_boundary"))
    lines.extend(
        f"- {field}={str(_bool(boundary.get(field))).lower()}" for field in AUTHORITY_FIELDS
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sdetkit.diagnostic_execution_plan",
        description="Build a deterministic, non-executing repository diagnostic command plan.",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--surface-json", default="")
    parser.add_argument("--proof-json", default="")
    parser.add_argument("--topology-json", default="")
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--format", choices=["json", "text"], default="json")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    payload = write_diagnostic_execution_plan_artifact(
        repo_root=ns.root,
        surface_json=ns.surface_json or None,
        proof_json=ns.proof_json or None,
        topology_json=ns.topology_json or None,
        out=ns.out,
    )
    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_diagnostic_execution_plan_text(payload) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
