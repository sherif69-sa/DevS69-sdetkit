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
    validate_adoption_surface_artifact,
    validate_adoption_surface_payload,
)
from sdetkit.adoption_surface.jenkins import extract_jenkins_pipeline

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

_WORKSPACE_IGNORED_TOP_LEVEL = {
    ".github",
    "build",
    "dist",
    "docs",
    "examples",
    "site",
    "templates",
    "test",
    "tests",
}


def _cargo_audit_evidence(root: Path) -> list[str]:
    if not _core._file(root, "Cargo.toml"):
        return []

    config_files = [path for path in (".cargo/audit.toml", "audit.toml") if _core._file(root, path)]
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


def _jenkins_context(stage: str) -> str:
    return f"stage {stage}" if stage else "pipeline"


def _nested_owned_files(root: Path, pattern: str) -> list[str]:
    return [
        path
        for path in _core._recursive_files(root, pattern)
        if "/" in path and Path(path).parts[0] not in _WORKSPACE_IGNORED_TOP_LEVEL
    ]


def _workspace_directory(path: str) -> str:
    return Path(path).parent.as_posix()


def _workspace_path(workspace: str, name: str) -> str:
    return f"{workspace}/{name}" if workspace != "." else name


def _merge_named_list(
    items: list[dict[str, Any]],
    name: str,
    *,
    list_field: str,
    values: Sequence[str],
    **fields: Any,
) -> None:
    normalized = sorted(set(values))
    existing = next((item for item in items if item.get("name") == name), None)
    if existing is None:
        items.append({"name": name, list_field: normalized, **fields})
        return

    current = existing.get(list_field, [])
    current_values = [str(value) for value in current] if isinstance(current, list) else []
    existing[list_field] = sorted(set(current_values + normalized))
    for key, value in fields.items():
        existing.setdefault(key, value)


def _workspace_source(*, file: str, working_directory: str) -> dict[str, str]:
    return {
        "scope": "nested_workspace",
        "file": file,
        "working_directory": working_directory,
    }


def _add_workspace_proof_command(
    items: list[dict[str, Any]],
    *,
    surface: str,
    command: str,
    confidence: str,
    purpose: str,
    file: str,
    working_directory: str,
) -> None:
    for existing in items:
        source = existing.get("source")
        existing_directory = (
            str(source.get("working_directory", "")) if isinstance(source, dict) else ""
        )
        if (
            existing.get("surface") == surface
            and existing.get("command") == command
            and existing_directory == working_directory
        ):
            return

    items.append(
        {
            "surface": surface,
            "command": command,
            "confidence": confidence,
            "purpose": purpose,
            "executes_untrusted_code": True,
            "auto_run_allowed": False,
            "evidence": [file],
            "source": _workspace_source(file=file, working_directory=working_directory),
        }
    )


def _extend_nested_python_workspaces(payload: dict[str, Any], root: Path) -> None:
    manifests = _nested_owned_files(root, "pyproject.toml")
    requirements = _nested_owned_files(root, "requirements*.txt")
    workspace_files: dict[str, list[str]] = {}
    for path in [*manifests, *requirements]:
        workspace_files.setdefault(_workspace_directory(path), []).append(path)

    if not workspace_files:
        return

    evidence = sorted({path for paths in workspace_files.values() for path in paths})
    _merge_named_list(
        payload["detected_languages"],
        "python",
        list_field="evidence",
        values=evidence,
        confidence="high",
    )

    pip_files = sorted(path for path in requirements)
    uv_files = [
        _workspace_path(workspace, "uv.lock")
        for workspace in workspace_files
        if _core._file(root, _workspace_path(workspace, "uv.lock"))
    ]
    poetry_files = [
        _workspace_path(workspace, "poetry.lock")
        for workspace in workspace_files
        if _core._file(root, _workspace_path(workspace, "poetry.lock"))
    ]
    if pip_files:
        _merge_named_list(payload["package_managers"], "pip", list_field="files", values=pip_files)
    if uv_files:
        _merge_named_list(payload["package_managers"], "uv", list_field="files", values=uv_files)
    if poetry_files:
        _merge_named_list(
            payload["package_managers"], "poetry", list_field="files", values=poetry_files
        )

    for workspace, files in sorted(workspace_files.items()):
        proof_file = next((path for path in files if path.endswith("pyproject.toml")), files[0])
        text = "\n".join(_core._read_text(root, path) for path in files).lower()
        if "pytest" not in text:
            payload["review_first_unknowns"].append(
                f"Python workspace {workspace} detected but test command is not proven"
            )
            continue

        command = "python -m pytest -q -o addopts="
        _merge_named_list(
            payload["test_runners"],
            "pytest",
            list_field="commands",
            values=[command],
            confidence="high",
        )
        _add_workspace_proof_command(
            payload["recommended_proof_commands"],
            surface="python",
            command=command,
            confidence="high",
            purpose="test",
            file=proof_file,
            working_directory=workspace,
        )


