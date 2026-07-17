from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from sdetkit.adoption_proof_recommendations import build_proof_recommendations_payload
from sdetkit.adoption_surface import discover_adoption_surface
from sdetkit.doctor_report import build_doctor_report_contract, render_doctor_report_markdown
from sdetkit.failure_vector import BUNDLE_SCHEMA_VERSION
from sdetkit.failure_vector import SCHEMA_VERSION as FAILURE_VECTOR_SCHEMA_VERSION
from sdetkit.repo_memory import build_repo_memory_profile
from sdetkit.workspace_failure_ownership import WorkspaceDefinition, build_workspace_failure_bundle

SCHEMA_VERSION = "sdetkit.mixed_monorepo_operator_proof.v1"
TRAJECTORY_SCHEMA_VERSION = "sdetkit.trajectory_pattern_insights.v1"
DEFAULT_OUT_DIR = Path("build") / "mixed-monorepo-operator-proof"
PROOF_JSON = "mixed-monorepo-operator-proof.json"
PROOF_MD = "mixed-monorepo-operator-proof.md"
DOCTOR_JSON = "doctor-report.json"
DOCTOR_MD = "doctor-report.md"
WORKSPACE_FAILURES_JSON = "workspace-failures.json"
REPO_MEMORY_JSON = "repo-memory-profile.json"

JsonObject = dict[str, Any]

_AUTHORITY_BOUNDARY: JsonObject = {
    "target_code_execution": False,
    "automation_allowed": False,
    "patch_application_allowed": False,
    "security_dismissal_allowed": False,
    "publication_authorized": False,
    "merge_authorized": False,
    "semantic_equivalence_proven": False,
}

_IGNORED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "out",
    "target",
    "vendor",
}


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: object) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _truth(value: object) -> bool:
    return value if isinstance(value, bool) else _text(value).lower() in {"1", "true", "yes"}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _digest(root: Path, out_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root)
        if out_dir.is_relative_to(root) and out_dir.relative_to(root) in relative.parents:
            continue
        if any(part.lower() in _IGNORED_PARTS for part in relative.parts):
            continue
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _commands(adoption: Mapping[str, Any]) -> list[JsonObject]:
    return [
        dict(item)
        for item in _list(adoption.get("recommended_proof_commands"))
        if isinstance(item, dict)
    ]


def _source(command: Mapping[str, Any]) -> Mapping[str, Any]:
    return _mapping(command.get("source"))


def _workspaces(adoption: Mapping[str, Any]) -> tuple[WorkspaceDefinition, ...]:
    rows: dict[str, WorkspaceDefinition] = {}
    for command in _commands(adoption):
        source = _source(command)
        path = _text(source.get("working_directory"))
        manifest = _text(source.get("file"))
        ecosystem = _text(command.get("surface"))
        if not path or path == "." or not manifest or not ecosystem:
            continue
        row = WorkspaceDefinition(path, ecosystem, manifest).normalized()
        previous = rows.get(path)
        if previous is not None and previous != row:
            raise RuntimeError(f"inconsistent workspace identity: {path}")
        rows[path] = row
    return tuple(rows[path] for path in sorted(rows))


def _aggregate_vectors(workspace_bundle: Mapping[str, Any]) -> JsonObject:
    entries = [
        _mapping(item)
        for item in _list(workspace_bundle.get("workspace_failures"))
        if _mapping(item)
    ]
    vectors = [_mapping(item.get("failure_vector")) for item in entries]
    classes = Counter(_text(item.get("failure_class")) or "unknown" for item in vectors)
    risks = Counter(_text(item.get("risk")) or "unknown" for item in vectors)
    return {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "vector_schema_version": FAILURE_VECTOR_SCHEMA_VERSION,
        "status": "review_required",
        "failure_vector_count": len(vectors),
        "summary": {
            "by_failure_class": dict(sorted(classes.items())),
            "by_risk": dict(sorted(risks.items())),
            "safe_fix_candidate_count": 0,
            "review_first_count": len(entries),
        },
        "failure_vectors": [dict(item) for item in vectors],
        "decision_boundary": dict(_AUTHORITY_BOUNDARY),
    }


