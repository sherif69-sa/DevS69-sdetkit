from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .adoption_surface import discover_adoption_surface, validate_adoption_surface_payload

SCHEMA_VERSION = "sdetkit.adoption_proof_recommendations.v1"

AUTHORITY_FIELDS = (
    "automation_allowed",
    "patch_application_allowed",
    "merge_authorized",
    "semantic_equivalence_proven",
)


def _authority_boundary() -> dict[str, bool]:
    return {field: False for field in AUTHORITY_FIELDS}


def _command_text(item: dict[str, Any]) -> str:
    return str(item.get("command", "")).strip()


def _surface(item: dict[str, Any]) -> str:
    return str(item.get("surface", "unknown")).strip() or "unknown"


def _purpose(item: dict[str, Any]) -> str:
    return str(item.get("purpose", "unknown")).strip() or "unknown"


def _confidence(item: dict[str, Any]) -> str:
    value = str(item.get("confidence", "unknown")).strip().lower()
    if value in {"high", "medium", "low"}:
        return value
    return "unknown"


def _source(item: dict[str, Any]) -> dict[str, Any]:
    source = item.get("source")
    return dict(source) if isinstance(source, dict) else {}


def _operator_level(item: dict[str, Any]) -> str:
    purpose = _purpose(item)
    surface = _surface(item)
    command = _command_text(item)

    if not command:
        return "review_first"
    if command == "make proof-after-format":
        return "required"
    if purpose == "test":
        return "required"
    if purpose in {"docs", "quality"}:
        return "recommended"
    if surface in {"security", "ci"}:
        return "recommended"
    return "review_first"


def _reason(item: dict[str, Any]) -> str:
    purpose = _purpose(item)
    command = _command_text(item)

    if command == "make proof-after-format":
        return "full repository quality proof; run manually before merge confidence"
    if purpose == "test":
        return "test proof for detected target repo surface"
    if purpose == "docs":
        return "documentation proof for detected docs surface"
    if purpose == "quality":
        return "quality proof for detected formatter/lint/pre-commit surface"
    return "operator review required before trusting this proof command"


def _recommendation_from_command(item: dict[str, Any], index: int) -> dict[str, Any]:
    command = _command_text(item)
    level = _operator_level(item)
    recommendation: dict[str, Any] = {
        "index": index,
        "command": command,
        "surface": _surface(item),
        "purpose": _purpose(item),
        "confidence": _confidence(item),
        "operator_level": level,
        "execution_policy": "manual_only",
        "executes_target_code": bool(command),
        "manual_execution_required": True,
        "auto_run_allowed": False,
        "reason": _reason(item),
    }
    source = _source(item)
    if source:
        recommendation["source"] = source
        working_directory = str(source.get("working_directory", "")).strip()
        if working_directory:
            recommendation["working_directory"] = working_directory
    return recommendation


def _review_first_items(surface_payload: dict[str, Any]) -> list[dict[str, Any]]:
    unknowns = surface_payload.get("review_first_unknowns", [])
    if not isinstance(unknowns, list):
        return []

    return [
        {
            "description": str(item),
            "operator_level": "review_first",
            "manual_resolution_required": True,
            "auto_run_allowed": False,
            "reason": "unknown repo surface must be reviewed before proof execution",
        }
        for item in unknowns
    ]


def _first_manual_command(recommendations: list[dict[str, Any]]) -> str:
    for level in ("required", "recommended", "review_first"):
        for item in recommendations:
            if item["operator_level"] == level and item["command"]:
                return str(item["command"])
    return ""


def build_proof_recommendations_payload(
    repo_root: str | Path = ".",
    *,
    surface_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    surface = (
        surface_payload if surface_payload is not None else discover_adoption_surface(repo_root)
    )
    errors = validate_adoption_surface_payload(surface)
    if errors:
        raise ValueError("invalid adoption surface payload: " + "; ".join(errors))

    raw_commands = surface.get("recommended_proof_commands", [])
    if not isinstance(raw_commands, list):
        raw_commands = []

    recommendations = [
        _recommendation_from_command(item, index)
        for index, item in enumerate(raw_commands, start=1)
        if isinstance(item, dict)
    ]

    review_first = _review_first_items(surface)
    required_count = sum(1 for item in recommendations if item["operator_level"] == "required")
    recommended_count = sum(
        1 for item in recommendations if item["operator_level"] == "recommended"
    )
    confidence_counts = {
        confidence: sum(1 for item in recommendations if item["confidence"] == confidence)
        for confidence in ("high", "medium", "low", "unknown")
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "repo_identity": surface.get("repo_identity", {}),
        "summary": {
            "recommended_next_action": "review_and_run_manual_proof",
            "first_manual_command": _first_manual_command(recommendations),
            "required_count": required_count,
            "recommended_count": recommended_count,
            "review_first_count": len(review_first),
            "confidence_counts": confidence_counts,
        },
        "proof_recommendations": recommendations,
        "review_first_items": review_first,
        "rules": {
            "manual_only": True,
            "no_auto_execution": True,
            "no_dependency_install": True,
            "no_target_repo_mutation": True,
        },
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "authority_boundary": _authority_boundary(),
    }


def write_proof_recommendations_artifact(
    *,
    repo_root: str | Path = ".",
    surface_json: str | Path | None = None,
    out: str | Path = "build/sdetkit/adoption-proof-recommendations.json",
) -> dict[str, Any]:
    surface_payload: dict[str, Any] | None = None
    if surface_json:
        loaded = json.loads(Path(surface_json).read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("surface_json must contain a JSON object")
        surface_payload = loaded

    payload = build_proof_recommendations_payload(
        repo_root,
        surface_payload=surface_payload,
    )
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def render_proof_recommendations_text(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "adoption_proof_recommendations_status=generated",
        f"recommended_next_action={summary['recommended_next_action']}",
        f"first_manual_command={summary['first_manual_command']}",
        f"required_count={summary['required_count']}",
        f"recommended_count={summary['recommended_count']}",
        f"review_first_count={summary['review_first_count']}",
        "confidence_counts="
        + ",".join(
            f"{confidence}:{summary['confidence_counts'][confidence]}"
            for confidence in ("high", "medium", "low", "unknown")
        ),
        "proof_recommendations:",
    ]

    for item in payload["proof_recommendations"]:
        working_directory = str(item.get("working_directory", "")).strip()
        scope = f"; working_directory={working_directory}" if working_directory else ""
        lines.append(
            "- "
            f"level={item['operator_level']}; "
            f"surface={item['surface']}; "
            f"purpose={item['purpose']}; "
            f"confidence={item['confidence']}; "
            f"manual_only={str(item['manual_execution_required']).lower()}; "
            f"auto_run_allowed={str(item['auto_run_allowed']).lower()}"
            f"{scope}; "
            f"command={item['command']}"
        )

    lines.append("review_first_items:")
    review_first_items = payload["review_first_items"]
    if review_first_items:
        for item in review_first_items:
            lines.append(f"- {item['description']}")
    else:
        lines.append("- none")

    lines.append("authority_boundary:")
    boundary = payload["authority_boundary"]
    lines.extend(f"- {field}={str(boundary[field]).lower()}" for field in AUTHORITY_FIELDS)
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit adoption-proof-recommendations",
        description="Classify adoption-surface proof commands for operator review.",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--surface-json", default="")
    parser.add_argument("--out", default="build/sdetkit/adoption-proof-recommendations.json")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    payload = write_proof_recommendations_artifact(
        repo_root=ns.root,
        surface_json=ns.surface_json or None,
        out=ns.out,
    )

    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_proof_recommendations_text(payload) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