def _node_workspace_command(root: Path, workspace: str) -> tuple[str, list[str]]:
    lockfiles = [
        name
        for name in ("pnpm-lock.yaml", "yarn.lock", "package-lock.json")
        if _core._file(root, _workspace_path(workspace, name))
    ]
    if "pnpm-lock.yaml" in lockfiles:
        return "pnpm test", lockfiles
    if "yarn.lock" in lockfiles:
        return "yarn test", lockfiles
    return "npm test", lockfiles


def _extend_nested_node_workspaces(payload: dict[str, Any], root: Path) -> None:
    manifests = _nested_owned_files(root, "package.json")
    if not manifests:
        return

    evidence: list[str] = []
    manager_files: dict[str, list[str]] = {"npm": [], "pnpm": [], "yarn": []}
    for manifest in manifests:
        workspace = _workspace_directory(manifest)
        command, lockfiles = _node_workspace_command(root, workspace)
        workspace_lockfiles = [_workspace_path(workspace, name) for name in lockfiles]
        evidence.extend([manifest, *workspace_lockfiles])
        if command.startswith("pnpm"):
            manager_files["pnpm"].extend(workspace_lockfiles)
        elif command.startswith("yarn"):
            manager_files["yarn"].extend(workspace_lockfiles)
        elif workspace_lockfiles:
            manager_files["npm"].extend(workspace_lockfiles)

        scripts = _core._read_json(root, manifest).get("scripts")
        has_test = isinstance(scripts, dict) and bool(str(scripts.get("test", "")).strip())
        if not has_test:
            payload["review_first_unknowns"].append(
                f"JavaScript/TypeScript workspace {workspace} detected but test command is not proven"
            )
            continue

        _merge_named_list(
            payload["test_runners"],
            "node_test_script",
            list_field="commands",
            values=[command],
            confidence="medium",
        )
        _add_workspace_proof_command(
            payload["recommended_proof_commands"],
            surface="javascript_typescript",
            command=command,
            confidence="medium",
            purpose="test",
            file=manifest,
            working_directory=workspace,
        )

    _merge_named_list(
        payload["detected_languages"],
        "javascript_typescript",
        list_field="evidence",
        values=evidence,
        confidence="medium",
    )
    for manager, files in manager_files.items():
        if files:
            _merge_named_list(
                payload["package_managers"], manager, list_field="files", values=files
            )


def _nested_rust_audit_evidence(root: Path, workspace: str) -> list[str]:
    return [
        _workspace_path(workspace, path)
        for path in (".cargo/audit.toml", "audit.toml")
        if _core._file(root, _workspace_path(workspace, path))
    ]


