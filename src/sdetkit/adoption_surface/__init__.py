from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from sdetkit.adoption_surface import _base
from sdetkit.adoption_surface import core as _core
from sdetkit.adoption_surface.circleci import extend_circleci
from sdetkit.adoption_surface.cpp import extend_cpp
from sdetkit.adoption_surface.cpp_quality_security import extend_cpp_quality_security
from sdetkit.adoption_surface.java_security import extend_java_dependency_security
from sdetkit.adoption_surface.java_workspaces import (
    extend_dotnet_workspaces,
    extend_nested_java_workspaces,
)
from sdetkit.adoption_surface.javascript_security import (
    extend_javascript_package_security,
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

_PYTHON_TEST_UNKNOWN = "Python project detected but test command is not proven"


def _src_contains_python_sources(root: Path) -> bool:
    src_root = root / "src"
    if not src_root.is_dir():
        return False
    return bool(_core._recursive_files_for_patterns(src_root, ("*.py", "*.pyi")))


def _refine_python_src_evidence(payload: dict[str, Any], root: Path) -> None:
    if _src_contains_python_sources(root):
        return

    languages = payload.get("detected_languages")
    if not isinstance(languages, list):
        return

    for index, item in enumerate(languages):
        if not isinstance(item, dict) or item.get("name") != "python":
            continue
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or "src/" not in evidence:
            return

        filtered = sorted({str(value) for value in evidence if str(value) != "src/"})
        if filtered:
            item["evidence"] = filtered
            return

        del languages[index]
        unknowns = payload.get("review_first_unknowns")
        if isinstance(unknowns, list):
            payload["review_first_unknowns"] = [
                value for value in unknowns if value != _PYTHON_TEST_UNKNOWN
            ]
        return


def discover_adoption_surface(repo_root: str | Path = ".") -> dict[str, Any]:
    root = Path(repo_root)
    payload = _base.discover_adoption_surface(root)
    _refine_python_src_evidence(payload, root)
    extend_cpp(payload, root)
    extend_cpp_quality_security(payload, root)
    extend_circleci(payload, root)
    extend_javascript_package_security(payload, root)
    extend_nested_java_workspaces(payload, root)
    extend_java_dependency_security(payload, root)
    extend_dotnet_workspaces(payload, root)

    for field in (
        "detected_languages",
        "package_managers",
        "test_runners",
        "security_tools",
        "artifact_surfaces",
    ):
        payload[field] = sorted(payload[field], key=lambda item: item["name"])
    payload["ci_systems"] = sorted(payload["ci_systems"], key=lambda item: item["name"])
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
