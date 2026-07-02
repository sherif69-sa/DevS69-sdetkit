from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from sdetkit import pr_quality_terminal_workflows as base

JsonObject = dict[str, Any]

_BLOCKER_NAME = "PR Quality terminal workflow snapshot"


def _string(value: Any) -> str:
    return str(value or "").strip()


def _integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _context_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    unique: dict[str, str] = {}
    for value in values:
        text = _string(value)
        key = base.canonical_context(text)
        if text and key and key not in unique:
            unique[key] = text
    return [unique[key] for key in sorted(unique)]


def _workflow_names(rows: list[JsonObject]) -> list[str]:
    return [_string(row.get("name")) for row in rows if _string(row.get("name"))]


def _missing_expected_contexts(
    rows: list[JsonObject],
    expected_contexts: list[str],
) -> list[str]:
    observed = {base.canonical_context(row.get("name")) for row in rows}
    return [
        context
        for context in expected_contexts
        if base.canonical_context(context) not in observed
    ]


def classify_required_terminal_snapshot(
    rows: list[JsonObject],
    *,
    expected_contexts: list[str],
    expected_head_sha: str,
    current_head_sha: str,
    stable_poll_count: int,
    required_stable_polls: int,
    timed_out: bool = False,
    collection_errors: list[str] | None = None,
) -> JsonObject:
    expected = _context_list(expected_contexts)
    snapshot = base.classify_terminal_snapshot(
        rows,
        expected_head_sha=expected_head_sha,
        current_head_sha=current_head_sha,
        stable_poll_count=stable_poll_count,
        required_stable_polls=required_stable_polls,
        timed_out=timed_out,
        collection_errors=collection_errors,
    )
    missing = _missing_expected_contexts(rows, expected)
    required_contexts_available = bool(expected)
    evidence_complete = bool(rows) and required_contexts_available and not missing
    if snapshot["status"] != "stale" and not evidence_complete:
        snapshot["status"] = "incomplete"

    failed_names = _workflow_names(snapshot.get("failed_workflows", []))
    pending_names = _workflow_names(snapshot.get("pending_workflows", []))
    unknown_names = _workflow_names(snapshot.get("unknown_workflows", []))
    snapshot.update(
        {
            "schema_version": "sdetkit.pr_quality.required_terminal_snapshot.v1",
            "required_contexts": expected,
            "required_context_count": len(expected),
            "required_contexts_available": required_contexts_available,
            "missing_expected_contexts": missing,
            "missing_expected_context_count": len(missing),
            "failed_workflow_names": failed_names,
            "pending_workflow_names": pending_names,
            "unknown_workflow_names": unknown_names,
            "terminal_evidence_complete": bool(
                snapshot["status"] in {"passed", "failed"} and evidence_complete
            ),
            "exact_head_complete": bool(
                snapshot.get("exact_head")
                and snapshot["status"] in {"passed", "failed"}
                and evidence_complete
            ),
        }
    )
    return snapshot


def collect_required_terminal_snapshot(
    *,
    repository: str,
    pr_number: int,
    head_sha: str,
    expected_contexts: list[str],
    current_workflow: str = "PR Quality Comment",
    timeout_seconds: int = 600,
    poll_interval_seconds: int = 15,
    required_stable_polls: int = 2,
) -> JsonObject:
    expected = _context_list(expected_contexts)
    if not expected:
        return classify_required_terminal_snapshot(
            [],
            expected_contexts=[],
            expected_head_sha=head_sha,
            current_head_sha=head_sha,
            stable_poll_count=0,
            required_stable_polls=required_stable_polls,
            collection_errors=["required check contexts unavailable"],
        )

    started = time.monotonic()
    previous_signature = ""
    stable_poll_count = 0
    last_rows: list[JsonObject] = []
    current_head_sha = head_sha
    errors: list[str] = []

    while True:
        errors = []
        try:
            pr = base._gh_api_json(f"repos/{repository}/pulls/{pr_number}")
            current_head_sha = _string((pr.get("head") or {}).get("sha"))
            payload = base._gh_api_json(
                f"repos/{repository}/actions/runs"
                f"?head_sha={head_sha}&event=pull_request&per_page=100"
            )
            raw_runs = payload.get("workflow_runs") if isinstance(payload, dict) else []
            last_rows = base.normalize_workflow_runs(
                [item for item in raw_runs or [] if isinstance(item, dict)],
                current_workflow=current_workflow,
            )
        except (
            OSError,
            subprocess.CalledProcessError,
            json.JSONDecodeError,
            ValueError,
        ) as exc:
            errors = [f"terminal workflow collection failed: {exc}"]

        provisional = classify_required_terminal_snapshot(
            last_rows,
            expected_contexts=expected,
            expected_head_sha=head_sha,
            current_head_sha=current_head_sha,
            stable_poll_count=0,
            required_stable_polls=required_stable_polls,
            collection_errors=errors,
        )
        signature = base.workflow_signature(last_rows)
        waiting = bool(
            provisional["pending_workflows"]
            or provisional["unknown_workflows"]
            or provisional["missing_expected_contexts"]
            or errors
        )
        if not waiting and signature == previous_signature:
            stable_poll_count += 1
        elif not waiting:
            stable_poll_count = 1
        else:
            stable_poll_count = 0
        previous_signature = signature

        snapshot = classify_required_terminal_snapshot(
            last_rows,
            expected_contexts=expected,
            expected_head_sha=head_sha,
            current_head_sha=current_head_sha,
            stable_poll_count=stable_poll_count,
            required_stable_polls=required_stable_polls,
            collection_errors=errors,
        )
        if snapshot["status"] in {"passed", "failed", "stale"}:
            return snapshot
        if time.monotonic() - started >= timeout_seconds:
            return classify_required_terminal_snapshot(
                last_rows,
                expected_contexts=expected,
                expected_head_sha=head_sha,
                current_head_sha=current_head_sha,
                stable_poll_count=stable_poll_count,
                required_stable_polls=required_stable_polls,
                timed_out=True,
                collection_errors=errors,
            )
        time.sleep(max(poll_interval_seconds, 1))


