from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.workflow_permission_decision_record.v1"
CONTRACT_PATH = "docs/contracts/workflow-permission-decision-record.v1.json"
DECISION_DIR = "docs/ci/workflow-permission-decisions"
DECISION_GLOB = "*.decision.json"
GENERATOR_SOURCE_LABEL = "src/sdetkit/workflow_permission_decision_record.py"
ALLOWED_DECISIONS = ("keep", "reduce", "split", "defer")

AUTHORITY_FIELDS = (
    "automation_allowed",
    "implementation_authorized",
    "merge_authorized",
    "patch_application_allowed",
    "security_dismissal_allowed",
    "semantic_equivalence_proven",
    "workflow_mutation_allowed",
)


def authority_boundary() -> dict[str, bool]:
    return {field: False for field in AUTHORITY_FIELDS}


def decision_record_paths(repo_root: str | Path = ".") -> list[Path]:
    root = Path(repo_root).resolve()
    directory = root / DECISION_DIR
    if not directory.is_dir():
        return []
    return sorted(directory.glob(DECISION_GLOB))


def _nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_list(value: object) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(_nonempty_string(item) for item in value)
    )


def _is_timezone_aware_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _validate_proposed_change(decision: str, value: object) -> list[str]:
    reasons: list[str] = []
    if not isinstance(value, dict):
        return ["proposed_change_missing"]

    kind = value.get("kind")
    if decision in {"keep", "defer"}:
        if kind != "none":
            reasons.append("proposed_change_must_be_none")
        return reasons

    if kind != "permission_only":
        reasons.append("proposed_change_must_be_permission_only")
    if not _nonempty_string(value.get("summary")):
        reasons.append("proposed_change_summary_missing")
    if not _nonempty_string(value.get("evidence_ref")):
        reasons.append("proposed_change_evidence_ref_missing")
    return reasons


def _validate_rollback(value: object, workflow_sha256: str) -> list[str]:
    if not isinstance(value, dict):
        return ["rollback_contract_missing"]
    reasons: list[str] = []
    if value.get("strategy") != "restore_exact_workflow_bytes":
        reasons.append("rollback_strategy_invalid")
    if value.get("workflow_sha256") != workflow_sha256:
        reasons.append("rollback_workflow_digest_mismatch")
    return reasons


def validate_decision_record(
    record: dict[str, Any],
    review_entry: dict[str, Any],
) -> dict[str, Any]:
    reasons: list[str] = []

    if record.get("schema_version") != SCHEMA_VERSION:
        reasons.append("schema_version_mismatch")
    if record.get("review_id") != review_entry.get("review_id"):
        reasons.append("review_id_mismatch")
    if record.get("workflow") != review_entry.get("workflow"):
        reasons.append("workflow_mismatch")
    if record.get("permission_group") != review_entry.get("permission_group"):
        reasons.append("permission_group_mismatch")

    current_digest = str(review_entry.get("workflow_sha256", ""))
    recorded_digest = record.get("workflow_sha256")
    if recorded_digest != current_digest:
        reasons.append("workflow_digest_mismatch")

    decision = record.get("decision")
    if decision not in ALLOWED_DECISIONS:
        reasons.append("decision_invalid")
        decision_text = ""
    else:
        decision_text = str(decision)

    if not _nonempty_string(record.get("reviewer")):
        reasons.append("reviewer_missing")
    reviewer_evidence = record.get("reviewer_evidence")
    if not _nonempty_string(reviewer_evidence):
        reasons.append("reviewer_evidence_missing")
    elif not str(reviewer_evidence).startswith("https://github.com/"):
        reasons.append("reviewer_evidence_must_be_github_url")
    if not _is_timezone_aware_timestamp(record.get("decided_at")):
        reasons.append("decided_at_invalid")
    if not _nonempty_string(record.get("rationale")):
        reasons.append("rationale_missing")

    if decision_text:
        reasons.extend(_validate_proposed_change(decision_text, record.get("proposed_change")))
    if not _string_list(record.get("proof_contract")):
        reasons.append("proof_contract_missing")
    reasons.extend(_validate_rollback(record.get("rollback_contract"), current_digest))

    if record.get("authority_boundary") != authority_boundary():
        reasons.append("authority_boundary_mismatch")

    reasons = sorted(set(reasons))
    stale_reasons = {"workflow_digest_mismatch", "rollback_workflow_digest_mismatch"}
    status = "current"
    if reasons:
        status = "stale" if set(reasons).issubset(stale_reasons) else "invalid"

    return {
        "status": status,
        "valid_current": status == "current",
        "stale": status == "stale",
        "reasons": reasons,
        "review_id": review_entry.get("review_id"),
        "workflow": review_entry.get("workflow"),
        "current_workflow_sha256": current_digest,
        "recorded_workflow_sha256": recorded_digest,
        "decision": decision if decision in ALLOWED_DECISIONS else None,
        "reviewer": record.get("reviewer"),
        "reviewer_evidence": record.get("reviewer_evidence"),
        "authority_boundary": authority_boundary(),
    }


