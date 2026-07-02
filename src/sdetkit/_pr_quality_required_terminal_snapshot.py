from __future__ import annotations

import json
import subprocess
import time
from typing import Any

from sdetkit import pr_quality_terminal_workflows as base

JsonObject = dict[str, Any]


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


def _required_workflow_rows(
    rows: list[JsonObject],
    expected_contexts: list[str],
) -> list[JsonObject]:
    expected = {base.canonical_context(item) for item in _context_list(expected_contexts)}
    latest: dict[str, JsonObject] = {}
    for row in rows:
        key = base.canonical_context(row.get("name"))
        if not key or key not in expected:
            continue
        previous = latest.get(key)
        rank = (
            _integer(row.get("run_attempt")),
            _integer(row.get("run_number")),
            _integer(row.get("id")),
        )
        previous_rank = (
            (
                _integer(previous.get("run_attempt")),
                _integer(previous.get("run_number")),
                _integer(previous.get("id")),
            )
            if previous
            else (-1, -1, -1)
        )
        if rank >= previous_rank:
            latest[key] = dict(row)
    return [latest[key] for key in sorted(latest)]


def _missing_expected_contexts(
    rows: list[JsonObject],
    expected_contexts: list[str],
) -> list[str]:
    observed = {base.canonical_context(row.get("name")) for row in rows}
    return [
        context for context in expected_contexts if base.canonical_context(context) not in observed
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
    observed_rows = [dict(row) for row in rows]
    required_rows = _required_workflow_rows(observed_rows, expected)
    expected_keys = {base.canonical_context(item) for item in expected}
    ignored_rows = [
        row for row in observed_rows if base.canonical_context(row.get("name")) not in expected_keys
    ]
    snapshot = base.classify_terminal_snapshot(
        required_rows,
        expected_head_sha=expected_head_sha,
        current_head_sha=current_head_sha,
        stable_poll_count=stable_poll_count,
        required_stable_polls=required_stable_polls,
        timed_out=timed_out,
        collection_errors=collection_errors,
    )
    missing = _missing_expected_contexts(required_rows, expected)
    required_contexts_available = bool(expected)
    evidence_complete = bool(required_rows) and required_contexts_available and not missing
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
            "observed_workflow_count": len(observed_rows),
            "ignored_non_required_workflow_count": len(ignored_rows),
            "ignored_non_required_workflow_names": _workflow_names(ignored_rows),
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
        required_rows = _required_workflow_rows(last_rows, expected)
        signature = base.workflow_signature(required_rows)
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
