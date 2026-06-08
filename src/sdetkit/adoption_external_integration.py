from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .adoption_evidence_bundle import write_adoption_evidence_bundle_artifact
from .adoption_proof_recommendations import write_proof_recommendations_artifact
from .adoption_repo_topology import write_repo_topology_artifact
from .adoption_surface import write_adoption_surface_artifact

SCHEMA_VERSION = "sdetkit.adoption_external_integration.v1"

AUTHORITY_FIELDS = (
    "automation_allowed",
    "patch_application_allowed",
    "merge_authorized",
    "semantic_equivalence_proven",
)


def _authority_boundary() -> dict[str, bool]:
    return {field: False for field in AUTHORITY_FIELDS}


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _ensure_artifact_dir_outside_target(target_root: Path, artifact_dir: Path) -> None:
    target = target_root.resolve()
    artifact = artifact_dir.resolve()

    if artifact == target or artifact.is_relative_to(target):
        raise ValueError("artifact_dir must be outside target_root")


def run_external_integration(
    *,
    target_root: str | Path,
    artifact_dir: str | Path,
) -> dict[str, Any]:
    target = Path(target_root).resolve()
    artifact_root = Path(artifact_dir).resolve()

    if not target.is_dir():
        raise ValueError(f"target_root does not exist or is not a directory: {target}")

    _ensure_artifact_dir_outside_target(target, artifact_root)
    artifact_root.mkdir(parents=True, exist_ok=True)

    before_digest = _tree_digest(target)

    surface_json = artifact_root / "adoption-surface.json"
    proof_json = artifact_root / "adoption-proof-recommendations.json"
    topology_json = artifact_root / "adoption-repo-topology.json"
    bundle_json = artifact_root / "adoption-evidence-bundle.json"

    write_adoption_surface_artifact(repo_root=target, out=surface_json)
    write_proof_recommendations_artifact(
        repo_root=target,
        surface_json=surface_json,
        out=proof_json,
    )
    write_repo_topology_artifact(
        repo_root=target,
        surface_json=surface_json,
        proof_json=proof_json,
        out=topology_json,
    )
    write_adoption_evidence_bundle_artifact(
        repo_root=target,
        surface_json=surface_json,
        proof_json=proof_json,
        topology_json=topology_json,
        out=bundle_json,
    )

    after_digest = _tree_digest(target)
    target_tree_unchanged = before_digest == after_digest

    bundle = json.loads(bundle_json.read_text(encoding="utf-8"))
    surface = json.loads(surface_json.read_text(encoding="utf-8"))

    return {
        "schema_version": SCHEMA_VERSION,
        "integration_status": "passed" if target_tree_unchanged else "failed",
        "target_root": target.as_posix(),
        "artifact_dir": artifact_root.as_posix(),
        "repo_identity": surface.get("repo_identity", {}),
        "artifact_paths": {
            "surface_json": surface_json.as_posix(),
            "proof_recommendations_json": proof_json.as_posix(),
            "repo_topology_json": topology_json.as_posix(),
            "evidence_bundle_json": bundle_json.as_posix(),
        },
        "target_tree_unchanged": target_tree_unchanged,
        "bundle_status": bundle.get("bundle_status", ""),
        "rules": {
            "external_target_root_required": True,
            "artifacts_outside_target_root": True,
            "read_only": True,
            "manual_only": True,
            "no_dependency_install": True,
            "no_target_tests_executed": True,
            "no_target_repo_mutation": True,
            "no_target_pr_or_issue_opened": True,
            "no_endorsement_claim": True,
        },
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "authority_boundary": _authority_boundary(),
    }


def write_external_integration_artifact(
    *,
    target_root: str | Path,
    artifact_dir: str | Path,
    out: str | Path | None = None,
) -> dict[str, Any]:
    payload = run_external_integration(target_root=target_root, artifact_dir=artifact_dir)
    out_path = Path(out) if out else Path(artifact_dir) / "adoption-external-integration.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def render_external_integration_text(payload: dict[str, Any]) -> str:
    lines = [
        f"adoption_external_integration_status={payload['integration_status']}",
        f"target_root={payload['target_root']}",
        f"artifact_dir={payload['artifact_dir']}",
        f"target_tree_unchanged={str(payload['target_tree_unchanged']).lower()}",
        f"bundle_status={payload['bundle_status']}",
        "rules:",
    ]

    rules = payload["rules"]
    lines.extend(f"- {name}={str(value).lower()}" for name, value in rules.items())

    lines.append("authority_boundary:")
    boundary = payload["authority_boundary"]
    lines.extend(f"- {field}={str(boundary[field]).lower()}" for field in AUTHORITY_FIELDS)
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit adoption-external-integration",
        description="Run the read-only adoption artifact stack against an external target root.",
    )
    parser.add_argument("--target-root", required=True)
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--out", default="")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    payload = write_external_integration_artifact(
        target_root=ns.target_root,
        artifact_dir=ns.artifact_dir,
        out=ns.out or None,
    )

    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_external_integration_text(payload) + "\n")

    if not payload["target_tree_unchanged"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
