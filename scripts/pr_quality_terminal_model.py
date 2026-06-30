from __future__ import annotations

from collections.abc import Mapping

from pr_quality_terminal_core import (
    inline,
    latest_runs,
    normalized_checks,
    normalized_statuses,
    required_rows,
    signature,
    text,
    trusted_link,
)
from pr_quality_terminal_failures import failed_workflows
from pr_quality_terminal_findings import finding_rows


def build_snapshot(
    *,
    repository,
    pr_number,
    head_sha,
    current_head_sha,
    workflow_runs,
    merge_commit_sha="",
    check_runs=(),
    statuses=(),
    required_contexts=(),
    jobs_by_run=None,
    logs_by_job=None,
    security_alerts=(),
    stable_poll_count=0,
    required_stable_polls=2,
    timed_out=False,
    collection_errors=(),
):
    runs = latest_runs(workflow_runs)
    checks = normalized_checks(check_runs)
    status_rows = normalized_statuses(statuses)
    required = required_rows(required_contexts, runs, checks, status_rows)
    pending = [row for row in runs if row["conclusion"] == "pending"]
    unknown = [row for row in runs if row["conclusion"] == "unknown"]
    failed = failed_workflows(runs, jobs_by_run, logs_by_job)
    missing_required = [row for row in required if row["state"] == "missing"]
    pending_required = [row for row in required if row["state"] == "pending"]
    failed_required = [row for row in required if row["state"] == "failure"]
    unknown_required = [row for row in required if row["state"] == "unknown"]
    security, incomplete_security = finding_rows(
        security_alerts, head_sha, merge_commit_sha, pr_number
    )
    exact_head = bool(head_sha) and current_head_sha == head_sha
    stable = stable_poll_count >= required_stable_polls
    terminal_snapshot = exact_head and not pending and not unknown and stable and not timed_out
    if not exact_head:
        snapshot_status, review_state = "stale", "stale"
    elif (
        not terminal_snapshot
        or missing_required
        or pending_required
        or unknown_required
        or incomplete_security
        or collection_errors
    ):
        snapshot_status, review_state = "incomplete", "waiting_or_unknown"
    elif failed or failed_required or security:
        snapshot_status, review_state = "terminal", "blocked"
    else:
        snapshot_status, review_state = "terminal", "ready"
    return {
        "schema_version": "sdetkit.pr_quality_terminal_snapshot.v1",
        "repository": repository,
        "pr_number": pr_number,
        "head_sha": head_sha,
        "current_head_sha": current_head_sha,
        "merge_commit_sha": merge_commit_sha,
        "exact_head": exact_head,
        "snapshot_status": snapshot_status,
        "review_state": review_state,
        "merge_readiness": "SHIP_REVIEWABLE" if review_state == "ready" else "NO_SHIP",
        "merge_authorized": False,
        "stable_poll_count": stable_poll_count,
        "required_stable_polls": required_stable_polls,
        "workflow_signature": signature(runs, required),
        "workflow_runs": runs,
        "failed_workflows": failed,
        "pending_workflows": pending,
        "unknown_workflows": unknown,
        "required_contexts": required,
        "missing_required_contexts": missing_required,
        "pending_required_contexts": pending_required,
        "failed_required_contexts": failed_required,
        "unknown_required_contexts": unknown_required,
        "security_findings": security,
        "incomplete_security_findings": incomplete_security,
        "collection_errors": list(collection_errors),
        "timed_out": timed_out,
        "reporting_only": True,
        "pull_request_code_executed": False,
    }


def fact_status(model, fact_id: str) -> str:
    live = model.get("live_evidence") if isinstance(model.get("live_evidence"), Mapping) else {}
    for item in live.get("facts") or []:
        if isinstance(item, Mapping) and text(item.get("id")) == fact_id:
            return text(item.get("status")) or "unavailable"
    return "unavailable"


