from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .adoption_proof_recommendations import build_proof_recommendations_payload
from .adoption_surface import discover_adoption_surface, validate_adoption_surface_payload

SCHEMA_VERSION = "sdetkit.adoption_repo_topology.v1"

AUTHORITY_FIELDS = (
    "automation_allowed",
    "patch_application_allowed",
    "merge_authorized",
    "semantic_equivalence_proven",
)


def _authority_boundary() -> dict[str, bool]:
    return {field: False for field in AUTHORITY_FIELDS}


def _names(items: object) -> list[str]:
    if not isinstance(items, list):
        return []
    names: list[str] = []
    for item in items:
        if isinstance(item, dict):
            names.append(str(item.get("name", "unknown")))
    return names


def _commands(proof_payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = proof_payload.get("proof_recommendations", [])
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _section_lines(items: list[str]) -> list[str]:
    if not items:
        return ["- none"]
    return [f"- {item}" for item in items]


def _manual_sequence(proof_payload: dict[str, Any]) -> list[dict[str, Any]]:
    order = {"review_first": 0, "required": 1, "recommended": 2}
    commands = sorted(
        _commands(proof_payload),
        key=lambda item: (
            order.get(str(item.get("operator_level", "review_first")), 9),
            int(item.get("index", 999)),
        ),
    )
    return [
        {
            "step": index,
            "operator_level": str(item.get("operator_level", "review_first")),
            "surface": str(item.get("surface", "unknown")),
            "purpose": str(item.get("purpose", "unknown")),
            "command": str(item.get("command", "")),
            "manual_only": True,
            "auto_run_allowed": False,
        }
        for index, item in enumerate(commands, start=1)
    ]


def build_repo_topology_payload(
    repo_root: str | Path = ".",
    *,
    surface_payload: dict[str, Any] | None = None,
    proof_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    surface = (
        surface_payload if surface_payload is not None else discover_adoption_surface(repo_root)
    )
    errors = validate_adoption_surface_payload(surface)
    if errors:
        raise ValueError("invalid adoption surface payload: " + "; ".join(errors))

    proof = (
        proof_payload
        if proof_payload is not None
        else build_proof_recommendations_payload(repo_root, surface_payload=surface)
    )

    unknowns = surface.get("review_first_unknowns", [])
    if not isinstance(unknowns, list):
        unknowns = []

    topology = {
        "languages": _names(surface.get("detected_languages")),
        "package_managers": _names(surface.get("package_managers")),
        "test_runners": _names(surface.get("test_runners")),
        "ci_systems": _names(surface.get("ci_systems")),
        "security_tools": _names(surface.get("security_tools")),
        "artifact_surfaces": _names(surface.get("artifact_surfaces")),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "repo_identity": surface.get("repo_identity", {}),
        "topology": topology,
        "review_first_unknowns": [str(item) for item in unknowns],
        "manual_proof_sequence": _manual_sequence(proof),
        "operator_summary": {
            "status": "repo_topology_summarized",
            "primary_language": topology["languages"][0] if topology["languages"] else "unknown",
            "has_ci": bool(topology["ci_systems"]),
            "has_review_first_unknowns": bool(unknowns),
            "next_action": "Review topology, resolve review-first unknowns, then run manual proof sequence.",
        },
        "rules": {
            "summary_only": True,
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


def write_repo_topology_artifact(
    *,
    repo_root: str | Path = ".",
    surface_json: str | Path | None = None,
    proof_json: str | Path | None = None,
    out: str | Path = "build/sdetkit/adoption-repo-topology.json",
) -> dict[str, Any]:
    surface_payload: dict[str, Any] | None = None
    proof_payload: dict[str, Any] | None = None

    if surface_json:
        loaded = json.loads(Path(surface_json).read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("surface_json must contain a JSON object")
        surface_payload = loaded

    if proof_json:
        loaded = json.loads(Path(proof_json).read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("proof_json must contain a JSON object")
        proof_payload = loaded

    payload = build_repo_topology_payload(
        repo_root,
        surface_payload=surface_payload,
        proof_payload=proof_payload,
    )
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def render_repo_topology_text(payload: dict[str, Any]) -> str:
    topology = payload["topology"]
    summary = payload["operator_summary"]

    lines = [
        "adoption_repo_topology_status=summarized",
        f"primary_language={summary['primary_language']}",
        f"has_ci={str(summary['has_ci']).lower()}",
        f"has_review_first_unknowns={str(summary['has_review_first_unknowns']).lower()}",
        "languages:",
        *_section_lines(topology["languages"]),
        "package_managers:",
        *_section_lines(topology["package_managers"]),
        "test_runners:",
        *_section_lines(topology["test_runners"]),
        "ci_systems:",
        *_section_lines(topology["ci_systems"]),
        "security_tools:",
        *_section_lines(topology["security_tools"]),
        "review_first_unknowns:",
    ]

    unknowns = payload["review_first_unknowns"]
    if unknowns:
        lines.extend(f"- {item}" for item in unknowns)
    else:
        lines.append("- none")

    lines.append("manual_proof_sequence:")
    sequence = payload["manual_proof_sequence"]
    if sequence:
        for item in sequence:
            lines.append(
                "- "
                f"step={item['step']}; "
                f"level={item['operator_level']}; "
                f"surface={item['surface']}; "
                f"manual_only={str(item['manual_only']).lower()}; "
                f"auto_run_allowed={str(item['auto_run_allowed']).lower()}; "
                f"command={item['command']}"
            )
    else:
        lines.append("- none")

    lines.append("authority_boundary:")
    boundary = payload["authority_boundary"]
    lines.extend(f"- {field}={str(boundary[field]).lower()}" for field in AUTHORITY_FIELDS)
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit adoption-repo-topology",
        description="Summarize adoption repo topology for operator planning.",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--surface-json", default="")
    parser.add_argument("--proof-json", default="")
    parser.add_argument("--out", default="build/sdetkit/adoption-repo-topology.json")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    payload = write_repo_topology_artifact(
        repo_root=ns.root,
        surface_json=ns.surface_json or None,
        proof_json=ns.proof_json or None,
        out=ns.out,
    )

    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_repo_topology_text(payload) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
