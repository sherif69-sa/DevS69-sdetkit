from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from sdetkit.adoption_surface import _base
from sdetkit.adoption_surface.java_workspaces import (
    extend_dotnet_workspaces,
    extend_nested_java_workspaces,
)

REQUIRED_FALSE_FIELDS = _base.REQUIRED_FALSE_FIELDS
REQUIRED_LIST_FIELDS = _base.REQUIRED_LIST_FIELDS
REQUIRED_OBJECT_FIELDS = _base.REQUIRED_OBJECT_FIELDS
SCHEMA_VERSION = _base.SCHEMA_VERSION
validate_adoption_surface_artifact = _base.validate_adoption_surface_artifact
validate_adoption_surface_payload = _base.validate_adoption_surface_payload
render_adoption_surface_report = _base.render_adoption_surface_report

__all__ = (
    "REQUIRED_FALSE_FIELDS",
    "REQUIRED_LIST_FIELDS",
    "REQUIRED_OBJECT_FIELDS",
    "SCHEMA_VERSION",
    "discover_adoption_surface",
    "main",
    "render_adoption_surface_report",
    "validate_adoption_surface_artifact",
    "validate_adoption_surface_payload",
    "write_adoption_surface_artifact",
)


def discover_adoption_surface(repo_root: str | Path = ".") -> dict[str, Any]:
    root = Path(repo_root)
    payload = _base.discover_adoption_surface(root)
    extend_nested_java_workspaces(payload, root)
    extend_dotnet_workspaces(payload, root)

    for field in ("detected_languages", "package_managers", "test_runners", "security_tools"):
        payload[field] = sorted(payload[field], key=lambda item: item["name"])
    payload["recommended_proof_commands"] = sorted(
        payload["recommended_proof_commands"], key=_base._proof_sort_key
    )
    payload["review_first_unknowns"] = sorted(set(payload["review_first_unknowns"]))
    return payload


def write_adoption_surface_artifact(
    *,
    repo_root: str | Path = ".",
    out: str | Path = "build/sdetkit/adoption-surface.json",
) -> dict[str, Any]:
    payload = discover_adoption_surface(repo_root)
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "schema_version": payload["schema_version"],
        "adoption_surface_json": out_path.as_posix(),
        "automation_allowed": payload["automation_allowed"],
        "patch_application_allowed": payload["patch_application_allowed"],
        "merge_authorized": payload["merge_authorized"],
        "semantic_equivalence_proven": payload["semantic_equivalence_proven"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit adoption-surface",
        description="Write a read-only adoption surface discovery artifact.",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", default="build/sdetkit/adoption-surface.json")
    parser.add_argument("--format", choices=["json", "text", "report"], default="json")
    ns = parser.parse_args(list(argv) if argv is not None else None)
    summary = write_adoption_surface_artifact(repo_root=ns.root, out=ns.out)
    if ns.format == "json":
        sys.stdout.write(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    elif ns.format == "report":
        payload = json.loads(Path(summary["adoption_surface_json"]).read_text(encoding="utf-8"))
        sys.stdout.write(render_adoption_surface_report(payload) + "\n")
    else:
        sys.stdout.write(f"adoption_surface_json={summary['adoption_surface_json']}\n")
        sys.stdout.write(f"automation_allowed={str(summary['automation_allowed']).lower()}\n")
        sys.stdout.write(
            f"patch_application_allowed={str(summary['patch_application_allowed']).lower()}\n"
        )
        sys.stdout.write(f"merge_authorized={str(summary['merge_authorized']).lower()}\n")
        sys.stdout.write(
            f"semantic_equivalence_proven={str(summary['semantic_equivalence_proven']).lower()}\n"
        )
    return 0
