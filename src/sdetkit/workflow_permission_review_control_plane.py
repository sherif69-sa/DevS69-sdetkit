from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .workflow_governance_report import build_workflow_governance_report

SCHEMA_VERSION = "sdetkit.workflow_permission_review_control_plane.v1"
CONTRACT_PATH = "docs/contracts/workflow-permission-review-control-plane.v1.json"
DECISION_DIR = "docs/ci/workflow-permission-decisions"
REVIEW_CARD_DIR = "docs/ci/workflow-permission-review-cards"
GENERATOR_SOURCE_LABEL = "src/sdetkit/workflow_permission_review_control_plane.py"
INPUT_DIGEST_ALGORITHM = "sha256"
ALLOWED_DECISIONS = ("keep", "reduce", "split", "defer")

AUTHORITY_FIELDS = (
    "automation_allowed",
    "patch_application_allowed",
    "merge_authorized",
    "security_dismissal_allowed",
    "semantic_equivalence_proven",
    "workflow_mutation_allowed",
)


def _authority_boundary() -> dict[str, bool]:
    return {field: False for field in AUTHORITY_FIELDS}


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _update_input_digest(hasher: Any, label: str, content: bytes) -> None:
    label_bytes = label.encode("utf-8")
    hasher.update(len(label_bytes).to_bytes(8, "big"))
    hasher.update(label_bytes)
    hasher.update(len(content).to_bytes(8, "big"))
    hasher.update(content)


def _evidence_documents(root: Path) -> list[Path]:
    documents: list[Path] = []
    for relative_dir in (DECISION_DIR, REVIEW_CARD_DIR):
        directory = root / relative_dir
        if directory.is_dir():
            documents.extend(sorted(directory.glob("*.md")))
    return sorted(documents)