def _record_matches_run(record: JsonObject, run: JsonObject) -> bool:
    workflow_id = _integer(run.get("workflow_id"))
    record_workflow_id = _integer(record.get("workflow_id"))
    if workflow_id and record_workflow_id == workflow_id:
        return True
    name = base.canonical_context(run.get("name"))
    return bool(name and base.canonical_context(record.get("name")) == name)


def _terminal_record(
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


def _incomplete_reason(snapshot: JsonObject) -> str:
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


def merge_required_terminal_snapshot_into_checks(
    payload: JsonObject,
    snapshot: JsonObject,
) -> JsonObject:
    merged = dict(payload)
    records_key = "check_runs" if isinstance(payload.get("check_runs"), list) else "checks"
    records = [
        dict(item)
        for item in payload.get(records_key, [])
        if isinstance(item, dict) and _string(item.get("name")) != _BLOCKER_NAME
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
        matches = [index for index, record in enumerate(records) if _record_matches_run(record, run)]
        matched_records = [records[index] for index in matches]
        authoritative = _terminal_record(
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
                "name": _BLOCKER_NAME,
                "status": "completed",
                "conclusion": "failure",
                "head_sha": _string(snapshot.get("expected_head_sha")),
                "required": True,
                "log": _incomplete_reason(snapshot),
                "terminal_snapshot_source": True,
            }
        )

    merged[records_key] = records
    merged["terminal_workflow_snapshot"] = snapshot
    merged["terminal_failed_workflow_names"] = list(
        snapshot.get("failed_workflow_names", [])
    )
    merged["terminal_pending_workflow_names"] = list(
        snapshot.get("pending_workflow_names", [])
    )
    merged["terminal_unknown_workflow_names"] = list(
        snapshot.get("unknown_workflow_names", [])
    )
    merged["terminal_missing_required_contexts"] = list(
        snapshot.get("missing_expected_contexts", [])
    )
    merged["terminal_check_snapshot_complete"] = bool(
        snapshot.get("terminal_evidence_complete")
    )
    return merged


def _snapshot_covers_expected(
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
        return {
            base.canonical_context(item) for item in recorded
        } == {base.canonical_context(item) for item in expected}
    rows = [item for item in snapshot.get("workflow_runs", []) if isinstance(item, dict)]
    return not _missing_expected_contexts(rows, expected)


def collect_and_merge_terminal_snapshot_from_environment(
    *,
    checks_json: Path,
    out_dir: Path,
) -> JsonObject | None:
    if os.environ.get("GITHUB_ACTIONS", "").lower() != "true":
        return None
    repository = _string(os.environ.get("GITHUB_REPOSITORY"))
    if not repository:
        owner = _string(os.environ.get("REPOSITORY_OWNER"))
        name = _string(os.environ.get("REPOSITORY_NAME"))
        repository = f"{owner}/{name}" if owner and name else ""
    head_sha = _string(os.environ.get("HEAD_SHA"))
    pr_number = _integer(os.environ.get("PR_NUMBER"))
    if not repository or not head_sha or pr_number <= 0 or not os.environ.get("GH_TOKEN"):
        return None

    payload = json.loads(checks_json.read_text(encoding="utf-8"))
    checks_payload = payload if isinstance(payload, dict) else {}
    expected_contexts = _context_list(checks_payload.get("required_contexts", []))
    snapshot_path = out_dir / "terminal-workflow-snapshot.json"
    snapshot: JsonObject = {}
    if snapshot_path.exists():
        candidate = json.loads(snapshot_path.read_text(encoding="utf-8"))
        if isinstance(candidate, dict) and _snapshot_covers_expected(
            candidate,
            head_sha=head_sha,
            expected_contexts=expected_contexts,
        ):
            snapshot = candidate

    if not snapshot:
        snapshot = collect_required_terminal_snapshot(
            repository=repository,
            pr_number=pr_number,
            head_sha=head_sha,
            expected_contexts=expected_contexts,
            current_workflow=_string(os.environ.get("GITHUB_WORKFLOW") or "PR Quality Comment"),
            timeout_seconds=max(
                _integer(os.environ.get("SDETKIT_TERMINAL_TIMEOUT_SECONDS")) or 600, 1
            ),
            poll_interval_seconds=max(
                _integer(os.environ.get("SDETKIT_TERMINAL_POLL_INTERVAL_SECONDS")) or 15,
                1,
            ),
            required_stable_polls=max(
                _integer(os.environ.get("SDETKIT_TERMINAL_STABLE_POLLS")) or 2,
                2,
            ),
        )
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(
            json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    merged = merge_required_terminal_snapshot_into_checks(checks_payload, snapshot)
    checks_json.write_text(
        json.dumps(merged, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return snapshot