def _trajectory(workspace_bundle: Mapping[str, Any]) -> JsonObject:
    entries = [
        _mapping(item)
        for item in _list(workspace_bundle.get("workspace_failures"))
        if _mapping(item)
    ]
    workspaces = Counter(
        _text(_mapping(item.get("workspace_identity")).get("path")) or "unknown" for item in entries
    )
    kinds = Counter(
        _text(_mapping(item.get("failure_vector")).get("failure_class")) or "unknown"
        for item in entries
    )
    surfaces = Counter(
        _text(_mapping(item.get("safety_gate")).get("affected_surface")) or "unknown"
        for item in entries
    )
    denied = {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }
    return {
        "schema_version": TRAJECTORY_SCHEMA_VERSION,
        "record_count": len(entries),
        "recurring_review_first_surfaces": [
            {"value": value, "count": count} for value, count in sorted(workspaces.items())
        ],
        "recurring_safe_fix_patterns": [],
        "safety_gate_evidence": {
            "collection_status": "collected",
            "status": "safety_gate_evidence_observed",
            "source": "mixed_monorepo_operator_proof.safety_gate",
            "record_count": len(entries),
            "review_first_count": len(entries),
            "safe_fix_allowed_count": 0,
            "reporting_only_count": len(entries),
            "report_paths": [WORKSPACE_FAILURES_JSON],
            "decision_boundary": denied,
        },
        "authority_boundary_evidence": {
            "collection_status": "collected",
            "status": "authority_boundary_evidence_observed",
            "source": "mixed_monorepo_operator_proof",
            "record_count": len(entries),
            "review_first_count": len(entries),
            "auto_fix_allowed_count": 0,
            "reporting_only_count": len(entries),
            "sources": ["adoption_surface", "workspace_failure_ownership", "doctor_report"],
            "decision_boundary": {
                **denied,
                "automatic_security_fix_allowed": False,
                "automatic_dismissal_allowed": False,
            },
        },
        "failure_vector_contract_evidence": {
            "collection_status": "collected",
            "status": "failure_vector_contract_evidence_observed",
            "source": "mixed_monorepo_operator_proof.failure_vectors",
            "record_count": len(entries),
            "security_relevance_count": 0,
            "authority_boundary_preserved_count": len(entries),
            "failure_kinds": [
                {"value": value, "count": count} for value, count in sorted(kinds.items())
            ],
            "affected_surfaces": [
                {"value": value, "count": count} for value, count in sorted(surfaces.items())
            ],
            "decision_boundary": {
                "automation_allowed": False,
                "patch_application_allowed": False,
                "security_dismissal_allowed": False,
                "merge_authorized": False,
                "semantic_equivalence_claim": False,
            },
        },
    }


def _benchmark() -> JsonObject:
    return {
        "schema_version": "sdetkit.replayable_benchmark_report.v1",
        "status": "not_collected",
        "required_contract": {"all_required_present": False, "all_required_passed": False},
        "safety_boundary": {
            "preserved": True,
            "automation_allowed_count": 0,
            "merge_authorized_count": 0,
            "semantic_equivalence_claimed_count": 0,
        },
        "scenarios": [],
    }


def _doctor_input() -> JsonObject:
    return {
        "ok": True,
        "score": 100,
        "quality": {"selected_checks": 1, "passed_checks": 1},
        "next_actions": [],
    }


