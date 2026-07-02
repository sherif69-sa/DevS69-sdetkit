from __future__ import annotations

from sdetkit import pr_quality_terminal_workflows as base
from sdetkit._pr_quality_required_terminal_snapshot import (
    JsonObject,
    _context_list,
    _integer,
    _string,
)

BLOCKER_NAME = "PR Quality terminal workflow snapshot"


def record_matches_run(record: JsonObject, run: JsonObject) -> bool:
    workflow_id = _integer(run.get("workflow_id"))
    record_workflow_id = _integer(record.get("workflow_id"))
    if workflow_id and record_workflow_id == workflow_id:
        return True
    name = base.canonical_context(run.get("name"))
    return bool(name and base.canonical_context(record.get("name")) == name)


def terminal_record(
    existing: list[JsonObject],
    run: JsonObject,
    *,
    required_contexts: set[str],
) -> JsonObject:
    merged: JsonObject = {}
    required = False
    for record in existing:
        merged.update(record)
        required = required or bool(record.get("required"))

    name = _string(run.get("name"))
    url = _string(run.get("html_url"))
    merged.update(
        {
            "id": _integer(run.get("id")),
            "workflow_id": _integer(run.get("workflow_id")),
            "name": name,
            "status": _string(run.get("status")),
            "conclusion": _string(run.get("conclusion")),
            "details_url": url,
            "html_url": url,
            "head_sha": _string(run.get("head_sha")),
            "required": required or base.canonical_context(name) in required_contexts,
            "workflow_run": dict(run),
            "terminal_snapshot_source": True,
        }
    )
    return merged


def incomplete_reason(snapshot: JsonObject) -> str:
    parts: list[str] = []
    errors = [_string(item) for item in snapshot.get("collection_errors", []) if _string(item)]
    if errors:
        parts.append("collection errors: " + "; ".join(errors))
    missing = _context_list(snapshot.get("missing_expected_contexts", []))
    if missing:
        parts.append("missing required checks: " + ", ".join(missing))
    pending = _context_list(snapshot.get("pending_workflow_names", []))
    if pending:
        parts.append("pending workflows: " + ", ".join(pending))
    unknown = _context_list(snapshot.get("unknown_workflow_names", []))
    if unknown:
        parts.append("unknown workflows: " + ", ".join(unknown))
    failed = _context_list(snapshot.get("failed_workflow_names", []))
    if failed:
        parts.append("failed workflows: " + ", ".join(failed))
    return "; ".join(parts) or f"terminal workflow snapshot status={snapshot.get('status')}"
