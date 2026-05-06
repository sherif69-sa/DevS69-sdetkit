from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.maintenance.signal_trends.v1"

DIAGNOSTIC_ONLY = True
AUTOMATION_ALLOWED = False


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


def _cell(value: Any) -> str:
    return _text(value).replace("|", "\\|")


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
    p = Path(path)
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in p.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        item = json.loads(raw)
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _history_key(item: dict[str, Any]) -> str:
    return (
        _text(item.get("memory_lookup_key"))
        or _text(item.get("source_key"))
        or f"{_text(item.get('source'))}:{_text(item.get('title'))}"
    )


def _history_counts(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    recent_records = records[-5:]
    recent_keys: set[str] = set()

    for record in recent_records:
        payload = _as_dict(record)
        for decision in _as_list(payload.get("decisions")):
            key = _history_key(_as_dict(decision))
            if key:
                recent_keys.add(key)

    for record in records:
        payload = _as_dict(record)
        for decision in _as_list(payload.get("decisions")):
            row = _as_dict(decision)
            key = _history_key(row)
            if not key:
                continue
            bucket = by_key.setdefault(
                key,
                {
                    "seen_count": 0,
                    "decision_counts": {},
                    "latest_decision": "",
                    "latest_title": "",
                    "recent_count": 0,
                },
            )
            bucket["seen_count"] = _as_int(bucket.get("seen_count")) + 1
            decision_name = _text(row.get("decision")) or "UNKNOWN"
            counts = _as_dict(bucket.get("decision_counts"))
            counts[decision_name] = _as_int(counts.get(decision_name)) + 1
            bucket["decision_counts"] = counts
            bucket["latest_decision"] = decision_name
            bucket["latest_title"] = _text(row.get("title"))

    for key in recent_keys:
        if key in by_key:
            by_key[key]["recent_count"] = _as_int(by_key[key].get("recent_count")) + 1

    return by_key


def _safe_fix_group_key(group: dict[str, Any]) -> str:
    fix_type = _text(group.get("fix_type"))
    code = _text(group.get("code"))
    if fix_type and code:
        return f"safe-fix:{fix_type}:{code}"
    if code:
        return f"diagnosis:{code}"
    return ""


def _safe_fix_context(safe_fix_rollup: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    if not safe_fix_rollup:
        return result

    for group in _as_list(safe_fix_rollup.get("groups")):
        row = _as_dict(group)
        keys = {_safe_fix_group_key(row)}
        code = _text(row.get("code"))
        if code:
            keys.add(f"diagnosis:{code}")

        context = {
            "safe_fix_attempts": _as_int(row.get("remediation_attempts")),
            "safe_fix_successes": _as_int(row.get("remediation_successes")),
            "safe_fix_pushes": _as_int(row.get("commit_pushes")),
            "latest_safe_fix_status": _text(row.get("latest_remediation_status")) or "unknown",
        }
        for key in keys:
            if key:
                result[key] = context

    return result


def _matching_safe_context(
    memory_lookup_key: str, diagnosis_class: str, contexts: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    candidates = [
        memory_lookup_key,
        f"diagnosis:{diagnosis_class}",
    ]
    for candidate in candidates:
        for key, context in contexts.items():
            if candidate.startswith(key) or key.startswith(candidate):
                return context
    return {}


def _trend(seen_count: int, recent_count: int, safe_fix_attempts: int, safe_fix_successes: int) -> str:
    if safe_fix_attempts and safe_fix_successes >= safe_fix_attempts:
        return "previously_fixed"
    if seen_count >= 3 and recent_count >= 1:
        return "recurring"
    if seen_count >= 3:
        return "repeated"
    if recent_count >= 2:
        return "worsening"
    return "new"


def _trend_confidence(seen_count: int, safe_fix_attempts: int) -> str:
    if safe_fix_attempts or seen_count >= 3:
        return "high"
    if seen_count >= 1:
        return "medium"
    return "low"


def _recommendation_impact(trend: str, safe_fix_route: str) -> str:
    if trend == "previously_fixed" and safe_fix_route in {"candidate_later", "policy_required"}:
        return "candidate_later"
    if trend in {"recurring", "repeated", "worsening"}:
        return "prioritize_review"
    return "observe"


def _trend_item(
    item: dict[str, Any],
    history: dict[str, dict[str, Any]],
    safe_contexts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    memory_key = _text(item.get("memory_lookup_key"))
    diagnosis_class = _text(item.get("diagnosis_class")) or "UNKNOWN_REVIEW_REQUIRED"
    history_row = _as_dict(history.get(memory_key))
    safe_row = _matching_safe_context(memory_key, diagnosis_class, safe_contexts)

    seen_count = _as_int(history_row.get("seen_count"))
    recent_count = _as_int(history_row.get("recent_count"))
    safe_fix_attempts = _as_int(safe_row.get("safe_fix_attempts"))
    safe_fix_successes = _as_int(safe_row.get("safe_fix_successes"))
    trend = _trend(seen_count, recent_count, safe_fix_attempts, safe_fix_successes)

    return {
        "rank": item.get("rank", ""),
        "signal": _text(item.get("signal")) or memory_key,
        "memory_lookup_key": memory_key,
        "diagnosis_class": diagnosis_class,
        "category": _text(item.get("category")),
        "risk_level": _text(item.get("risk_level")),
        "safe_fix_route": _text(item.get("safe_fix_route")),
        "proof_status": _text(item.get("proof_status")),
        "seen_count": seen_count,
        "recent_count": recent_count,
        "safe_fix_attempts": safe_fix_attempts,
        "safe_fix_successes": safe_fix_successes,
        "safe_fix_pushes": _as_int(safe_row.get("safe_fix_pushes")),
        "latest_safe_fix_status": _text(safe_row.get("latest_safe_fix_status")) or "none",
        "trend": trend,
        "trend_confidence": _trend_confidence(seen_count, safe_fix_attempts),
        "recommendation_impact": _recommendation_impact(trend, _text(item.get("safe_fix_route"))),
    }


def build_signal_trends(
    proof_checklist_payload: dict[str, Any],
    *,
    history_records: list[dict[str, Any]] | None = None,
    safe_fix_rollup: dict[str, Any] | None = None,
) -> dict[str, Any]:
    history = _history_counts(history_records or [])
    safe_contexts = _safe_fix_context(safe_fix_rollup)
    signals = [
        _trend_item(_as_dict(item), history, safe_contexts)
        for item in _as_list(proof_checklist_payload.get("items"))
        if _as_dict(item)
    ]

    counts_by_trend: dict[str, int] = {}
    counts_by_impact: dict[str, int] = {}
    for item in signals:
        trend = _text(item.get("trend")) or "unknown"
        impact = _text(item.get("recommendation_impact")) or "observe"
        counts_by_trend[trend] = counts_by_trend.get(trend, 0) + 1
        counts_by_impact[impact] = counts_by_impact.get(impact, 0) + 1

    repeated_count = sum(
        1 for item in signals if _text(item.get("trend")) in {"recurring", "repeated", "worsening"}
    )
    prior_success_count = sum(1 for item in signals if _as_int(item.get("safe_fix_successes")) > 0)

    return {
        "schema_version": SCHEMA_VERSION,
        "ok": bool(proof_checklist_payload.get("ok", True)),
        "source_schema_version": _text(proof_checklist_payload.get("schema_version")),
        "diagnostic_only": DIAGNOSTIC_ONLY,
        "automation_allowed": AUTOMATION_ALLOWED,
        "signal_count": len(signals),
        "repeated_signal_count": repeated_count,
        "prior_safe_fix_success_count": prior_success_count,
        "counts_by_trend": dict(sorted(counts_by_trend.items())),
        "counts_by_recommendation_impact": dict(sorted(counts_by_impact.items())),
        "signals": signals,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Maintenance signal trends",
        "",
        f"- diagnostic only: **{payload.get('diagnostic_only', True)}**",
        f"- automation allowed: **{payload.get('automation_allowed', False)}**",
        f"- signals: **{payload.get('signal_count', 0)}**",
        f"- repeated signals: **{payload.get('repeated_signal_count', 0)}**",
        f"- prior safe-fix successes: **{payload.get('prior_safe_fix_success_count', 0)}**",
    ]

    trends = _as_dict(payload.get("counts_by_trend"))
    if trends:
        lines.extend(["", "## Trend mix", "", "| Trend | Count |", "|---|---:|"])
        for name, count in sorted(trends.items()):
            lines.append(f"| {_cell(name)} | {count} |")

    signals = _as_list(payload.get("signals"))
    if not signals:
        lines.extend(["", "No maintenance signals were available for trend analysis."])
        return "\n".join(lines).rstrip() + "\n"

    lines.extend(
        [
            "",
            "## Signal trends",
            "",
            "| Rank | Signal | Diagnosis | Trend | Seen | Recent | Safe-fix success | Impact |",
            "|---:|---|---|---|---:|---:|---:|---|",
        ]
    )
    for item in signals:
        row = _as_dict(item)
        lines.append(
            f"| {row.get('rank', '')} | {_cell(row.get('signal'))} | "
            f"{_cell(row.get('diagnosis_class'))} | {_cell(row.get('trend'))} | "
            f"{_as_int(row.get('seen_count'))} | {_as_int(row.get('recent_count'))} | "
            f"{_as_int(row.get('safe_fix_successes'))} | "
            f"{_cell(row.get('recommendation_impact'))} |"
        )

    lines.extend(["", "## What this means", ""])
    for item in signals[:8]:
        row = _as_dict(item)
        lines.append(
            f"- **{_cell(row.get('signal'))}** is `{_cell(row.get('trend'))}` "
            f"with `{_cell(row.get('recommendation_impact'))}` impact."
        )

    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.maintenance_signal_trends")
    parser.add_argument("--proof-checklist-json", required=True)
    parser.add_argument("--history-jsonl")
    parser.add_argument("--safe-fix-rollup-json")
    parser.add_argument("--out-json")
    parser.add_argument("--out-md")
    parser.add_argument("--format", choices=["json", "md"], default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = build_signal_trends(
            _read_json(args.proof_checklist_json) or {},
            history_records=_read_jsonl(args.history_jsonl),
            safe_fix_rollup=_read_json(args.safe_fix_rollup_json),
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
