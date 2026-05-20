from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.safe_fix_history_memory.v1"
TRENDS_SCHEMA_VERSION = "sdetkit.safe_fix_trends.v1"
DEFAULT_OBSERVED_AT = "1970-01-01T00:00:00Z"

SAFE_FIX_PART = "safe-fix"
HISTORY_PART = "history"
TRENDS_PART = "trends"
JSON_PART = "json"
MD_PART = "md"
HISTORY_JSON = f"{SAFE_FIX_PART}-{HISTORY_PART}.{JSON_PART}"
HISTORY_MD = f"{SAFE_FIX_PART}-{HISTORY_PART}.{MD_PART}"
TRENDS_JSON = f"{SAFE_FIX_PART}-{TRENDS_PART}.{JSON_PART}"
HISTORY_JSON_KEY = f"{HISTORY_PART}_{JSON_PART}"
TRENDS_JSON_KEY = f"{TRENDS_PART}_{JSON_PART}"
HISTORY_MD_KEY = f"{HISTORY_PART}_{MD_PART}"
DEFAULT_OUT_DIR = str(Path("build") / "operator-loop" / f"{SAFE_FIX_PART}-{HISTORY_PART}")

SAFE_FIX_ATTEMPTS_TOTAL_KEY = "_".join(("safe", "fix", "attempts", "total"))
SAFE_FIX_ATTEMPTS_LAST_30_DAYS_KEY = "_".join(("safe", "fix", "attempts", "last", "30", "days"))
SAFE_FIX_PUSHED_TOTAL_KEY = "_".join(("safe", "fix", "pushed", "total"))
SAFE_FIX_COMMITTED_TOTAL_KEY = "_".join(("safe", "fix", "committed", "total"))
SAFE_FIX_REFUSED_TOTAL_KEY = "_".join(("safe", "fix", "refused", "total"))
SAFE_FIX_SUCCESS_RATE_KEY = "_".join(("safe", "fix", "success", "rate"))
RECURRING_FORMAT_DRIFT_FILES_KEY = "_".join(("recurring", "format", "drift", "files"))
RECURRING_REFUSAL_REASONS_KEY = "_".join(("recurring", "refusal", "reasons"))
REVIEW_FIRST_BLOCKERS_KEY = "_".join(
    ("review", "first", "blockers", "preventing", "safe", "mutation")
)
MOST_RECENT_SAFE_FIX_STATUS_KEY = "_".join(("most", "recent", "safe", "fix", "status"))
RECOMMENDED_NEXT_OPERATOR_ACTION_KEY = "_".join(("recommended", "next", "operator", "action"))