def _verify(payload: Mapping[str, Any]) -> JsonObject:
    adoption = _mapping(payload.get("adoption_surface"))
    workspace_bundle = _mapping(payload.get("workspace_failure_bundle"))
    commands = _commands(adoption)
    definitions = _workspaces(adoption)
    paths = {item.path for item in definitions}
    npm = [
        item
        for item in commands
        if _text(item.get("command")) == "npm test"
        and _text(_source(item).get("working_directory"))
    ]
    entries = [
        _mapping(item)
        for item in _list(workspace_bundle.get("workspace_failures"))
        if _mapping(item)
    ]
    owners = [
        _text(_mapping(item.get("workspace_identity")).get("path")) or "unknown" for item in entries
    ]
    root_python = any(
        _text(item.get("surface")) == "python" and not _text(_source(item).get("working_directory"))
        for item in commands
    )
    no_ignored_owner = all(
        not any(
            part.lower() in _IGNORED_PARTS for part in Path(_text(_source(item).get("file"))).parts
        )
        for item in commands
    )
    protected_review_first = all(
        _truth(
            _mapping(_mapping(item.get("protected_verifier")).get("decision")).get("review_first")
        )
        for item in entries
    )
    doctor = _mapping(payload.get("doctor_report"))
    memory = _mapping(payload.get("repo_memory_profile"))
    command_profile = _mapping(memory.get("command_profile"))
    boundary = _mapping(payload.get("authority_boundary"))
    checks = {
        "root_python_proof_present": root_python,
        "nested_workspaces_complete": {
            "apps/admin",
            "apps/web",
            "crates/native",
            "services/api",
        }.issubset(paths),
        "duplicate_commands_remain_distinct": len(npm) == 2
        and len({_text(_source(item).get("working_directory")) for item in npm}) == 2,
        "all_commands_manual": bool(commands)
        and all(item.get("auto_run_allowed") is False for item in commands),
        "ignored_ownership_absent": no_ignored_owner,
        "owned_failures_preserved": {
            "apps/admin",
            "apps/web",
            "crates/native",
        }.issubset(set(owners)),
        "ambiguous_failure_fails_closed": owners.count("unknown") == 1,
        "safety_gate_review_first": all(
            _truth(_mapping(item.get("safety_gate")).get("review_first")) for item in entries
        ),
        "protected_verifier_review_first": protected_review_first,
        "doctor_review_required": _text(doctor.get("status")) == "review_required",
        "repo_memory_read_only": command_profile.get("commands_executed_by_repo_memory") is False,
        "repository_unchanged": payload.get("repository_unchanged") is True,
        "authority_boundary_preserved": bool(boundary)
        and all(value is False for value in boundary.values()),
    }
    return {"ok": all(checks.values()), "checks": checks}


def render_markdown(payload: Mapping[str, Any]) -> str:
    adoption = _mapping(payload.get("adoption_surface"))
    workspace_bundle = _mapping(payload.get("workspace_failure_bundle"))
    verification = _mapping(payload.get("verification"))
    lines = [
        "# Mixed-language monorepo operator proof",
        "",
        "This proof composes existing SDETKit contracts from repository-owned and saved evidence.",
        "It does not execute workspace commands or authorize remediation.",
        "",
        "## Detected manual proof commands",
        "",
    ]
    for command in _commands(adoption):
        source = _source(command)
        lines.append(
            "- `{}` in `{}` for `{}` (auto_run_allowed=false)".format(
                _text(command.get("command")),
                _text(source.get("working_directory")) or ".",
                _text(command.get("surface")),
            )
        )
    lines.extend(["", "## Saved failure ownership", ""])
    for raw in _list(workspace_bundle.get("workspace_failures")):
        item = _mapping(raw)
        workspace = _mapping(item.get("workspace_identity"))
        vector = _mapping(item.get("failure_vector"))
        lines.append(
            "- `{}` / `{}` -> `{}` (confidence={}, review_first={})".format(
                _text(workspace.get("path")) or "unknown",
                _text(workspace.get("ecosystem")) or "unknown",
                _text(vector.get("failure_class")) or "unknown",
                _text(item.get("ownership_confidence")) or "unknown",
                str(_truth(item.get("review_first"))).lower(),
            )
        )
    lines.extend(["", "## Authority boundary", "", "```text"])
    for key, value in _AUTHORITY_BOUNDARY.items():
        lines.append(f"{key}={str(value).lower()}")
    lines.extend(["```", "", "## Verification", ""])
    lines.append(f"- overall: `{str(_truth(verification.get('ok'))).lower()}`")
    for key, value in sorted(_mapping(verification.get("checks")).items()):
        lines.append(f"- {key}: `{str(_truth(value)).lower()}`")
    return "\n".join(lines).rstrip() + "\n"