def _extend_nested_rust_workspaces(payload: dict[str, Any], root: Path) -> None:
    manifests = _nested_owned_files(root, "Cargo.toml")
    if not manifests:
        return

    cargo_files: list[str] = []
    for manifest in manifests:
        workspace = _workspace_directory(manifest)
        workspace_files = [manifest]
        lockfile = _workspace_path(workspace, "Cargo.lock")
        if _core._file(root, lockfile):
            workspace_files.append(lockfile)
        cargo_files.extend(workspace_files)

        _merge_named_list(
            payload["test_runners"],
            "cargo_test",
            list_field="commands",
            values=["cargo test"],
            confidence="high",
        )
        _add_workspace_proof_command(
            payload["recommended_proof_commands"],
            surface="rust",
            command="cargo test",
            confidence="high",
            purpose="test",
            file=manifest,
            working_directory=workspace,
        )

        audit_evidence = _nested_rust_audit_evidence(root, workspace)
        if not audit_evidence:
            continue
        _merge_named_list(
            payload["security_tools"],
            "cargo_audit",
            list_field="evidence",
            values=audit_evidence,
            confidence="detected",
        )
        _add_workspace_proof_command(
            payload["recommended_proof_commands"],
            surface="rust",
            command="cargo audit",
            confidence="medium",
            purpose="security",
            file=audit_evidence[0],
            working_directory=workspace,
        )

    _merge_named_list(
        payload["detected_languages"],
        "rust",
        list_field="evidence",
        values=cargo_files,
        confidence="high",
    )
    _merge_named_list(
        payload["package_managers"],
        "cargo",
        list_field="files",
        values=cargo_files,
    )


def _nested_go_security_evidence(root: Path, workspace: str) -> list[str]:
    workspace_root = root / workspace
    named_files = [
        _workspace_path(workspace, path)
        for path in ("Makefile", "Taskfile.yml", "Taskfile.yaml", "justfile", "Justfile")
        if _core._file(root, _workspace_path(workspace, path))
    ]
    script_files = [
        _workspace_path(workspace, path)
        for path in _core._recursive_files(workspace_root, "*.sh")
    ]
    workflow_files = [
        _workspace_path(workspace, path)
        for path in (
            *_core._glob_files(workspace_root, ".github/workflows/*.yml"),
            *_core._glob_files(workspace_root, ".github/workflows/*.yaml"),
        )
    ]
    candidates = sorted(set(named_files + script_files + workflow_files))
    return _core._files_containing(root, candidates, "govulncheck")


def _extend_nested_go_workspaces(payload: dict[str, Any], root: Path) -> None:
    manifests = _nested_owned_files(root, "go.mod")
    if not manifests:
        return

    go_files: list[str] = []
    for manifest in manifests:
        workspace = _workspace_directory(manifest)
        workspace_files = [manifest]
        checksum = _workspace_path(workspace, "go.sum")
        if _core._file(root, checksum):
            workspace_files.append(checksum)
        go_files.extend(workspace_files)

        _merge_named_list(
            payload["test_runners"],
            "go_test",
            list_field="commands",
            values=["go test ./..."],
            confidence="high",
        )
        _add_workspace_proof_command(
            payload["recommended_proof_commands"],
            surface="go",
            command="go test ./...",
            confidence="high",
            purpose="test",
            file=manifest,
            working_directory=workspace,
        )

        security_evidence = _nested_go_security_evidence(root, workspace)
        if not security_evidence:
            continue
        _merge_named_list(
            payload["security_tools"],
            "govulncheck",
            list_field="evidence",
            values=security_evidence,
            confidence="detected",
        )
        _add_workspace_proof_command(
            payload["recommended_proof_commands"],
            surface="go",
            command="govulncheck ./...",
            confidence="medium",
            purpose="security",
            file=security_evidence[0],
            working_directory=workspace,
        )

    _merge_named_list(
        payload["detected_languages"],
        "go",
        list_field="evidence",
        values=go_files,
        confidence="high",
    )
    _merge_named_list(
        payload["package_managers"],
        "go_modules",
        list_field="files",
        values=go_files,
    )


def _extend_nested_workspaces(payload: dict[str, Any], root: Path) -> None:
    _extend_nested_python_workspaces(payload, root)
    _extend_nested_node_workspaces(payload, root)
    _extend_nested_go_workspaces(payload, root)
    _extend_nested_rust_workspaces(payload, root)