def render_comment(snapshot, review_model=None) -> str:
    model = review_model or {}
    title = {
        "ready": "✅ Ready for human review",
        "blocked": "⛔ Blocked",
        "waiting_or_unknown": "⏳ Incomplete evidence — NO-SHIP",
        "stale": "⚠️ Stale evidence — publication refused",
    }.get(
        snapshot["review_state"],
        snapshot["review_state"].replace("_", " ").title(),
    )
    required = "✅ Clear"
    if snapshot["missing_required_contexts"]:
        required = "❌ Missing"
    elif snapshot["pending_required_contexts"]:
        required = "⏳ Pending"
    elif snapshot["failed_required_contexts"]:
        required = "❌ Failed"
    elif snapshot["unknown_required_contexts"]:
        required = "⚠️ Unknown"
    security = "✅ Clear"
    if snapshot["security_findings"]:
        security = f"❌ {len(snapshot['security_findings'])} current finding(s)"
    elif snapshot["incomplete_security_findings"]:
        security = "⚠️ Incomplete provenance"
    labels = {
        "clear": "✅ Clear",
        "attention": "⚠️ Needs attention",
        "unavailable": "➖ Unavailable",
    }
    workflow_state = "✅ Terminal" if snapshot["snapshot_status"] == "terminal" else "⚠️ Incomplete"
    decision = model.get("decision") if isinstance(model.get("decision"), Mapping) else {}
    risk = text(decision.get("risk_surface")) or "not_collected"
    lines = [
        "### SDET Quality Gate",
        "",
        (
            "> Terminal publisher evaluated exact head "
            f"`{snapshot['head_sha']}` using a stable workflow/check snapshot."
        ),
        "",
        f"## {title}",
        "",
        "| Review signal | Result |",
        "|---|---|",
        f"| Exact head | `{snapshot['head_sha'][:12]}` |",
        f"| Workflow snapshot | {workflow_state} |",
        f"| Required checks | {required} |",
        f"| Failed workflows | `{len(snapshot['failed_workflows'])}` |",
        f"| Pending workflows | `{len(snapshot['pending_workflows'])}` |",
        f"| Security | {security} |",
        (
            "| Runtime proof | "
            f"{labels.get(fact_status(model, 'runtime_proof'), '➖ Unavailable')} |"
        ),
        (
            "| Artifact integrity | "
            f"{labels.get(fact_status(model, 'artifact_inventory'), '➖ Unavailable')} |"
        ),
        f"| Risk focus | {inline(risk).replace('_', ' ').title()} |",
        "",
    ]
    if snapshot["failed_workflows"]:
        lines += ["### Failed workflows", ""]
        for item in snapshot["failed_workflows"]:
            step = inline(item["step_name"])
            if item["step_number"]:
                step += f" (step {item['step_number']})"
            failure = inline(item["first_failure"]) or "First failure line not captured"
            lines.append(
                f"- {trusted_link(item['workflow_name'], item['workflow_url'])} — "
                f"{trusted_link(item['job_name'], item['job_url'])} — "
                f"`{step}` — {failure}"
            )
        lines.append("")
    if snapshot["security_findings"]:
        lines += ["### Security findings", ""]
        for item in snapshot["security_findings"]:
            location = f"{item['path']}:{item['start_line']}"
            lines.append(
                f"- {trusted_link('Alert ' + str(item['number']), item['url'])} — "
                f"`{item['rule_id']}` — `{location}` — {inline(item['message'])}"
            )
        lines.append("")
    missing = [
        f"{trusted_link(item['name'], item['url'])} — `pending`"
        for item in snapshot["pending_workflows"]
    ]
    missing += [
        f"`{item['name']}` — `missing required context`"
        for item in snapshot["missing_required_contexts"]
    ]
    missing += [
        f"`{item['name']}` — `pending required context`"
        for item in snapshot["pending_required_contexts"]
    ]
    for item in snapshot["incomplete_security_findings"]:
        missing.append(
            f"`security alert {item.get('number') or 'unknown'}` — "
            "incomplete provenance: " + ", ".join(item.get("evidence_gaps") or [])
        )
    missing += [f"`collection error` — {inline(item)}" for item in snapshot["collection_errors"]]
    if missing:
        lines += [
            "### Pending or missing evidence",
            "",
            *[f"- {item}" for item in missing],
            "",
        ]
    lines += [
        (
            "> 🔒 Authority: `reporting only`. This snapshot does not authorize "
            "merge, patch application, finding disposition, or semantic-equivalence claims."
        ),
        "",
        "`merge_authorized=false`",
        "",
    ]
    return "\n".join(lines)