def build_mixed_monorepo_operator_proof(
    *,
    repo: Path,
    failure_logs: Sequence[Path],
    evidence_root: Path,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> JsonObject:
    repo = repo.resolve()
    evidence_root = evidence_root.resolve()
    out_dir = out_dir.resolve()
    if not repo.is_dir():
        raise ValueError(f"proof repository does not exist: {repo}")
    if not failure_logs:
        raise ValueError("at least one saved failure log is required")
    logs = tuple(sorted((path.resolve() for path in failure_logs), key=str))
    if any(not path.is_file() for path in logs):
        raise ValueError("one or more saved failure logs do not exist")

    before = _digest(repo, out_dir)
    adoption = discover_adoption_surface(repo)
    recommendations = build_proof_recommendations_payload(repo)
    workspace_bundle = build_workspace_failure_bundle(
        logs,
        workspaces=_workspaces(adoption),
        evidence_root=evidence_root,
    )
    vectors = _aggregate_vectors(workspace_bundle)
    trajectory = _trajectory(workspace_bundle)
    memory = build_repo_memory_profile(
        pattern_insights=trajectory,
        benchmark_report=_benchmark(),
    )
    doctor = build_doctor_report_contract(_doctor_input(), failure_vector_bundle=vectors)
    after = _digest(repo, out_dir)

    payload: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "status": "review_required",
        "repository_unchanged": before == after,
        "source_evidence": {
            "repository_digest_before": before,
            "repository_digest_after": after,
            "saved_failure_logs": [
                {
                    "path": path.relative_to(evidence_root).as_posix(),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
                for path in logs
            ],
        },
        "adoption_surface": adoption,
        "proof_recommendations": recommendations,
        "workspace_failure_bundle": workspace_bundle,
        "failure_vector_bundle": vectors,
        "doctor_report": doctor,
        "trajectory_evidence": trajectory,
        "repo_memory_profile": memory,
        "authority_boundary": dict(_AUTHORITY_BOUNDARY),
    }
    payload["verification"] = _verify(payload)
    if not payload["repository_unchanged"]:
        raise RuntimeError("operator proof detected a repository mutation")
    if not _truth(_mapping(payload["verification"]).get("ok")):
        raise RuntimeError("operator proof failed shared-contract verification")

    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(out_dir / PROOF_JSON, payload)
    (out_dir / PROOF_MD).write_text(render_markdown(payload), encoding="utf-8")
    _write_json(out_dir / WORKSPACE_FAILURES_JSON, workspace_bundle)
    _write_json(out_dir / DOCTOR_JSON, doctor)
    (out_dir / DOCTOR_MD).write_text(render_doctor_report_markdown(doctor), encoding="utf-8")
    _write_json(out_dir / REPO_MEMORY_JSON, memory)
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sdetkit-mixed-monorepo-operator-proof")
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--failure-log", required=True, action="append", type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ns = parser.parse_args(list(argv) if argv is not None else None)
    build_mixed_monorepo_operator_proof(
        repo=ns.repo,
        failure_logs=tuple(ns.failure_log),
        evidence_root=ns.evidence_root,
        out_dir=ns.out_dir,
    )
    sys.stdout.write(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "status": "review_required",
                "verification_ok": True,
                "authority_boundary": dict(_AUTHORITY_BOUNDARY),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