def _extend_jenkins_pipeline(payload: dict[str, Any], root: Path) -> None:
    extracted, unknowns = extract_jenkins_pipeline(root)
    payload["review_first_unknowns"].extend(unknowns)

    for item in extracted:
        command = str(item.get("command", "")).strip()
        stage = str(item.get("stage", "")).strip()
        if not command or _core._command_is_shell_message(command):
            continue
        if _core._command_is_dynamic(command):
            payload["review_first_unknowns"].append(
                f"Jenkins {_jenkins_context(stage)} has dynamic shell command that was not guessed"
            )
            continue

        source: dict[str, Any] = {
            "ci_system": "jenkins",
            "file": str(item.get("file", "Jenkinsfile")),
        }
        if stage:
            source["stage"] = stage
        _core._add_proof_command(
            payload["recommended_proof_commands"],
            surface="jenkins",
            command=command,
            confidence="medium",
            purpose=_core._classify_proof_purpose(command),
            evidence=[str(item.get("file", "Jenkinsfile"))],
            source=source,
        )


def _extend_cargo_audit(payload: dict[str, Any], root: Path) -> None:
    evidence = _cargo_audit_evidence(root)
    if not evidence:
        return

    _merge_named_list(
        payload["security_tools"],
        "cargo_audit",
        list_field="evidence",
        values=evidence,
        confidence="detected",
    )
    _core._add_proof_command(
        payload["recommended_proof_commands"],
        surface="rust",
        command="cargo audit",
        confidence="medium",
        purpose="security",
        evidence=evidence,
    )


def _proof_sort_key(item: dict[str, Any]) -> tuple[str, str, str, str]:
    source = item.get("source")
    source_payload = source if isinstance(source, dict) else {}
    return (
        str(item.get("surface", "")),
        str(item.get("command", "")),
        str(source_payload.get("working_directory", "")),
        str(source_payload.get("file", "")),
    )


def discover_adoption_surface(repo_root: str | Path = ".") -> dict[str, Any]:
    root = Path(repo_root)
    payload = _core.discover_adoption_surface(root)
    _extend_cargo_audit(payload, root)
    _extend_nested_workspaces(payload, root)
    _extend_jenkins_pipeline(payload, root)

    for field in ("detected_languages", "package_managers", "test_runners", "security_tools"):
        payload[field] = sorted(payload[field], key=lambda item: item["name"])
    payload["recommended_proof_commands"] = sorted(
        payload["recommended_proof_commands"], key=_proof_sort_key
    )
    payload["review_first_unknowns"] = sorted(set(payload["review_first_unknowns"]))
    return payload


def _format_scoped_proof_commands(items: object) -> list[str]:
    if not isinstance(items, list) or not items:
        return ["- none recommended"]

    lines: list[str] = []
    for item in items:
        if not isinstance(item, dict) or not str(item.get("command", "")).strip():
            continue
        source = item.get("source")
        source_payload = source if isinstance(source, dict) else {}
        working_directory = str(source_payload.get("working_directory", "")).strip()
        scope = f"; working_directory={working_directory}" if working_directory else ""
        lines.append(
            f"- `{item['command']}` - surface={item.get('surface', 'unknown')}; "
            f"purpose={item.get('purpose', 'unknown')}{scope}; "
            f"auto_run_allowed={str(item.get('auto_run_allowed', False)).lower()}"
        )
    return lines or ["- none recommended"]


def render_adoption_surface_report(payload: dict[str, Any]) -> str:
    lines = _core.render_adoption_surface_report(payload).splitlines()
    start = lines.index("## Recommended proof commands") + 1
    end = lines.index("## Review-first unknowns")
    lines[start:end] = [
        *_format_scoped_proof_commands(payload.get("recommended_proof_commands")),
        "",
    ]
    return "\n".join(lines)


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
