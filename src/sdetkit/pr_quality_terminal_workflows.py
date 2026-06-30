from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

JsonObject = dict[str, Any]

_FAILURE_CONCLUSIONS = {
    "action_required",
    "cancelled",
    "failure",
    "startup_failure",
    "timed_out",
}
_SUCCESS_CONCLUSIONS = {"neutral", "skipped", "success"}
_PENDING_STATUSES = {
    "expected",
    "in_progress",
    "pending",
    "queued",
    "requested",
    "waiting",
}
_PUBLISHER_WORKFLOWS = {"PR Quality Publisher"}


def _string(value: Any) -> str:
    return str(value or "").strip()


def _integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def canonical_context(value: Any) -> str:
    return "".join(character.lower() for character in _string(value) if character.isalnum())


def normalize_workflow_runs(
    rows: list[JsonObject],
    *,
    current_workflow: str = "PR Quality Comment",
) -> list[JsonObject]:
    latest: dict[str, JsonObject] = {}
    for raw in rows:
        name = _string(raw.get("name")) or "Unnamed workflow"
        if name == current_workflow or name in _PUBLISHER_WORKFLOWS:
            continue
        workflow_id = _integer(raw.get("workflow_id"))
        key = str(workflow_id) if workflow_id else canonical_context(name)
        normalized = {
            "id": _integer(raw.get("id")),
            "workflow_id": workflow_id,
            "name": name,
            "status": _string(raw.get("status")) or "unknown",
            "conclusion": _string(raw.get("conclusion")).lower(),
            "run_attempt": max(_integer(raw.get("run_attempt")), 1),
            "run_number": _integer(raw.get("run_number")),
            "head_sha": _string(raw.get("head_sha")),
            "html_url": _string(raw.get("html_url")),
            "event": _string(raw.get("event")),
        }
        previous = latest.get(key)
        rank = (
            normalized["run_attempt"],
            normalized["run_number"],
            normalized["id"],
        )
        previous_rank = (
            (
                previous["run_attempt"],
                previous["run_number"],
                previous["id"],
            )
            if previous
            else (-1, -1, -1)
        )
        if rank >= previous_rank:
            latest[key] = normalized
    return sorted(
        latest.values(),
        key=lambda item: (canonical_context(item["name"]), item["id"]),
    )


def workflow_signature(rows: list[JsonObject]) -> str:
    stable = [
        {
            "id": row["id"],
            "workflow_id": row["workflow_id"],
            "name": row["name"],
            "status": row["status"],
            "conclusion": row["conclusion"],
            "run_attempt": row["run_attempt"],
        }
        for row in rows
    ]
    return json.dumps(stable, sort_keys=True, separators=(",", ":"))