def _load_record(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None, ["record_json_invalid"]
    if not isinstance(payload, dict):
        return None, ["record_must_be_object"]
    return payload, []


def build_decision_record_index(
    repo_root: str | Path,
    review_queue: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    by_workflow = {
        str(entry.get("workflow", "")): entry
        for entry in review_queue
        if _nonempty_string(entry.get("workflow"))
    }
    records: list[dict[str, Any]] = []
    current_candidates: dict[str, list[dict[str, Any]]] = {}

    for path in decision_record_paths(root):
        relative = path.relative_to(root).as_posix()
        payload, load_reasons = _load_record(path)
        if payload is None:
            records.append(
                {
                    "record_path": relative,
                    "status": "invalid",
                    "valid_current": False,
                    "reasons": load_reasons,
                    "authority_boundary": authority_boundary(),
                }
            )
            continue

        workflow = payload.get("workflow")
        if not isinstance(workflow, str) or workflow not in by_workflow:
            records.append(
                {
                    "record_path": relative,
                    "status": "invalid",
                    "valid_current": False,
                    "reasons": ["workflow_not_in_review_queue"],
                    "workflow": workflow,
                    "authority_boundary": authority_boundary(),
                }
            )
            continue

        validation = validate_decision_record(payload, by_workflow[workflow])
        item = {"record_path": relative, **validation, "record": payload}
        records.append(item)
        if validation["valid_current"]:
            current_candidates.setdefault(workflow, []).append(item)

    current_by_workflow: dict[str, dict[str, Any]] = {}
    conflict_workflows: list[str] = []
    for workflow, candidates in sorted(current_candidates.items()):
        if len(candidates) == 1:
            current_by_workflow[workflow] = candidates[0]
            continue
        conflict_workflows.append(workflow)
        for candidate in candidates:
            candidate["status"] = "conflict"
            candidate["valid_current"] = False
            candidate["reasons"] = sorted(
                set([*candidate.get("reasons", []), "duplicate_current_decision_records"])
            )

    status_counts: dict[str, int] = {}
    for item in records:
        status = str(item.get("status", "invalid"))
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "schema_version": SCHEMA_VERSION,
        "record_count": len(records),
        "current_decision_count": len(current_by_workflow),
        "conflict_workflow_count": len(conflict_workflows),
        "conflict_workflows": conflict_workflows,
        "status_counts": dict(sorted(status_counts.items())),
        "records": records,
        "current_by_workflow": current_by_workflow,
        "authority_boundary": authority_boundary(),
    }


def render_decision_record_index_text(index: dict[str, Any]) -> str:
    status_counts = index.get("status_counts", {})
    if not isinstance(status_counts, dict):
        status_counts = {}
    return "\n".join(
        [
            f"decision_record_count={index.get('record_count', 0)}",
            f"current_decision_count={index.get('current_decision_count', 0)}",
            f"conflict_workflow_count={index.get('conflict_workflow_count', 0)}",
            "status_counts=" + json.dumps(status_counts, sort_keys=True),
            "implementation_authorized=false",
            "workflow_mutation_allowed=false",
            "merge_authorized=false",
        ]
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sdetkit.workflow_permission_decision_record",
        description="Validate exact-digest human workflow permission decision records.",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    parser.add_argument("--fail-on-invalid", action="store_true")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    from .workflow_permission_review_control_plane import (
        build_workflow_permission_review_control_plane,
    )

    control_plane = build_workflow_permission_review_control_plane(ns.root)
    queue = control_plane.get("review_queue", [])
    if not isinstance(queue, list):
        queue = []
    typed_queue = [entry for entry in queue if isinstance(entry, dict)]
    index = build_decision_record_index(ns.root, typed_queue)

    if ns.format == "json":
        sys.stdout.write(json.dumps(index, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_decision_record_index_text(index) + "\n")

    if ns.fail_on_invalid and any(
        status != "current" for status in index.get("status_counts", {})
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
