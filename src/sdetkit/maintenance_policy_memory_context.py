from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.maintenance.policy_memory_context.v1"


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


def _read_json(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _read_jsonl(path: str | None) -> list[dict[str, Any]]:
    if not path:
        return []
    records: list[dict[str, Any]] = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        item = json.loads(raw)
        if isinstance(item, dict):
            records.append(item)
    return records


def _decision_key(item: dict[str, Any]) -> str:
    return (
        _text(item.get("memory_lookup_key"))
        or _text(item.get("source_key"))
        or f"{_text(item.get('source'))}:{_text(item.get('title'))}"
    )


def _safe_fix_group_key(group: dict[str, Any]) -> str:
    return f"safe-fix:{_text(group.get('fix_type'))}:{_text(group.get('code'))}"


def _safe_fix_context(
    decision: dict[str, Any], safe_fix_rollup: dict[str, Any] | None
) -> dict[str, Any]:
    key = _decision_key(decision)
    if not safe_fix_rollup or not key.startswith("safe-fix:"):
        return {}

    for group in _as_list(safe_fix_rollup.get("groups")):
        row = _as_dict(group)
        group_key = _safe_fix_group_key(row)
        if not key.startswith(group_key):
            continue

        attempts = _as_int(row.get("remediation_attempts"))
        successes = _as_int(row.get("remediation_successes"))
        pushes = _as_int(row.get("commit_pushes"))
        latest = _text(row.get("latest_remediation_status")) or "unknown"
        return {
            "matched": True,
            "context_type": "safe_fix_memory",
            "fix_type": _text(row.get("fix_type")),
            "code": _text(row.get("code")),
            "remediation_attempts": attempts,
            "remediation_successes": successes,
            "commit_pushes": pushes,
            "latest_remediation_status": latest,
            "summary": (
                f"Safe-fix memory shows {successes}/{attempts} remediation successes, "
                f"{pushes} commit pushes, latest status `{latest}`."
            ),
            "policy_hint": (
                "Keep REVIEW_REQUIRED until safe-fix outcomes are consistently successful."
                if attempts and successes < attempts
                else "Safe-fix memory is stable enough to keep observing before policy expansion."
            ),
        }

    return {}


def _annotation_finding_key(finding: dict[str, Any]) -> str:
    finding_id = _text(finding.get("id"))
    job = _text(finding.get("job")) or "unknown"
    if "node20" in finding_id or "node20" in finding_id.replace("_", ""):
        short = "node20"
    elif "python_version" in finding_id or "python-version" in finding_id:
        short = "python-version"
    else:
        short = finding_id
    return f"annotation:{short}:{job}"


def _annotation_context(
    decision: dict[str, Any],
    annotation_report: dict[str, Any] | None,
) -> dict[str, Any]:
    key = _decision_key(decision)
    if not annotation_report or not key.startswith("annotation:"):
        return {}

    annotation = _as_dict(annotation_report.get("annotation_hygiene"))
    for finding in _as_list(annotation.get("findings")):
        row = _as_dict(finding)
        finding_key = _annotation_finding_key(row)
        if finding_key != key:
            continue

        severity = _text(row.get("severity")) or "unknown"
        job = _text(row.get("job")) or "unknown"
        recommendation = _text(row.get("recommendation"))
        return {
            "matched": True,
            "context_type": "annotation_hygiene",
            "finding_id": _text(row.get("id")),
            "job": job,
            "severity": severity,
            "evidence": _text(row.get("evidence")),
            "recommendation": recommendation,
            "summary": (
                f"Annotation memory matched `{row.get('id')}` for job `{job}` "
                f"with severity `{severity}`."
            ),
            "policy_hint": (
                "Track as workflow hygiene unless repeated history later shows release impact."
            ),
        }

    return {}


def _history_records_by_key(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    for record in records:
        payload = _as_dict(record)
        for decision in _as_list(payload.get("decisions")):
            row = _as_dict(decision)
            key = _decision_key(row)
            if not key:
                continue
            bucket = by_key.setdefault(
                key,
                {
                    "seen_count": 0,
                    "decisions_by_type": {},
                    "last_decision": "",
                    "last_title": "",
                },
            )
            bucket["seen_count"] += 1
            decision_name = _text(row.get("decision")) or "UNKNOWN"
            counts = _as_dict(bucket.get("decisions_by_type"))
            counts[decision_name] = _as_int(counts.get(decision_name)) + 1
            bucket["decisions_by_type"] = counts
            bucket["last_decision"] = decision_name
            bucket["last_title"] = _text(row.get("title"))
    return by_key


def _history_context(
    decision: dict[str, Any], history: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    key = _decision_key(decision)
    row = _as_dict(history.get(key))
    if not row:
        return {
            "matched": False,
            "context_type": "history",
            "seen_count": 0,
            "summary": "No prior policy-decision history matched this signal.",
            "policy_hint": "Treat this as a first observation until more history exists.",
        }

    seen = _as_int(row.get("seen_count"))
    return {
        "matched": True,
        "context_type": "history",
        "seen_count": seen,
        "decisions_by_type": _as_dict(row.get("decisions_by_type")),
        "last_decision": _text(row.get("last_decision")),
        "last_title": _text(row.get("last_title")),
        "summary": f"This signal has appeared {seen} time(s) in prior policy-decision history.",
        "policy_hint": (
            "Escalate recurrence review if the same non-green decision keeps appearing."
            if seen >= 3
            else "Keep collecting history before changing policy behavior."
        ),
    }


def build_policy_memory_context(
    policy_decisions: dict[str, Any],
    *,
    safe_fix_rollup: dict[str, Any] | None = None,
    annotation_report: dict[str, Any] | None = None,
    history_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    history = _history_records_by_key(history_records or [])
    contextual_decisions: list[dict[str, Any]] = []

    for decision in _as_list(policy_decisions.get("decisions")):
        row = _as_dict(decision)
        if not row:
            continue
        safe_context = _safe_fix_context(row, safe_fix_rollup)
        annotation_context = _annotation_context(row, annotation_report)
        history_context = _history_context(row, history)
        context_sources = [
            source
            for source in [
                safe_context.get("context_type") if safe_context else "",
                annotation_context.get("context_type") if annotation_context else "",
                history_context.get("context_type") if history_context else "",
            ]
            if source
        ]
        contextual_decisions.append(
            {
                **row,
                "memory_context_sources": context_sources,
                "safe_fix_context": safe_context,
                "annotation_context": annotation_context,
                "history_context": history_context,
                "memory_enriched": bool(
                    safe_context or annotation_context or history_context.get("matched")
                ),
            }
        )

    enriched_count = sum(1 for item in contextual_decisions if item.get("memory_enriched"))
    repeated_count = sum(
        1
        for item in contextual_decisions
        if _as_int(_as_dict(item.get("history_context")).get("seen_count")) >= 3
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "ok": policy_decisions.get("ok", True),
        "decision": policy_decisions.get("decision", "NO_ACTION"),
        "release_blocking": policy_decisions.get("release_blocking", False),
        "automation_allowed": False,
        "memory_aware": True,
        "decision_count": len(contextual_decisions),
        "memory_enriched_count": enriched_count,
        "repeated_signal_count": repeated_count,
        "top_action": policy_decisions.get("top_action", ""),
        "top_memory_context": (
            _as_dict(contextual_decisions[0].get("history_context")).get("summary", "")
            if contextual_decisions
            else ""
        ),
        "decisions": contextual_decisions,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Maintenance policy memory context",
        "",
        f"- overall decision: **{payload.get('decision', 'NO_ACTION')}**",
        f"- release blocking: **{payload.get('release_blocking', False)}**",
        f"- memory aware: **{payload.get('memory_aware', False)}**",
        f"- decisions: **{payload.get('decision_count', 0)}**",
        f"- memory enriched: **{payload.get('memory_enriched_count', 0)}**",
        f"- repeated signals: **{payload.get('repeated_signal_count', 0)}**",
    ]

    decisions = _as_list(payload.get("decisions"))
    if not decisions:
        lines.extend(["", "No policy decisions were available for memory context."])
        return "\n".join(lines) + "\n"

    lines.extend(["", "## Context highlights", ""])
    for item in decisions[:8]:
        row = _as_dict(item)
        history = _as_dict(row.get("history_context"))
        safe = _as_dict(row.get("safe_fix_context"))
        annotation = _as_dict(row.get("annotation_context"))
        highlights = [
            _text(history.get("summary")),
            _text(safe.get("summary")),
            _text(annotation.get("summary")),
        ]
        highlights = [item for item in highlights if item]
        lines.append(
            f"- **{row.get('decision', 'UNKNOWN')}** `{row.get('memory_lookup_key', '')}`: "
            + (" ".join(highlights) if highlights else "No matching memory context.")
        )

    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.maintenance_policy_memory_context")
    parser.add_argument("--policy-decisions-json", required=True)
    parser.add_argument("--safe-fix-rollup-json")
    parser.add_argument("--annotation-report-json")
    parser.add_argument("--history-jsonl")
    parser.add_argument("--out-json")
    parser.add_argument("--out-md")
    parser.add_argument("--format", choices=["json", "md"], default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = build_policy_memory_context(
            _read_json(args.policy_decisions_json) or {},
            safe_fix_rollup=_read_json(args.safe_fix_rollup_json),
            annotation_report=_read_json(args.annotation_report_json),
            history_records=_read_jsonl(args.history_jsonl),
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
    return 1 if payload.get("release_blocking", False) else 0


if __name__ == "__main__":
    raise SystemExit(main())
