from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.maintenance.priority_rollup.v1"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _text(value: Any) -> str:
    return str(value or "").strip()


def _append_item(
    items: list[dict[str, Any]],
    *,
    priority: int,
    source: str,
    title: str,
    reason: str,
    action: str,
    severity: str,
    key: str,
) -> None:
    items.append(
        {
            "priority": priority,
            "source": source,
            "title": title,
            "reason": reason,
            "action": action,
            "severity": severity,
            "key": key,
        }
    )


def _maintenance_items(report: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    checks = _as_dict(report.get("checks"))
    for name in sorted(checks):
        check = _as_dict(checks.get(name))
        if check.get("ok") is False:
            _append_item(
                items,
                priority=1,
                source="maintenance",
                title=f"Maintenance check failed: {name}",
                reason=_text(check.get("summary")) or "Maintenance check reported a failure.",
                action=f"Review maintenance check `{name}` and run its suggested action.",
                severity="error",
                key=f"maintenance:{name}",
            )

        for action in _as_list(check.get("actions"))[:3]:
            row = _as_dict(action)
            title = _text(row.get("title"))
            if not title:
                continue
            _append_item(
                items,
                priority=3 if check.get("ok") else 2,
                source="maintenance_action",
                title=title,
                reason=f"Suggested by maintenance check `{name}`.",
                action=title,
                severity="warning" if not check.get("ok") else "info",
                key=f"maintenance-action:{name}:{row.get('id', title)}",
            )
    return items


def _annotation_items(report: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    annotation = _as_dict(report.get("annotation_hygiene"))
    findings = _as_list(annotation.get("findings"))
    for finding in findings:
        row = _as_dict(finding)
        severity = _text(row.get("severity")) or "info"
        if severity == "warning":
            priority = 2
        elif severity == "notice":
            priority = 4
        else:
            priority = 5
        title = _text(row.get("title")) or "GitHub Actions annotation hygiene finding"
        recommendation = _text(row.get("recommendation")) or "Review GitHub Actions annotation."
        _append_item(
            items,
            priority=priority,
            source="annotation_hygiene",
            title=title,
            reason=_text(row.get("evidence")) or "Annotation hygiene finding was reported.",
            action=recommendation,
            severity=severity,
            key=f"annotation:{row.get('id', title)}:{row.get('job', 'unknown')}",
        )
    return items


def _safe_fix_items(report: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for group in _as_list(report.get("groups")):
        row = _as_dict(group)
        fix_type = _text(row.get("fix_type")) or "unknown"
        code = _text(row.get("code")) or "UNKNOWN"
        attempts = _as_int(row.get("remediation_attempts"))
        successes = _as_int(row.get("remediation_successes"))
        pushes = _as_int(row.get("commit_pushes"))
        latest_status = _text(row.get("latest_remediation_status")) or "unknown"

        if attempts and successes < attempts:
            _append_item(
                items,
                priority=2,
                source="safe_fix_rollup",
                title=f"Safe fix needs review: {fix_type}",
                reason=(
                    f"{successes}/{attempts} remediation attempts succeeded for {code}; "
                    f"latest status is {latest_status}."
                ),
                action=f"Review safe-fix outcomes for `{fix_type}` before widening automation policy.",
                severity="warning",
                key=f"safe-fix:{fix_type}:{code}:remediation",
            )
        elif attempts and pushes == 0:
            _append_item(
                items,
                priority=5,
                source="safe_fix_rollup",
                title=f"Safe fix has no commit pushes yet: {fix_type}",
                reason=f"{successes}/{attempts} remediations succeeded for {code}, but no pushes were recorded.",
                action="Keep observing safe-fix outcomes before using them for commit/push policy.",
                severity="info",
                key=f"safe-fix:{fix_type}:{code}:pushes",
            )
    return items


def _dedupe_rank(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    seen: set[str] = set()
    ordered: list[dict[str, Any]] = []
    for item in sorted(
        items,
        key=lambda row: (
            _as_int(row.get("priority")),
            _text(row.get("source")),
            _text(row.get("title")),
            _text(row.get("key")),
        ),
    ):
        key = _text(item.get("key")) or f"{item.get('source')}:{item.get('title')}"
        if key in seen:
            continue
        seen.add(key)
        item["rank"] = len(ordered) + 1
        ordered.append(item)
        if len(ordered) >= limit:
            break
    return ordered


def build_priority_rollup(
    *,
    maintenance_report: dict[str, Any] | None = None,
    annotation_report: dict[str, Any] | None = None,
    safe_fix_rollup: dict[str, Any] | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    if maintenance_report:
        items.extend(_maintenance_items(maintenance_report))
    if annotation_report:
        items.extend(_annotation_items(annotation_report))
    if safe_fix_rollup:
        items.extend(_safe_fix_items(safe_fix_rollup))

    priority_queue = _dedupe_rank(items, limit)
    counts_by_priority: dict[str, int] = {}
    counts_by_source: dict[str, int] = {}
    for item in priority_queue:
        priority = str(item.get("priority", "unknown"))
        source = _text(item.get("source")) or "unknown"
        counts_by_priority[priority] = counts_by_priority.get(priority, 0) + 1
        counts_by_source[source] = counts_by_source.get(source, 0) + 1

    return {
        "schema_version": SCHEMA_VERSION,
        "ok": not any(_as_int(item.get("priority")) <= 2 for item in priority_queue),
        "queue_count": len(priority_queue),
        "counts_by_priority": dict(sorted(counts_by_priority.items())),
        "counts_by_source": dict(sorted(counts_by_source.items())),
        "top_action": _text(priority_queue[0].get("action")) if priority_queue else "",
        "priority_queue": priority_queue,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Maintenance priority rollup",
        "",
        f"- queue items: **{payload.get('queue_count', 0)}**",
        f"- top action: {payload.get('top_action') or 'No action required.'}",
    ]

    queue = _as_list(payload.get("priority_queue"))
    if not queue:
        lines.extend(["", "No prioritized maintenance follow-ups detected."])
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            "",
            "| Rank | P | Source | Severity | Title | Action |",
            "|---:|---:|---|---|---|---|",
        ]
    )
    for item in queue:
        row = _as_dict(item)
        lines.append(
            "| {rank} | {priority} | {source} | {severity} | {title} | {action} |".format(
                rank=row.get("rank", ""),
                priority=row.get("priority", ""),
                source=_text(row.get("source")).replace("|", "\\|"),
                severity=_text(row.get("severity")).replace("|", "\\|"),
                title=_text(row.get("title")).replace("|", "\\|"),
                action=_text(row.get("action")).replace("|", "\\|"),
            )
        )

    return "\n".join(lines).rstrip() + "\n"


def _read_json(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.maintenance_priority_rollup")
    parser.add_argument("--maintenance-json")
    parser.add_argument("--annotation-report-json")
    parser.add_argument("--safe-fix-rollup-json")
    parser.add_argument("--out-json")
    parser.add_argument("--out-md")
    parser.add_argument("--format", choices=["json", "md"], default="json")
    parser.add_argument("--limit", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = build_priority_rollup(
            maintenance_report=_read_json(args.maintenance_json),
            annotation_report=_read_json(args.annotation_report_json),
            safe_fix_rollup=_read_json(args.safe_fix_rollup_json),
            limit=max(1, args.limit),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    json_text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    md_text = render_markdown(payload)

    if args.out_json:
        Path(args.out_json).write_text(json_text, encoding="utf-8")
    if args.out_md:
        Path(args.out_md).write_text(md_text, encoding="utf-8")

    print(json_text if args.format == "json" else md_text, end="")
    return 1 if not payload.get("ok", False) else 0


if __name__ == "__main__":
    raise SystemExit(main())
