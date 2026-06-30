from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping, Sequence

SUCCESS = {"success", "neutral", "skipped"}
BLOCKING = {"failure", "cancelled", "timed_out", "action_required", "startup_failure"}
TERMINAL = SUCCESS | BLOCKING | {"stale"}
PUBLISHERS = {"PR Quality Publisher", "PR Quality Terminal Publisher"}


def text(value: object) -> str:
    return str(value or "").strip()


def inline(value: object) -> str:
    return text(value).replace("\n", " ").replace("|", "\\|")


def number(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def canonical(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text(value).lower()).strip("-")


def conclusion(status: object, value: object) -> str:
    rendered = text(value).lower()
    if text(status).lower() != "completed" or not rendered:
        return "pending"
    return rendered if rendered in TERMINAL else "unknown"


def trusted_link(label: object, url: object) -> str:
    label_text, url_text = inline(label) or "unknown", text(url)
    if url_text.startswith("https://github.com/"):
        return f"[{label_text}]({url_text})"
    return f"`{label_text}`"


def latest_runs(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for raw in rows:
        name = text(raw.get("name")) or "Unnamed workflow"
        if name in PUBLISHERS:
            continue
        workflow_id = number(raw.get("workflow_id"))
        key = str(workflow_id) if workflow_id else canonical(name)
        row = {
            "id": number(raw.get("id")),
            "workflow_id": workflow_id,
            "name": name,
            "status": text(raw.get("status")) or "unknown",
            "conclusion": conclusion(raw.get("status"), raw.get("conclusion")),
            "run_attempt": max(number(raw.get("run_attempt")), 1),
            "run_number": number(raw.get("run_number")),
            "url": text(raw.get("html_url")),
        }
        previous = selected.get(key)
        rank = row["run_attempt"], row["run_number"], row["id"]
        old_rank = (
            (previous["run_attempt"], previous["run_number"], previous["id"])
            if previous
            else (-1, -1, -1)
        )
        if rank >= old_rank:
            selected[key] = row
    return sorted(
        selected.values(), key=lambda item: (canonical(item["name"]), item["id"])
    )


def normalized_checks(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": number(raw.get("id")),
            "name": text(raw.get("name")) or "Unnamed check",
            "conclusion": conclusion(raw.get("status"), raw.get("conclusion")),
            "url": text(raw.get("details_url")),
        }
        for raw in rows
    ]


def normalized_statuses(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    mapping = {
        "success": "success",
        "failure": "failure",
        "error": "failure",
        "pending": "pending",
    }
    return [
        {
            "id": number(raw.get("id")),
            "name": text(raw.get("context")) or "Unnamed status",
            "conclusion": mapping.get(text(raw.get("state")).lower(), "unknown"),
            "url": text(raw.get("target_url")),
        }
        for raw in rows
    ]


def required_rows(contexts, runs, checks, statuses):
    candidates: dict[str, list[dict[str, Any]]] = {}
    for source, rows in (
        ("workflow", runs),
        ("check_run", checks),
        ("status", statuses),
    ):
        for row in rows:
            candidates.setdefault(canonical(row["name"]), []).append(
                {
                    "source": source,
                    "name": row["name"],
                    "conclusion": row["conclusion"],
                    "url": row["url"],
                }
            )
    result = []
    for context in contexts:
        matches = candidates.get(canonical(context), [])
        states = {item["conclusion"] for item in matches}
        if not matches:
            state = "missing"
        elif "pending" in states:
            state = "pending"
        elif states and states.issubset(SUCCESS):
            state = "success"
        elif states & BLOCKING:
            state = "failure"
        else:
            state = "unknown"
        result.append({"name": context, "state": state, "matches": matches})
    return result


def signature(runs, required):
    payload = {
        "runs": [
            {
                "id": row["id"],
                "name": row["name"],
                "status": row["status"],
                "conclusion": row["conclusion"],
                "attempt": row["run_attempt"],
            }
            for row in runs
        ],
        "required": [{"name": row["name"], "state": row["state"]} for row in required],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