def classify_terminal_snapshot(
    rows: list[JsonObject],
    *,
    expected_head_sha: str,
    current_head_sha: str,
    stable_poll_count: int,
    required_stable_polls: int,
    timed_out: bool = False,
    collection_errors: list[str] | None = None,
) -> JsonObject:
    errors = list(collection_errors or [])
    stale = bool(expected_head_sha) and current_head_sha != expected_head_sha
    pending = [
        row
        for row in rows
        if row["status"].lower() in _PENDING_STATUSES
        or (row["status"].lower() != "completed" and not row["conclusion"])
    ]
    failures = [
        row
        for row in rows
        if row["conclusion"] in _FAILURE_CONCLUSIONS
        or (
            row["status"].lower() == "completed"
            and row["conclusion"]
            and row["conclusion"] not in _SUCCESS_CONCLUSIONS
        )
    ]
    unknown = [
        row
        for row in rows
        if row not in pending
        and row not in failures
        and row["status"].lower() == "completed"
        and row["conclusion"] not in _SUCCESS_CONCLUSIONS
    ]
    stable = stable_poll_count >= required_stable_polls
    terminal = not stale and not pending and not unknown and stable and not timed_out and not errors
    if stale:
        status = "stale"
    elif terminal and failures:
        status = "failed"
    elif terminal:
        status = "passed"
    else:
        status = "incomplete"
    return {
        "schema_version": "sdetkit.pr_quality.terminal_workflow_snapshot.v1",
        "status": status,
        "expected_head_sha": expected_head_sha,
        "current_head_sha": current_head_sha,
        "exact_head": not stale,
        "stable_poll_count": stable_poll_count,
        "required_stable_polls": required_stable_polls,
        "timed_out": timed_out,
        "workflow_count": len(rows),
        "failed_workflow_count": len(failures),
        "pending_workflow_count": len(pending),
        "unknown_workflow_count": len(unknown),
        "workflow_runs": rows,
        "failed_workflows": failures,
        "pending_workflows": pending,
        "unknown_workflows": unknown,
        "collection_errors": errors,
        "reporting_only": True,
        "patch_application_allowed": False,
        "automation_allowed": False,
        "security_dismissal_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def _gh_api_json(path: str) -> Any:
    completed = subprocess.run(
        [
            "gh",
            "api",
            "-H",
            "Accept: application/vnd.github+json",
            path,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def collect_terminal_workflow_snapshot(
    *,
    repository: str,
    pr_number: int,
    head_sha: str,
    current_workflow: str = "PR Quality Comment",
    timeout_seconds: int = 600,
    poll_interval_seconds: int = 15,
    required_stable_polls: int = 2,
) -> JsonObject:
    started = time.monotonic()
    previous_signature = ""
    stable_poll_count = 0
    last_rows: list[JsonObject] = []
    current_head_sha = head_sha
    errors: list[str] = []

    while True:
        errors = []
        try:
            pr = _gh_api_json(f"repos/{repository}/pulls/{pr_number}")
            current_head_sha = _string((pr.get("head") or {}).get("sha"))
            payload = _gh_api_json(
                f"repos/{repository}/actions/runs"
                f"?head_sha={head_sha}&event=pull_request&per_page=100"
            )
            raw_runs = payload.get("workflow_runs") if isinstance(payload, dict) else []
            last_rows = normalize_workflow_runs(
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

        provisional = classify_terminal_snapshot(
            last_rows,
            expected_head_sha=head_sha,
            current_head_sha=current_head_sha,
            stable_poll_count=0,
            required_stable_polls=required_stable_polls,
            collection_errors=errors,
        )
        signature = workflow_signature(last_rows)
        waiting = bool(
            provisional["pending_workflows"] or provisional["unknown_workflows"] or errors
        )
        if not waiting and signature == previous_signature:
            stable_poll_count += 1
        elif not waiting:
            stable_poll_count = 1
        else:
            stable_poll_count = 0
        previous_signature = signature

        snapshot = classify_terminal_snapshot(
            last_rows,
            expected_head_sha=head_sha,
            current_head_sha=current_head_sha,
            stable_poll_count=stable_poll_count,
            required_stable_polls=required_stable_polls,
            collection_errors=errors,
        )
        if snapshot["status"] in {"passed", "failed", "stale"}:
            return snapshot
        if time.monotonic() - started >= timeout_seconds:
            return classify_terminal_snapshot(
                last_rows,
                expected_head_sha=head_sha,
                current_head_sha=current_head_sha,
                stable_poll_count=stable_poll_count,
                required_stable_polls=required_stable_polls,
                timed_out=True,
                collection_errors=errors,
            )
        time.sleep(max(poll_interval_seconds, 1))


def merge_terminal_snapshot_into_checks(
    payload: JsonObject,
    snapshot: JsonObject,
) -> JsonObject:
    merged = dict(payload)
    records_key = "check_runs" if isinstance(payload.get("check_runs"), list) else "checks"
    records = [dict(item) for item in payload.get(records_key, []) if isinstance(item, dict)]
    required_contexts = {
        canonical_context(item) for item in payload.get("required_contexts", []) if _string(item)
    }
    existing_workflow_ids = {
        _integer(item.get("workflow_id")) for item in records if _integer(item.get("workflow_id"))
    }

    for run in snapshot.get("workflow_runs", []):
        workflow_id = _integer(run.get("workflow_id"))
        if workflow_id and workflow_id in existing_workflow_ids:
            continue
        name = _string(run.get("name"))
        records.append(
            {
                "id": _integer(run.get("id")),
                "workflow_id": workflow_id,
                "name": name,
                "status": _string(run.get("status")),
                "conclusion": _string(run.get("conclusion")),
                "details_url": _string(run.get("html_url")),
                "html_url": _string(run.get("html_url")),
                "head_sha": _string(run.get("head_sha")),
                "required": canonical_context(name) in required_contexts,
                "workflow_run": dict(run),
                "terminal_snapshot_source": True,
            }
        )

    if snapshot.get("status") in {"incomplete", "stale"}:
        pending_names = [
            _string(item.get("name"))
            for item in snapshot.get("pending_workflows", [])
            if _string(item.get("name"))
        ]
        error_text = "; ".join(snapshot.get("collection_errors", []))
        reason = error_text or (
            "pending workflows: " + ", ".join(pending_names)
            if pending_names
            else f"terminal workflow snapshot status={snapshot.get('status')}"
        )
        records.append(
            {
                "name": "PR Quality terminal workflow snapshot",
                "status": "completed",
                "conclusion": "failure",
                "head_sha": _string(snapshot.get("expected_head_sha")),
                "required": True,
                "log": reason,
                "terminal_snapshot_source": True,
            }
        )

    merged[records_key] = records
    merged["terminal_workflow_snapshot"] = snapshot
    return merged


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

    snapshot_path = out_dir / "terminal-workflow-snapshot.json"
    if snapshot_path.exists():
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        if _string(snapshot.get("expected_head_sha")) != head_sha:
            snapshot = {}
    else:
        snapshot = {}

    if not snapshot:
        snapshot = collect_terminal_workflow_snapshot(
            repository=repository,
            pr_number=pr_number,
            head_sha=head_sha,
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

    payload = json.loads(checks_json.read_text(encoding="utf-8"))
    merged = merge_terminal_snapshot_into_checks(
        payload if isinstance(payload, dict) else {},
        snapshot,
    )
    checks_json.write_text(
        json.dumps(merged, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return snapshot
