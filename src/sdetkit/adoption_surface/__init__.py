from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from sdetkit.adoption_surface import core as _core
from sdetkit.adoption_surface.core import (
    REQUIRED_FALSE_FIELDS,
    REQUIRED_LIST_FIELDS,
    REQUIRED_OBJECT_FIELDS,
    SCHEMA_VERSION,
    render_adoption_surface_report,
    validate_adoption_surface_artifact,
    validate_adoption_surface_payload,
)

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


def _cargo_audit_evidence(root: Path) -> list[str]:
    if not _core._file(root, "Cargo.toml"):
        return []

    config_files = [
        path for path in (".cargo/audit.toml", "audit.toml") if _core._file(root, path)
    ]
    workflow_files = _core._workflow_files(root)
    script_files = _core._owned_script_files(root)
    command_files = sorted(
        set(
            _core._files_containing(root, workflow_files, "cargo audit")
            + _core._files_containing(root, script_files, "cargo audit")
            + _core._files_containing(root, workflow_files, "cargo-audit")
            + _core._files_containing(root, script_files, "cargo-audit")
        )
    )
    return sorted(set(config_files + command_files))


def discover_adoption_surface(repo_root: str | Path = ".") -> dict[str, Any]:
    payload = _core.discover_adoption_surface(repo_root)
    evidence = _cargo_audit_evidence(Path(repo_root))
    if not evidence:
        return payload

    _core._add_named(
        payload["security_tools"],
        "cargo_audit",
        confidence="detected",
        evidence=evidence,
    )
    _core._add_proof_command(
        payload["recommended_proof_commands"],
        surface="rust",
        command="cargo audit",
        confidence="medium",
        purpose="security",
        evidence=evidence,
    )
    payload["security_tools"] = sorted(
        payload["security_tools"], key=lambda item: item["name"]
    )
    payload["recommended_proof_commands"] = sorted(
        payload["recommended_proof_commands"],
        key=lambda item: (item["surface"], item["command"]),
    )
    return payload


def write_adoption_surface_artifact(
    *,
    repo_root: str | Path = ".",
    out: str | Path = "build/sdetkit/adoption-surface.json",
) -> dict[str, Any]:
    payload = discover_adoption_surface(repo_root)
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
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
        payload = json.loads(
            Path(summary["adoption_surface_json"]).read_text(encoding="utf-8")
        )
        sys.stdout.write(render_adoption_surface_report(payload) + "\n")
    else:
        sys.stdout.write(f"adoption_surface_json={summary['adoption_surface_json']}\n")
        sys.stdout.write(
            f"automation_allowed={str(summary['automation_allowed']).lower()}\n"
        )
        sys.stdout.write(
            f"patch_application_allowed={str(summary['patch_application_allowed']).lower()}\n"
        )
        sys.stdout.write(
            f"merge_authorized={str(summary['merge_authorized']).lower()}\n"
        )
        sys.stdout.write(
            f"semantic_equivalence_proven={str(summary['semantic_equivalence_proven']).lower()}\n"
        )
    return 0