def _decision_evidence_refs(root: Path, workflow: str) -> list[str]:
    refs: list[str] = []
    decision_root = root / DECISION_DIR
    if not decision_root.is_dir():
        return refs
    for path in sorted(decision_root.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if workflow in text:
            refs.append(path.relative_to(root).as_posix())
    return refs


def _review_id(workflow: str) -> str:
    digest = hashlib.sha256(workflow.encode("utf-8")).hexdigest()[:16]
    return f"wpr-{digest}"


def workflow_permission_control_plane_input_provenance(
    repo_root: str | Path = ".",
    *,
    governance_payload: dict[str, Any] | None = None,
    generator_path: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    governance = governance_payload or build_workflow_governance_report(root)
    generator = (
        Path(generator_path).resolve() if generator_path is not None else Path(__file__).resolve()
    )

    inputs: list[tuple[str, bytes]] = [
        ("schema_version", SCHEMA_VERSION.encode("utf-8")),
        (GENERATOR_SOURCE_LABEL, generator.read_bytes()),
        (
            "workflow_governance_input_digest",
            str(governance.get("input_provenance", {}).get("input_digest", "")).encode("utf-8"),
        ),
    ]

    contract = root / CONTRACT_PATH
    if contract.is_file():
        inputs.append((CONTRACT_PATH, contract.read_bytes()))

    for path in _evidence_documents(root):
        inputs.append((path.relative_to(root).as_posix(), path.read_bytes()))

    hasher = hashlib.sha256()
    for label, content in sorted(inputs, key=lambda item: item[0]):
        _update_input_digest(hasher, label, content)

    return {
        "digest_algorithm": INPUT_DIGEST_ALGORITHM,
        "input_digest": hasher.hexdigest(),
        "input_count": len(inputs),
        "governance_input_digest": governance.get("input_provenance", {}).get("input_digest", ""),
        "generator_schema_version": SCHEMA_VERSION,
        "generator_source": GENERATOR_SOURCE_LABEL,
        "contract_path": CONTRACT_PATH,
        "decision_document_count": len(list((root / DECISION_DIR).glob("*.md")))
        if (root / DECISION_DIR).is_dir()
        else 0,
        "review_card_document_count": len(list((root / REVIEW_CARD_DIR).glob("*.md")))
        if (root / REVIEW_CARD_DIR).is_dir()
        else 0,
    }


def _proof_contract() -> list[str]:
    return [
        "python -m sdetkit workflow-governance-report --root . --format text",
        "python -m pytest -q tests/test_workflow_governance_report.py tests/test_workflow_permission_review_control_plane.py -o addopts=",
        "python -m pre_commit run -a",
        "exact-head repository CI before merge",
    ]


def _build_review_entry(root: Path, task: dict[str, Any]) -> dict[str, Any]:
    workflow = str(task.get("workflow", "unknown"))
    workflow_path = root / workflow
    workflow_bytes = workflow_path.read_bytes() if workflow_path.is_file() else b""
    decision_refs = _decision_evidence_refs(root, workflow)

    return {
        "review_id": _review_id(workflow),
        "workflow": workflow,
        "workflow_sha256": _sha256_bytes(workflow_bytes),
        "permission_group": task.get("permission_group", "unknown"),
        "granted_write_scopes": list(task.get("granted_write_scopes", [])),
        "inferred_permission_reasons": list(task.get("inferred_permission_reasons", [])),
        "required_human_evidence": list(task.get("required_evidence", [])),
        "review_state": (
            "decision_evidence_present" if decision_refs else "pending_human_review"
        ),
        "human_decision_recorded": False,
        "human_decision": None,
        "allowed_decisions": list(ALLOWED_DECISIONS),
        "decision_evidence_refs": decision_refs,
        "proposed_change": None,
        "next_allowed_action": (
            "review_existing_decision_evidence"
            if decision_refs
            else "collect_human_review_evidence"
        ),
        "proof_contract": _proof_contract(),
        "rollback_contract": {
            "strategy": "restore_exact_workflow_bytes",
            "workflow_sha256": _sha256_bytes(workflow_bytes),
        },
        "requires_human_review": True,
        "safe_to_patch": False,
        "authority_boundary": _authority_boundary(),
    }


def build_workflow_permission_review_control_plane(
    repo_root: str | Path = ".",
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    governance = build_workflow_governance_report(root)
    packet = governance.get("permission_review_evidence_packet", {})
    tasks = packet.get("review_tasks", []) if isinstance(packet, dict) else []
    review_queue = [
        _build_review_entry(root, task)
        for task in tasks
        if isinstance(task, dict)
    ]
    review_queue.sort(key=lambda item: str(item["workflow"]))

    group_counts: dict[str, int] = {}
    decision_evidence_count = 0
    for entry in review_queue:
        group = str(entry["permission_group"])
        group_counts[group] = group_counts.get(group, 0) + 1
        if entry["decision_evidence_refs"]:
            decision_evidence_count += 1

    provenance = workflow_permission_control_plane_input_provenance(
        root,
        governance_payload=governance,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "human_review_required" if review_queue else "not_required",
        "input_provenance": provenance,
        "freshness": {
            "status": "fresh",
            "input_digest_matches": True,
            "reporting_only": True,
            "repo_mutation": False,
            **_authority_boundary(),
        },
        "summary": {
            "permission_review_count": len(review_queue),
            "permission_group_count": len(group_counts),
            "group_counts": dict(sorted(group_counts.items())),
            "decision_evidence_present_count": decision_evidence_count,
            "human_decision_recorded_count": 0,
            "pending_human_review_count": len(review_queue),
            "automatic_permission_reduction_allowed": False,
            "next_allowed_action": (
                "collect_human_review_evidence" if review_queue else "none"
            ),
        },
        "review_queue": review_queue,
        "rules": {
            "review_first": True,
            "reporting_only": True,
            "decision_markdown_is_evidence_not_automatic_authority": True,
            "exact_workflow_digest_required": True,
            "human_decision_required_before_permission_change": True,
            "automatic_permission_reduction_allowed": False,
            "broad_permission_sweep_allowed": False,
            "workflow_mutation_allowed": False,
        },
        "authority_boundary": _authority_boundary(),
    }


def validate_workflow_permission_review_control_plane(
    repo_root: str | Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    current = build_workflow_permission_review_control_plane(repo_root)
    reasons: list[str] = []

    if payload.get("schema_version") != SCHEMA_VERSION:
        reasons.append("schema_version_mismatch")

    recorded_digest = payload.get("input_provenance", {}).get("input_digest", "")
    current_digest = current.get("input_provenance", {}).get("input_digest", "")
    if recorded_digest != current_digest:
        reasons.append("input_digest_mismatch")

    recorded_queue = payload.get("review_queue")
    if not isinstance(recorded_queue, list):
        reasons.append("review_queue_missing")
        recorded_queue = []

    current_by_workflow = {
        str(entry["workflow"]): entry
        for entry in current["review_queue"]
    }
    recorded_by_workflow = {
        str(entry.get("workflow", "")): entry
        for entry in recorded_queue
        if isinstance(entry, dict)
    }
    if set(recorded_by_workflow) != set(current_by_workflow):
        reasons.append("review_queue_workflows_mismatch")

    for workflow, current_entry in current_by_workflow.items():
        recorded_entry = recorded_by_workflow.get(workflow, {})
        if recorded_entry.get("workflow_sha256") != current_entry["workflow_sha256"]:
            reasons.append(f"workflow_digest_mismatch:{workflow}")
        if recorded_entry.get("authority_boundary") != _authority_boundary():
            reasons.append(f"authority_boundary_mismatch:{workflow}")
        if recorded_entry.get("human_decision_recorded") is not False:
            reasons.append(f"unexpected_automatic_decision:{workflow}")

    if payload.get("authority_boundary") != _authority_boundary():
        reasons.append("top_level_authority_boundary_mismatch")

    reasons = sorted(set(reasons))
    fresh = not reasons
    return {
        "status": "fresh" if fresh else "stale",
        "fresh": fresh,
        "reasons": reasons,
        "recorded_input_digest": recorded_digest,
        "current_input_digest": current_digest,
        "reporting_only": True,
        "repo_mutation": False,
        **_authority_boundary(),
    }


def render_workflow_permission_review_control_plane_markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", {})
    lines = [
        "# Workflow permission review control plane",
        "",
        f"- schema_version: `{payload.get('schema_version', 'unknown')}`",
        f"- status: `{payload.get('status', 'unknown')}`",
        f"- permission_review_count: {summary.get('permission_review_count', 0)}",
        f"- permission_group_count: {summary.get('permission_group_count', 0)}",
        f"- decision_evidence_present_count: {summary.get('decision_evidence_present_count', 0)}",
        f"- human_decision_recorded_count: {summary.get('human_decision_recorded_count', 0)}",
        f"- input_digest: `{payload.get('input_provenance', {}).get('input_digest', '')}`",
        "- automatic_permission_reduction_allowed: false",
        "- workflow_mutation_allowed: false",
        "",
        "## Group counts",
        "",
    ]

    group_counts = summary.get("group_counts", {})
    if isinstance(group_counts, dict) and group_counts:
        for group, count in sorted(group_counts.items()):
            lines.append(f"- `{group}`: {count}")
    else:
        lines.append("- none")

    lines.extend(["", "## Review queue", ""])
    queue = payload.get("review_queue", [])
    if isinstance(queue, list) and queue:
        for entry in queue:
            if not isinstance(entry, dict):
                continue
            lines.extend(
                [
                    f"### `{entry.get('workflow', 'unknown')}`",
                    "",
                    f"- review_id: `{entry.get('review_id', '')}`",
                    f"- workflow_sha256: `{entry.get('workflow_sha256', '')}`",
                    f"- permission_group: `{entry.get('permission_group', 'unknown')}`",
                    f"- review_state: `{entry.get('review_state', 'pending_human_review')}`",
                    "- human_decision_recorded: false",
                    "- safe_to_patch: false",
                ]
            )
            scopes = entry.get("granted_write_scopes", [])
            if isinstance(scopes, list) and scopes:
                lines.append("- granted_write_scopes:")
                for scope in scopes:
                    lines.append(f"  - `{scope}`")
            reasons = entry.get("inferred_permission_reasons", [])
            if isinstance(reasons, list) and reasons:
                lines.append("- inferred_permission_reasons:")
                for reason in reasons:
                    lines.append(f"  - {reason}")
            refs = entry.get("decision_evidence_refs", [])
            if isinstance(refs, list) and refs:
                lines.append("- decision_evidence_refs:")
                for ref in refs:
                    lines.append(f"  - `{ref}`")
            lines.append("")
    else:
        lines.append("- none")

    lines.extend(
        [
            "## Authority boundary",
            "",
            "- automation_allowed: false",
            "- patch_application_allowed: false",
            "- merge_authorized: false",
            "- security_dismissal_allowed: false",
            "- semantic_equivalence_proven: false",
            "- workflow_mutation_allowed: false",
            "",
        ]
    )
    return "\n".join(lines)


def write_workflow_permission_review_control_plane(
    *,
    repo_root: str | Path,
    out: str | Path,
    markdown_out: str | Path | None = None,
) -> dict[str, Any]:
    payload = build_workflow_permission_review_control_plane(repo_root)
    out_path = Path(out)
    markdown_path = Path(markdown_out) if markdown_out else out_path.with_suffix(".md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(
        render_workflow_permission_review_control_plane_markdown(payload) + "\n",
        encoding="utf-8",
    )
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sdetkit.workflow_permission_review_control_plane",
        description="Build a read-only workflow permission review control plane.",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--out",
        default="build/sdetkit/workflow-permission-review-control-plane.json",
    )
    parser.add_argument("--markdown-out", default="")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    parser.add_argument("--check-freshness", action="store_true")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    if ns.check_freshness:
        path = Path(ns.out)
        if not path.is_file():
            result = {
                "status": "stale",
                "fresh": False,
                "reasons": ["report_missing"],
                "reporting_only": True,
                "repo_mutation": False,
                **_authority_boundary(),
            }
        else:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                payload = {}
            if not isinstance(payload, dict):
                payload = {}
            result = validate_workflow_permission_review_control_plane(ns.root, payload)

        if ns.format == "json":
            sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
        else:
            reasons = result.get("reasons", [])
            sys.stdout.write(
                "\n".join(
                    [
                        f"freshness_status={result.get('status', 'stale')}",
                        f"fresh={str(bool(result.get('fresh', False))).lower()}",
                        "freshness_reasons=" + (",".join(reasons) if reasons else "none"),
                        "reporting_only=true",
                        "repo_mutation=false",
                        "workflow_mutation_allowed=false",
                    ]
                )
                + "\n"
            )
        return 0 if result.get("fresh") else 1

    payload = write_workflow_permission_review_control_plane(
        repo_root=ns.root,
        out=ns.out,
        markdown_out=ns.markdown_out or None,
    )
    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_workflow_permission_review_control_plane_markdown(payload) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
