from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.maintenance.policy_decision_history.v1"


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


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        item = json.loads(raw)
        if isinstance(item, dict):
            records.append(item)
    return records


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _decision_key(item: dict[str, Any]) -> str:
    return (
        _text(item.get("memory_lookup_key"))
        or _text(item.get("source_key"))
        or f"{_text(item.get('source'))}:{_text(item.get('title'))}"
    )


def _memory_rows_by_key(memory_context: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    if not memory_context:
        return rows
    for item in _as_list(memory_context.get("decisions")):
        row = _as_dict(item)
        key = _decision_key(row)
        if key:
            rows[key] = row
    return rows


def _compact_context(row: dict[str, Any], name: str) -> dict[str, Any]:
    context = _as_dict(row.get(name))
    if not context:
        return {}
    return {
        key: context[key]
        for key in sorted(context)
        if key
        in {
            "matched",
            "context_type",
            "seen_count",
            "decisions_by_type",
            "job",
            "severity",
            "finding_id",
            "fix_type",
            "code",
            "remediation_attempts",
            "remediation_successes",
            "commit_pushes",
            "latest_remediation_status",
            "summary",
            "policy_hint",
        }
    }


def _compact_decision(
    decision: dict[str, Any],
    *,
    memory_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    memory = memory_row or {}
    key = _decision_key(decision)
    return {
        "rank": _as_int(decision.get("rank")),
        "decision": _text(decision.get("decision")),
        "priority": _as_int(decision.get("priority")),
        "source": _text(decision.get("source")),
        "severity": _text(decision.get("severity")),
        "title": _text(decision.get("title")),
        "action": _text(decision.get("action")),
        "reason": _text(decision.get("reason")),
        "adaptive_context": _text(decision.get("adaptive_context")),
        "source_key": _text(decision.get("source_key")) or key,
        "memory_lookup_key": key,
        "confidence": _text(decision.get("confidence")),
        "automation_risk": _text(decision.get("automation_risk")),
        "review_risk": _text(decision.get("review_risk")),
        "release_risk": _text(decision.get("release_risk")),
        "policy_basis": list(_as_list(decision.get("policy_basis"))),
        "memory_enriched": bool(memory.get("memory_enriched", False)),
        "history_context": _compact_context(memory, "history_context"),
        "safe_fix_context": _compact_context(memory, "safe_fix_context"),
        "annotation_context": _compact_context(memory, "annotation_context"),
    }


def _record_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def build_history_record(
    policy_decisions: dict[str, Any],
    *,
    memory_context: dict[str, Any] | None = None,
    recorded_at_utc: str | None = None,
    run_id: str = "",
) -> dict[str, Any]:
    memory_by_key = _memory_rows_by_key(memory_context)
    decisions = [
        _compact_decision(row, memory_row=memory_by_key.get(_decision_key(row)))
        for row in _as_list(policy_decisions.get("decisions"))
        if _as_dict(row)
    ]

    stable = {
        "run_id": _text(run_id),
        "decision": _text(policy_decisions.get("decision")) or "NO_ACTION",
        "release_blocking": bool(policy_decisions.get("release_blocking", False)),
        "top_action": _text(policy_decisions.get("top_action")),
        "decisions": decisions,
        "memory_enriched_count": _as_int((memory_context or {}).get("memory_enriched_count")),
        "repeated_signal_count": _as_int((memory_context or {}).get("repeated_signal_count")),
    }

    record_id = _record_hash(stable)
    return {
        "schema_version": SCHEMA_VERSION,
        "record_id": record_id,
        "recorded_at_utc": recorded_at_utc or _utc_now(),
        "run_id": _text(run_id),
        "decision": stable["decision"],
        "ok": bool(policy_decisions.get("ok", True)),
        "release_blocking": stable["release_blocking"],
        "automation_allowed": bool(policy_decisions.get("automation_allowed", False)),
        "decision_count": len(decisions),
        "memory_aware": bool((memory_context or {}).get("memory_aware", False)),
        "memory_enriched_count": stable["memory_enriched_count"],
        "repeated_signal_count": stable["repeated_signal_count"],
        "top_action": stable["top_action"],
        "top_reason": _text(policy_decisions.get("top_reason")),
        "top_adaptive_context": _text(policy_decisions.get("top_adaptive_context")),
        "top_memory_context": _text((memory_context or {}).get("top_memory_context")),
        "decisions": decisions,
    }


def append_history_record(path: Path, record: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = _read_jsonl(path)
    record_id = _text(record.get("record_id"))
    existing_ids = {_text(item.get("record_id")) for item in existing}

    appended = False
    if record_id not in existing_ids:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        appended = True
        existing.append(record)

    return {
        "schema_version": "sdetkit.maintenance.policy_decision_history_append.v1",
        "ok": True,
        "path": path.as_posix(),
        "record_id": record_id,
        "appended": appended,
        "history_count": len(existing),
        "decision": _text(record.get("decision")) or "NO_ACTION",
        "release_blocking": bool(record.get("release_blocking", False)),
        "decision_count": _as_int(record.get("decision_count")),
        "memory_enriched_count": _as_int(record.get("memory_enriched_count")),
        "repeated_signal_count": _as_int(record.get("repeated_signal_count")),
    }


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Maintenance policy decision history",
        "",
        f"- appended: **{summary.get('appended', False)}**",
        f"- history records: **{summary.get('history_count', 0)}**",
        f"- decision: **{summary.get('decision', 'NO_ACTION')}**",
        f"- release blocking: **{summary.get('release_blocking', False)}**",
        f"- decision items: **{summary.get('decision_count', 0)}**",
        f"- memory enriched: **{summary.get('memory_enriched_count', 0)}**",
        f"- repeated signals: **{summary.get('repeated_signal_count', 0)}**",
        f"- record id: `{summary.get('record_id', '')}`",
        f"- path: `{summary.get('path', '')}`",
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.maintenance_policy_decision_history")
    parser.add_argument("--policy-decisions-json", required=True)
    parser.add_argument("--memory-context-json")
    parser.add_argument("--history-jsonl", required=True)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--out-json")
    parser.add_argument("--out-md")
    parser.add_argument("--format", choices=["json", "md"], default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        record = build_history_record(
            _read_json(args.policy_decisions_json) or {},
            memory_context=_read_json(args.memory_context_json),
            run_id=args.run_id,
        )
        summary = append_history_record(Path(args.history_jsonl), record)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    json_text = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    md_text = render_markdown(summary)

    if args.out_json:
        Path(args.out_json).write_text(json_text, encoding="utf-8")
    if args.out_md:
        Path(args.out_md).write_text(md_text, encoding="utf-8")

    print(json_text if args.format == "json" else md_text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
