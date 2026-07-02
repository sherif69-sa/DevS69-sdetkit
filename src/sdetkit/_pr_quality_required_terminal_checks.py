from __future__ import annotations

from sdetkit import pr_quality_terminal_workflows as base
from sdetkit._pr_quality_required_terminal_records import (
    BLOCKER_NAME,
    incomplete_reason,
    record_matches_run,
    terminal_record,
)
from sdetkit._pr_quality_required_terminal_snapshot import (
    JsonObject,
    _context_list,
    _missing_expected_contexts,
    _string,
)


def merge_required_terminal_snapshot_into_checks(
    payload: JsonObject,
    snapshot: JsonObject,
) -> JsonObject:
    merged = dict(payload)
    records_key = "check_runs" if isinstance(payload.get("check_runs"), list) else "checks"
    records = [
        dict(item)
        for item in payload.get(records_key, [])
        if isinstance(item, dict) and _string(item.get("name")) != BLOCKER_NAME
    ]
    required_contexts = {
        base.canonical_context(item)
        for item in payload.get("required_contexts", [])
        if _string(item)
    }

    for raw_run in snapshot.get("workflow_runs", []):
        if not isinstance(raw_run, dict):
            continue
        run = dict(raw_run)
        matches = [
            index
            for index, record in enumerate(records)
            if record_matches_run(record=record, run=run)
        ]
        matched_records = [records[index] for index in matches]
        authoritative = terminal_record(
            matched_records,
            run,
            required_contexts=required_contexts,
        )
        if matches:
            insert_at = min(matches)
            for index in reversed(matches):
                del records[index]
            records.insert(insert_at, authoritative)
        else:
            records.append(authoritative)

    if snapshot.get("status") in {"incomplete", "stale"}:
        records.append(
            {
                "name": BLOCKER_NAME,
                "status": "queued",
                "conclusion": "",
                "head_sha": _string(snapshot.get("expected_head_sha")),
                "required": True,
                "log": incomplete_reason(snapshot),
                "terminal_snapshot_source": True,
                "terminal_snapshot_incomplete": True,
            }
        )

    merged[records_key] = records
    merged["terminal_workflow_snapshot"] = snapshot
    merged["terminal_failed_workflow_names"] = list(snapshot.get("failed_workflow_names", []))
    merged["terminal_pending_workflow_names"] = list(snapshot.get("pending_workflow_names", []))
    merged["terminal_unknown_workflow_names"] = list(snapshot.get("unknown_workflow_names", []))
    merged["terminal_missing_required_contexts"] = list(
        snapshot.get("missing_expected_contexts", [])
    )
    merged["terminal_check_snapshot_complete"] = bool(snapshot.get("terminal_evidence_complete"))
    return merged


def snapshot_covers_expected(
    snapshot: JsonObject,
    *,
    head_sha: str,
    expected_contexts: list[str],
) -> bool:
    if _string(snapshot.get("expected_head_sha")) != head_sha:
        return False
    expected = _context_list(expected_contexts)
    recorded = _context_list(snapshot.get("required_contexts", []))
    if recorded:
        return {base.canonical_context(item) for item in recorded} == {
            base.canonical_context(item) for item in expected
        }
    rows = [item for item in snapshot.get("workflow_runs", []) if isinstance(item, dict)]
    return not _missing_expected_contexts(rows, expected)
