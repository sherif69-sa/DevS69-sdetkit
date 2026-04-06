from __future__ import annotations

import csv
import html
import io
import json
from collections import Counter
from pathlib import Path
from typing import Any

from sdetkit.atomicio import atomic_write_text

from ..bools import coerce_bool


def _sort_key(item: dict[str, Any]) -> tuple[str, str]:
    return (str(item.get("captured_at", "")), str(item.get("hash", "")))


def _load_history(history_dir: Path) -> list[dict[str, Any]]:
    if not history_dir.exists():
        return []
    rows: list[dict[str, Any]] = []
    for file in sorted(history_dir.glob("*.json")):
        try:
            loaded = json.loads(file.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if not isinstance(loaded, dict):
            continue
        row = dict(loaded)
        row.setdefault("hash", file.stem)
        row.setdefault("captured_at", "")
        row.setdefault("status", "")
        row.setdefault("task", "")
        rows.append(row)
    rows.sort(key=_sort_key)
    return rows


def _extract_template_id(task: str) -> str | None:
    stripped = task.strip()
    if stripped.startswith("template:"):
        return stripped.split(":", 1)[1].strip() or None
    if stripped.startswith("template "):
        return stripped.split(" ", 1)[1].strip() or None
    return None


def _counter_to_rows(counter: Counter[str], *, limit: int = 10) -> list[dict[str, Any]]:
    pairs = sorted(counter.items(), key=lambda x: (-x[1], x[0]))[:limit]
    return [{"name": name, "count": count} for name, count in pairs]


def summarize_history(history_dir: Path) -> dict[str, Any]:
    runs = _load_history(history_dir)
    total = len(runs)
    success = sum(1 for item in runs if item.get("status") == "ok")
    failed = total - success
    success_rate = round((success / total) * 100.0, 2) if total else 0.0

    template_counter: Counter[str] = Counter()
    action_counter: Counter[str] = Counter()
    worker_counter: Counter[str] = Counter()
    task_family_counter: Counter[str] = Counter()
    failure_tasks: list[dict[str, Any]] = []
    approvals = {
        "approved": 0,
        "denied": 0,
        "failed_after_approval": 0,
    }

    for run in runs:
        task = str(run.get("task", ""))
        template_id = _extract_template_id(task)
        if template_id:
            template_counter[template_id] += 1
            task_family_counter["template"] += 1
        elif task.strip().startswith("action "):
            task_family_counter["action"] += 1
        elif "blueprint" in task.lower() or "umbrella" in task.lower():
            task_family_counter["blueprint"] += 1
        elif "audit" in task.lower():
            task_family_counter["audit"] += 1
        else:
            task_family_counter["other"] += 1
        for action in run.get("actions", []):
            if isinstance(action, dict):
                action_counter[str(action.get("action", "unknown"))] += 1
                worker_counter[str(action.get("worker_id", "unknown"))] += 1
                if coerce_bool(action.get("denied"), default=False):
                    approvals["denied"] += 1
                elif coerce_bool(action.get("approved"), default=False):
                    approvals["approved"] += 1
                    if not coerce_bool(action.get("ok"), default=False):
                        approvals["failed_after_approval"] += 1
        if str(run.get("status", "")) != "ok":
            failure_tasks.append(
                {
                    "hash": str(run.get("hash", "")),
                    "captured_at": str(run.get("captured_at", "")),
                    "task": task,
                    "status": str(run.get("status", "")),
                }
            )

    failure_tasks.sort(key=lambda x: (x["captured_at"], x["hash"]))
    latest_status = str(runs[-1].get("status", "")) if runs else "unknown"
    success_streak = 0
    for run in reversed(runs):
        if str(run.get("status", "")) != "ok":
            break
        success_streak += 1

    return {
        "runs": {
            "total": total,
            "success": success,
            "failed": failed,
            "success_rate": success_rate,
            "latest_status": latest_status,
            "success_streak": success_streak,
        },
        "top_templates": _counter_to_rows(template_counter),
        "top_actions": _counter_to_rows(action_counter),
        "workers": _counter_to_rows(worker_counter),
        "task_families": _counter_to_rows(task_family_counter),
        "approvals": approvals,
        "failures": failure_tasks,
        "records": [
            {
                "hash": str(run.get("hash", "")),
                "captured_at": str(run.get("captured_at", "")),
                "status": str(run.get("status", "")),
                "task": str(run.get("task", "")),
                "action_count": len(run.get("actions", []))
                if isinstance(run.get("actions"), list)
                else 0,
            }
            for run in runs
        ],
    }


def render_markdown(summary: dict[str, Any]) -> str:
    runs = summary["runs"]
    lines = [
        "# Agent dashboard summary",
        "",
        f"- Total runs: {runs['total']}",
        f"- Successful runs: {runs['success']}",
        f"- Failed runs: {runs['failed']}",
        f"- Success rate: {runs['success_rate']:.2f}%",
        f"- Latest status: {runs['latest_status']}",
        f"- Success streak: {runs['success_streak']}",
        "",
        "## Top templates",
    ]
    templates = summary.get("top_templates", [])
    if templates:
        for item in templates:
            lines.append(f"- `{item['name']}`: {item['count']}")
    else:
        lines.append("- none")

    lines.extend(["", "## Top actions"])
    actions = summary.get("top_actions", [])
    if actions:
        for item in actions:
            lines.append(f"- `{item['name']}`: {item['count']}")
    else:
        lines.append("- none")

    lines.extend(["", "## Worker utilization"])
    workers = summary.get("workers", [])
    if workers:
        for item in workers:
            lines.append(f"- `{item['name']}`: {item['count']}")
    else:
        lines.append("- none")

    lines.extend(["", "## Task families"])
    task_families = summary.get("task_families", [])
    if task_families:
        for item in task_families:
            lines.append(f"- `{item['name']}`: {item['count']}")
    else:
        lines.append("- none")

    approvals = summary.get("approvals", {})
    lines.extend(
        [
            "",
            "## Approvals",
            f"- approved actions: {approvals.get('approved', 0)}",
            f"- denied actions: {approvals.get('denied', 0)}",
            f"- failed after approval: {approvals.get('failed_after_approval', 0)}",
        ]
    )

    lines.extend(["", "## Failed runs"])
    failures = summary.get("failures", [])
    if failures:
        for item in failures:
            lines.append(
                f"- `{item['captured_at']}` `{item['hash']}` `{item['status']}` task={item['task']}"
            )
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def render_html(summary: dict[str, Any]) -> str:
    runs = summary["runs"]

    def _table(rows: list[dict[str, Any]], left: str, right: str) -> str:
        body = "".join(
            f"<tr><td>{html.escape(str(item[left]))}</td><td>{item[right]}</td></tr>"
            for item in rows
        )
        if not body:
            body = "<tr><td colspan='2'>none</td></tr>"
        return (
            "<table><thead><tr><th>Name</th><th>Count</th></tr></thead>"
            f"<tbody>{body}</tbody></table>"
        )

    failure_rows = "".join(
        (
            "<tr>"
            f"<td>{html.escape(item['captured_at'])}</td>"
            f"<td>{html.escape(item['hash'])}</td>"
            f"<td>{html.escape(item['status'])}</td>"
            f"<td>{html.escape(item['task'])}</td>"
            "</tr>"
        )
        for item in summary.get("failures", [])
    )
    if not failure_rows:
        failure_rows = "<tr><td colspan='4'>none</td></tr>"

    return "".join(
        [
            "<html><head><meta charset='utf-8'><title>sdetkit agent dashboard</title></head><body>",
            "<h1>sdetkit agent dashboard</h1>",
            "<h2>Runs</h2>",
            f"<p>Total runs: {runs['total']}</p>",
            f"<p>Successful runs: {runs['success']}</p>",
            f"<p>Failed runs: {runs['failed']}</p>",
            f"<p>Success rate: {runs['success_rate']:.2f}%</p>",
            f"<p>Latest status: {html.escape(str(runs['latest_status']))}</p>",
            f"<p>Success streak: {runs['success_streak']}</p>",
            "<h2>Top templates</h2>",
            _table(summary.get("top_templates", []), "name", "count"),
            "<h2>Top actions</h2>",
            _table(summary.get("top_actions", []), "name", "count"),
            "<h2>Worker utilization</h2>",
            _table(summary.get("workers", []), "name", "count"),
            "<h2>Task families</h2>",
            _table(summary.get("task_families", []), "name", "count"),
            "<h2>Approvals</h2>",
            (
                "<table><thead><tr><th>Metric</th><th>Count</th></tr></thead><tbody>"
                f"<tr><td>approved</td><td>{int(summary.get('approvals', {}).get('approved', 0))}</td></tr>"
                f"<tr><td>denied</td><td>{int(summary.get('approvals', {}).get('denied', 0))}</td></tr>"
                f"<tr><td>failed_after_approval</td><td>{int(summary.get('approvals', {}).get('failed_after_approval', 0))}</td></tr>"
                "</tbody></table>"
            ),
            "<h2>Failed runs</h2>",
            (
                "<table><thead><tr><th>Captured at</th><th>Hash</th><th>Status</th><th>Task</th></tr></thead>"
                f"<tbody>{failure_rows}</tbody></table>"
            ),
            "</body></html>\n",
        ]
    )


def render_csv(summary: dict[str, Any]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["captured_at", "hash", "status", "task", "action_count"])
    for item in summary.get("records", []):
        writer.writerow(
            [
                item.get("captured_at", ""),
                item.get("hash", ""),
                item.get("status", ""),
                item.get("task", ""),
                item.get("action_count", 0),
            ]
        )
    return buf.getvalue()


def build_dashboard(
    *,
    history_dir: Path,
    output: Path,
    fmt: str,
    summary_output: Path | None = None,
) -> dict[str, Any]:
    summary = summarize_history(history_dir)

    if fmt == "json":
        body = json.dumps(summary, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    elif fmt == "md":
        body = render_markdown(summary)
    elif fmt == "csv":
        body = render_csv(summary)
    else:
        body = render_html(summary)
    atomic_write_text(output, body)

    markdown_path: str | None = None
    if fmt == "html":
        md_target = summary_output or output.with_suffix(".md")
        atomic_write_text(md_target, render_markdown(summary))
        markdown_path = md_target.as_posix()

    return {
        "status": "ok",
        "output": output.as_posix(),
        "format": fmt,
        "markdown_summary": markdown_path,
        "runs": summary["runs"],
    }


def export_history_summary(*, history_dir: Path, output: Path, fmt: str) -> dict[str, Any]:
    summary = summarize_history(history_dir)
    if fmt == "csv":
        content = render_csv(summary)
    else:
        content = (
            json.dumps(summary.get("records", []), ensure_ascii=True, sort_keys=True, indent=2)
            + "\n"
        )
    atomic_write_text(output, content)
    return {
        "status": "ok",
        "output": output.as_posix(),
        "format": fmt,
        "count": len(summary.get("records", [])),
    }
