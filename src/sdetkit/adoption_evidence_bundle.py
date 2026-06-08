from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .adoption_learning import build_adoption_learning_payload
from .adoption_proof_recommendations import build_proof_recommendations_payload
from .adoption_repo_topology import build_repo_topology_payload
from .adoption_surface import discover_adoption_surface, validate_adoption_surface_payload

SCHEMA_VERSION = "sdetkit.adoption_evidence_bundle.v1"

AUTHORITY_FIELDS = (
    "automation_allowed",
    "patch_application_allowed",
    "merge_authorized",
    "semantic_equivalence_proven",
)


def _authority_boundary() -> dict[str, bool]:
    return {field: False for field in AUTHORITY_FIELDS}


def _load_json_object(path: str | Path | None) -> dict[str, Any] | None:
    if not path:
        return None
    loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return loaded


def _component_schema(payload: dict[str, Any] | None) -> str:
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("schema_version", ""))


def _review_first_count(proof_payload: dict[str, Any]) -> int:
    summary = proof_payload.get("summary", {})
    if not isinstance(summary, dict):
        return 0
    return int(summary.get("review_first_count", 0))


def _manual_step_count(topology_payload: dict[str, Any]) -> int:
    steps = topology_payload.get("manual_proof_sequence", [])
    if not isinstance(steps, list):
        return 0
    return len(steps)


def _learning_next_upgrade(learning_payload: dict[str, Any]) -> str:
    return str(learning_payload.get("recommended_next_upgrade", ""))


def _learning_gaps(learning_payload: dict[str, Any]) -> list[str]:
    gaps = learning_payload.get("learning_gaps", [])
    if not isinstance(gaps, list):
        return []
    return [str(item) for item in gaps]


def build_adoption_evidence_bundle_payload(
    repo_root: str | Path = ".",
    *,
    surface_payload: dict[str, Any] | None = None,
    proof_payload: dict[str, Any] | None = None,
    topology_payload: dict[str, Any] | None = None,
    learning_payload: dict[str, Any] | None = None,
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
    topology = (
        topology_payload
        if topology_payload is not None
        else build_repo_topology_payload(
            repo_root,
            surface_payload=surface,
            proof_payload=proof,
        )
    )
    learning = (
        learning_payload
        if learning_payload is not None
        else build_adoption_learning_payload(Path(repo_root))
    )

    review_first_count = _review_first_count(proof)
    manual_step_count = _manual_step_count(topology)
    next_upgrade = _learning_next_upgrade(learning)

    return {
        "schema_version": SCHEMA_VERSION,
        "bundle_status": "adoption_evidence_bundle_generated",
        "repo_identity": surface.get("repo_identity", {}),
        "components": {
            "surface_profile": {
                "present": True,
                "schema_version": _component_schema(surface),
            },
            "proof_recommendations": {
                "present": True,
                "schema_version": _component_schema(proof),
            },
            "repo_topology": {
                "present": True,
                "schema_version": _component_schema(topology),
            },
            "learning": {
                "present": True,
                "schema_version": _component_schema(learning),
            },
        },
        "operator_summary": {
            "status": "ready_for_human_review",
            "review_first_count": review_first_count,
            "manual_proof_step_count": manual_step_count,
            "recommended_next_upgrade": next_upgrade,
            "next_action": (
                "Review bundled evidence, resolve review-first unknowns, then run the "
                "manual proof sequence outside automation."
            ),
        },
        "evidence": {
            "surface": {
                "repo_identity": surface.get("repo_identity", {}),
                "detected_languages": surface.get("detected_languages", []),
                "package_managers": surface.get("package_managers", []),
                "test_runners": surface.get("test_runners", []),
                "ci_systems": surface.get("ci_systems", []),
                "security_tools": surface.get("security_tools", []),
                "review_first_unknowns": surface.get("review_first_unknowns", []),
            },
            "proof_recommendations": {
                "summary": proof.get("summary", {}),
                "proof_recommendations": proof.get("proof_recommendations", []),
                "review_first_items": proof.get("review_first_items", []),
            },
            "repo_topology": {
                "topology": topology.get("topology", {}),
                "manual_proof_sequence": topology.get("manual_proof_sequence", []),
                "operator_summary": topology.get("operator_summary", {}),
            },
            "learning": {
                "target": learning.get("target", ""),
                "recommended_next_upgrade": next_upgrade,
                "learning_gaps": _learning_gaps(learning),
            },
        },
        "rules": {
            "bundle_only": True,
            "read_only": True,
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


def write_adoption_evidence_bundle_artifact(
    *,
    repo_root: str | Path = ".",
    surface_json: str | Path | None = None,
    proof_json: str | Path | None = None,
    topology_json: str | Path | None = None,
    learning_json: str | Path | None = None,
    out: str | Path = "build/sdetkit/adoption-evidence-bundle.json",
) -> dict[str, Any]:
    payload = build_adoption_evidence_bundle_payload(
        repo_root,
        surface_payload=_load_json_object(surface_json),
        proof_payload=_load_json_object(proof_json),
        topology_payload=_load_json_object(topology_json),
        learning_payload=_load_json_object(learning_json),
    )
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _lines(items: list[str]) -> list[str]:
    if not items:
        return ["- none"]
    return [f"- {item}" for item in items]


def render_adoption_evidence_bundle_text(payload: dict[str, Any]) -> str:
    summary = payload["operator_summary"]
    components = payload["components"]
    evidence = payload["evidence"]
    learning = evidence["learning"]

    lines = [
        "adoption_evidence_bundle_status=generated",
        f"review_first_count={summary['review_first_count']}",
        f"manual_proof_step_count={summary['manual_proof_step_count']}",
        f"recommended_next_upgrade={summary['recommended_next_upgrade']}",
        "components:",
    ]

    for name, component in components.items():
        lines.append(
            "- "
            f"{name}: present={str(component['present']).lower()}; "
            f"schema_version={component['schema_version']}"
        )

    lines.extend(
        [
            "learning_gaps:",
            *_lines([str(item) for item in learning["learning_gaps"]]),
            "rules:",
        ]
    )
    rules = payload["rules"]
    lines.extend(f"- {name}={str(value).lower()}" for name, value in rules.items())

    lines.append("authority_boundary:")
    boundary = payload["authority_boundary"]
    lines.extend(f"- {field}={str(boundary[field]).lower()}" for field in AUTHORITY_FIELDS)
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit adoption-evidence-bundle",
        description="Build a read-only adoption evidence bundle for operator review.",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--surface-json", default="")
    parser.add_argument("--proof-json", default="")
    parser.add_argument("--topology-json", default="")
    parser.add_argument("--learning-json", default="")
    parser.add_argument("--out", default="build/sdetkit/adoption-evidence-bundle.json")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    payload = write_adoption_evidence_bundle_artifact(
        repo_root=ns.root,
        surface_json=ns.surface_json or None,
        proof_json=ns.proof_json or None,
        topology_json=ns.topology_json or None,
        learning_json=ns.learning_json or None,
        out=ns.out,
    )

    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_adoption_evidence_bundle_text(payload) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