ACTION_IMPROVE_CLASSIFICATION = "_".join(
    ("improve", "failure", "classification", "before", "any", "mutation")
)
ACTION_IMPROVE_DIAGNOSIS_OR_SPLIT = "_".join(
    ("improve", "diagnosis", "or", "split", "mixed", "failure", "surfaces")
)
ACTION_KEEP_REVIEW_FIRST = "_".join(
    ("keep", "review", "first", "boundary", "and", "improve", "owner", "guidance")
)
ACTION_ADD_FORMAT_GUARDRAIL = "_".join(
    ("add", "local", "guardrail", "for", "recurring", "format", "drift", "files")
)
ACTION_KEEP_SAFE_POLICY = "_".join(("keep", "current", "safe", "fix", "policy"))
ACTION_CONTINUE_COLLECTING = "_".join(("continue", "collecting", "safe", "fix", "history"))


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _safe_text(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes"}


def _parse_time(value: Any) -> datetime | None:
    text = _safe_text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _json_key(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _identity(row: dict[str, Any]) -> str:
    parts = [
        _safe_text(row.get(key))
        for key in (
            "source_id",
            "run_id",
            "pr_number",
            "check_run_id",
            "head_sha",
            "timestamp",
            "status",
        )
        if _safe_text(row.get(key))
    ]
    if parts:
        return "|".join(parts)
    return _json_key(row)


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"expected JSON object in {path}"
        raise ValueError(msg)
    return payload


def _candidate_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in (
        "attempts",
        "safe_fix_attempts",
        "safe_fix_outcomes",
        "outcomes",
        "results",
        "items",
    ):
        rows = [_as_dict(item) for item in _as_list(payload.get(key))]
        rows = [row for row in rows if row]
        if rows:
            return rows

    known_keys = {
        "safe_fix_attempted",
        "attempted",
        "safe_fix_committed",
        "committed",
        "safe_fix_pushed",
        "pushed",
        "refused_reason",
        "blocked_reason",
        "status",
    }
    if known_keys.intersection(payload):
        return [payload]

    return []


def _affected_files(row: dict[str, Any]) -> list[str]:
    values: list[Any] = []
    for key in ("affected_files", "files", "changed_files", "owner_files"):
        values.extend(_as_list(row.get(key)))
    return sorted({text for text in (_safe_text(value) for value in values) if text})


def _status(row: dict[str, Any]) -> str:
    explicit = _safe_text(row.get("status")).lower()
    if explicit in {"pushed", "committed", "refused", "attempted", "skipped", "unknown"}:
        return explicit

    if _bool(row.get("safe_fix_pushed")) or _bool(row.get("pushed")):
        return "pushed"
    if _bool(row.get("safe_fix_committed")) or _bool(row.get("committed")):
        return "committed"
    if _safe_text(row.get("refused_reason")) or _safe_text(row.get("blocked_reason")):
        return "refused"
    if row.get("safe_to_auto_fix") is False:
        return "refused"
    if _bool(row.get("safe_fix_attempted")) or _bool(row.get("attempted")):
        return "attempted"
    return "unknown"


def _classification(row: dict[str, Any]) -> str:
    for key in ("failure_surface", "classification", "fix_type", "source_code", "kind"):
        value = _safe_text(row.get(key))
        if value:
            return value
    return "unknown"


def _is_format_drift(row: dict[str, Any]) -> bool:
    haystack = " ".join(
        _safe_text(row.get(key)).lower()
        for key in (
            "failure_surface",
            "classification",
            "fix_type",
            "source_code",
            "kind",
            "reason",
            "refused_reason",
            "blocked_reason",
        )
    )
    return any(
        token in haystack
        for token in (
            "format",
            "formatter",
            "pre_commit_format_drift",
            "whitespace",
            "trailing",
            "eof",
            "ruff_format",
        )
    )


def _normalise_attempt(row: dict[str, Any], observed_at: str, source_path: str) -> dict[str, Any]:
    timestamp = (
        _safe_text(row.get("timestamp"))
        or _safe_text(row.get("created_at"))
        or _safe_text(row.get("observed_at"))
        or _safe_text(row.get("run_started_at"))
        or observed_at
    )
    status = _status(row)
    reason = (
        _safe_text(row.get("refused_reason"))
        or _safe_text(row.get("blocked_reason"))
        or _safe_text(row.get("reason"))
    )
    attempt = {
        "timestamp": timestamp,
        "status": status,
        "classification": _classification(row),
        "source_path": source_path,
        "source_id": _safe_text(row.get("source_id")),
        "run_id": _safe_text(row.get("run_id")),
        "pr_number": _safe_text(row.get("pr_number")),
        "head_sha": _safe_text(row.get("head_sha")),
        "safe_to_auto_fix": row.get("safe_to_auto_fix"),
        "committed": _bool(row.get("safe_fix_committed")) or _bool(row.get("committed")),
        "pushed": _bool(row.get("safe_fix_pushed")) or _bool(row.get("pushed")),
        "refused_reason": reason,
        "review_first": _bool(row.get("review_first")) or _bool(row.get("requires_human_review")),
        "review_first_reason": _safe_text(row.get("review_first_reason"))
        or _safe_text(row.get("human_review_action")),
        "affected_files": _affected_files(row),
        "format_drift": _is_format_drift(row),
    }
    return {key: value for key, value in attempt.items() if value not in ("", [], None)}


def _merge_attempts(
    previous_history: dict[str, Any],
    current_rollup: dict[str, Any],
    *,
    observed_at: str,
    source_path: str,
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}

    for item in _as_list(previous_history.get("attempts")):
        row = _as_dict(item)
        if row:
            merged[_identity(row)] = row

    for row in _candidate_rows(current_rollup):
        attempt = _normalise_attempt(row, observed_at, source_path)
        merged[_identity(attempt)] = attempt

    return sorted(
        merged.values(),
        key=lambda row: (
            _safe_text(row.get("timestamp")),
            _safe_text(row.get("head_sha")),
            _safe_text(row.get("status")),
            _json_key(row),
        ),
    )


def _last_30_days_count(attempts: list[dict[str, Any]], observed_at: str) -> int:
    observed = _parse_time(observed_at)
    if observed is None:
        return 0

    count = 0
    for row in attempts:
        timestamp = _parse_time(row.get("timestamp"))
        if timestamp is None:
            continue
        age_days = (observed - timestamp).days
        if 0 <= age_days <= 30:
            count += 1
    return count


def _recurring_format_files(attempts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for row in attempts:
        if not row.get("format_drift"):
            continue
        counter.update(_affected_files(row))
    return [{"file": file, "count": count} for file, count in sorted(counter.items()) if count >= 2]


def _recurring_reasons(attempts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter(
        _safe_text(row.get("refused_reason"))
        for row in attempts
        if _status(row) == "refused" and _safe_text(row.get("refused_reason"))
    )
    return [
        {"reason": reason, "count": count}
        for reason, count in sorted(counter.items())
        if count >= 2
    ]


def _review_first_blockers(attempts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for row in attempts:
        if row.get("review_first") or _status(row) == "refused":
            reason = _safe_text(row.get("review_first_reason")) or _safe_text(
                row.get("refused_reason")
            )
            if reason:
                counter[reason] += 1
    return [{"reason": reason, "count": count} for reason, count in sorted(counter.items())]


def _format_drift_owner_files(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    owner_files: list[dict[str, Any]] = []
    for item in _as_list(metrics.get(RECURRING_FORMAT_DRIFT_FILES_KEY)):
        row = _as_dict(item)
        file_path = _safe_text(row.get("file"))
        if not file_path:
            continue
        count = int(row.get("count") or 0)
        owner_files.append(
            {
                "file": file_path,
                "count": count,
                "owner_signal": "recurring_format_drift",
            }
        )
    return owner_files


def _owner_file_guardrail_recommendations(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    for item in _format_drift_owner_files(metrics):
        file_path = _safe_text(item.get("file"))
        count = int(item.get("count") or 0)
        if count < 2:
            continue
        action = (
            "escalate_recurring_drift_guardrail"
            if count >= 3
            else "add_owner_file_format_guardrail"
        )
        recommendations.append(
            {
                "file": file_path,
                "count": count,
                "action": action,
                "reason": ("file repeatedly required deterministic formatting safe fixes"),
            }
        )
    return recommendations


def _local_dev_guardrail_recommendations(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    for item in _format_drift_owner_files(metrics):
        file_path = _safe_text(item.get("file"))
        count = int(item.get("count") or 0)
        if count < 2:
            continue
        recommendations.append(
            {
                "file": file_path,
                "count": count,
                "action": "run_pre_commit_before_push",
                "reason": "recurring format drift should be caught before CI",
            }
        )
    return recommendations


def _recurring_format_drift_guardrails(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    guardrails: list[dict[str, Any]] = []
    for item in _format_drift_owner_files(metrics):
        file_path = _safe_text(item.get("file"))
        count = int(item.get("count") or 0)
        if count < 3:
            continue
        guardrails.append(
            {
                "file": file_path,
                "count": count,
                "action": "_".join(("escalate", "recurring", "format", "drift")),
                "reason": " ".join(
                    ("same", "file", "crossed", "recurring", "drift", "escalation", "threshold")
                ),
            }
        )
    return guardrails


def _recommend(metrics: dict[str, Any], attempts: list[dict[str, Any]]) -> str:
    recurring_guardrails = _recurring_format_drift_guardrails(metrics)
    if recurring_guardrails:
        return "_".join(("escalate", "recurring", "format", "drift", "guardrails"))

    recurring_unknown = [
        row for row in attempts if _classification(row) == "unknown" and _status(row) == "refused"
    ]
    if len(recurring_unknown) >= 2:
        return "improve_failure_classification_before_any_mutation"

    if metrics.get(RECURRING_FORMAT_DRIFT_FILES_KEY):
        return "add_local_guardrail_for_recurring_format_drift_files"

    success_rate = float(metrics.get("safe_fix_success_rate") or 0.0)
    if success_rate >= 0.8:
        return "keep_current_safe_policy"

    if metrics.get("safe_fix_refused_total", 0) >= 2:
        return "improve_diagnosis_or_split_failure_surfaces"

    return "_".join(("keep", "review", "first", "boundary", "and", "improve", "owner", "guidance"))


def _metrics(attempts: list[dict[str, Any]], observed_at: str) -> dict[str, Any]:
    attempts_total = len(attempts)
    pushed_total = sum(1 for row in attempts if row.get("pushed") or _status(row) == "pushed")
    committed_total = sum(
        1 for row in attempts if row.get("committed") or _status(row) in {"committed", "pushed"}
    )
    refused_total = sum(1 for row in attempts if _status(row) == "refused")
    success_total = sum(1 for row in attempts if _status(row) in {"committed", "pushed"})
    success_rate = round(success_total / attempts_total, 4) if attempts_total else 0.0

    metrics = {
        SAFE_FIX_ATTEMPTS_TOTAL_KEY: attempts_total,
        SAFE_FIX_ATTEMPTS_LAST_30_DAYS_KEY: _last_30_days_count(attempts, observed_at),
        SAFE_FIX_PUSHED_TOTAL_KEY: pushed_total,
        SAFE_FIX_COMMITTED_TOTAL_KEY: committed_total,
        SAFE_FIX_REFUSED_TOTAL_KEY: refused_total,
        SAFE_FIX_SUCCESS_RATE_KEY: success_rate,
        RECURRING_FORMAT_DRIFT_FILES_KEY: _recurring_format_files(attempts),
        RECURRING_REFUSAL_REASONS_KEY: _recurring_reasons(attempts),
        REVIEW_FIRST_BLOCKERS_KEY: _review_first_blockers(attempts),
        MOST_RECENT_SAFE_FIX_STATUS_KEY: _status(attempts[-1]) if attempts else "unknown",
    }
    metrics["format_drift_owner_files"] = _format_drift_owner_files(metrics)
    metrics["owner_file_guardrail_recommendations"] = _owner_file_guardrail_recommendations(metrics)
    metrics["local_dev_guardrail_recommendations"] = _local_dev_guardrail_recommendations(metrics)
    metrics["recurring_format_drift_guardrails"] = _recurring_format_drift_guardrails(metrics)
    metrics[RECOMMENDED_NEXT_OPERATOR_ACTION_KEY] = _recommend(metrics, attempts)
    return metrics


def render_markdown(history: dict[str, Any], trends: dict[str, Any]) -> str:
    metrics = _as_dict(trends.get("metrics"))
    lines = [
        "# Safe-Fix History",
        "",
        f"- Attempts total: {metrics.get(SAFE_FIX_ATTEMPTS_TOTAL_KEY, 0)}",
        f"- Attempts last 30 days: {metrics.get(SAFE_FIX_ATTEMPTS_LAST_30_DAYS_KEY, 0)}",
        f"- Pushed total: {metrics.get(SAFE_FIX_PUSHED_TOTAL_KEY, 0)}",
        f"- Committed total: {metrics.get(SAFE_FIX_COMMITTED_TOTAL_KEY, 0)}",
        f"- Refused total: {metrics.get(SAFE_FIX_REFUSED_TOTAL_KEY, 0)}",
        f"- Success rate: {metrics.get(SAFE_FIX_SUCCESS_RATE_KEY, 0.0)}",
        f"- Most recent status: {metrics.get(MOST_RECENT_SAFE_FIX_STATUS_KEY, 'unknown')}",
        f"- Recommended next operator action: {metrics.get(RECOMMENDED_NEXT_OPERATOR_ACTION_KEY, 'unknown')}",
        "",
        "## Recurring format drift files",
        "",
    ]

    recurring_files = _as_list(metrics.get(RECURRING_FORMAT_DRIFT_FILES_KEY))
    if recurring_files:
        for row in recurring_files:
            item = _as_dict(row)
            lines.append(f"- `{item.get('file')}`: {item.get('count')}")
    else:
        lines.append("- None")

    lines.extend(["", "## Recurring refusal reasons", ""])
    refusal_reasons = _as_list(metrics.get(RECURRING_REFUSAL_REASONS_KEY))
    if refusal_reasons:
        for row in refusal_reasons:
            item = _as_dict(row)
            lines.append(f"- {item.get('reason')}: {item.get('count')}")
    else:
        lines.append("- None")

    lines.extend(["", "## Attempts", ""])
    for row in _as_list(history.get("attempts")):
        item = _as_dict(row)
        files = ", ".join(str(file) for file in _as_list(item.get("affected_files"))) or "none"
        lines.append(
            "- "
            f"{item.get('timestamp', 'unknown')} | "
            f"{item.get('status', 'unknown')} | "
            f"{item.get('classification', 'unknown')} | "
            f"files={files}"
        )

    owner_recommendations = _as_list(metrics.get("owner_file_guardrail_recommendations"))
    if owner_recommendations:
        lines.extend(["", "## Owner-file guardrail recommendations"])
        for row in owner_recommendations:
            item = _as_dict(row)
            lines.append(
                f"- `{_safe_text(item.get('file'))}`: "
                f"{_safe_text(item.get('action'))} "
                f"(count={int(item.get('count') or 0)})"
            )

    local_recommendations = _as_list(metrics.get("local_dev_guardrail_recommendations"))
    if local_recommendations:
        lines.extend(["", "## Local developer guardrail recommendations"])
        for row in local_recommendations:
            item = _as_dict(row)
            lines.append(f"- `{_safe_text(item.get('file'))}`: {_safe_text(item.get('action'))}")

    recurring_guardrails = _as_list(metrics.get("recurring_format_drift_guardrails"))
    if recurring_guardrails:
        lines.extend(["", "## Recurring format drift guardrails"])
        for row in recurring_guardrails:
            item = _as_dict(row)
            lines.append(
                f"- `{_safe_text(item.get('file'))}`: "
                f"{_safe_text(item.get('action'))} "
                f"(count={int(item.get('count') or 0)})"
            )

    return "\n".join(lines) + "\n"


def build_safe_fix_history(
    current_rollup: dict[str, Any],
    previous_history: dict[str, Any] | None = None,
    *,
    observed_at: str = DEFAULT_OBSERVED_AT,
    source_path: str = "",
) -> tuple[dict[str, Any], dict[str, Any], str]:
    attempts = _merge_attempts(
        previous_history or {},
        current_rollup,
        observed_at=observed_at,
        source_path=source_path,
    )
    metrics = _metrics(attempts, observed_at)
    history = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": observed_at,
        "source_path": source_path,
        "attempts": attempts,
        "metrics": metrics,
    }
    trends = {
        "schema_version": TRENDS_SCHEMA_VERSION,
        "generated_at": observed_at,
        "metrics": metrics,
    }
    return history, trends, render_markdown(history, trends)


def persist_safe_fix_history(
    rollup_path: Path,
    out_dir: Path,
    *,
    previous_history_path: Path | None = None,
    observed_at: str = DEFAULT_OBSERVED_AT,
) -> dict[str, Path]:
    current_rollup = _load_json(rollup_path)
    previous_history = _load_json(previous_history_path)
    history, trends, markdown = build_safe_fix_history(
        current_rollup,
        previous_history,
        observed_at=observed_at,
        source_path=rollup_path.as_posix(),
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    history_path = out_dir / HISTORY_JSON
    trends_path = out_dir / TRENDS_JSON
    markdown_path = out_dir / HISTORY_MD

    history_path.write_text(json.dumps(history, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    trends_path.write_text(json.dumps(trends, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(markdown, encoding="utf-8")

    return {
        HISTORY_JSON_KEY: history_path,
        TRENDS_JSON_KEY: trends_path,
        HISTORY_MD_KEY: markdown_path,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.safe_fix_history_memory")
    parser.add_argument("rollup_json")
    parser.add_argument("--previous-history", default="")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--observed-at", default=DEFAULT_OBSERVED_AT)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    previous = Path(args.previous_history) if args.previous_history else None
    try:
        paths = persist_safe_fix_history(
            Path(args.rollup_json),
            Path(args.out_dir),
            previous_history_path=previous,
            observed_at=args.observed_at,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(
            json.dumps(
                {key: path.as_posix() for key, path in paths.items()}, indent=2, sort_keys=True
            )
        )
    else:
        for key, path in paths.items():
            print(f"{key}: {path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
