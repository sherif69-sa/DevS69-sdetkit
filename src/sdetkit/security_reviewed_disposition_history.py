"""Record sanitized reviewed security dispositions from accepted-main merge evidence.

This module records read-only historical evidence only. A previously dismissed
finding never authorizes a fix, dismissal, merge, or other action for a
current finding.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = ".".join(("sdetkit", "security", "reviewed", "disposition", "history", "v1"))
RECORD_SCHEMA_VERSION = ".".join(
    ("sdetkit", "security", "reviewed", "disposition", "history", "record", "v1")
)
DEFAULT_OUT_DIR = Path("build") / "repo-memory-history" / "security-reviewed-dispositions"
SUMMARY_JSON = "security-reviewed-disposition-history-summary.json"
SUMMARY_MD = "security-reviewed-disposition-history-summary.md"
HISTORY_JSONL = "security-reviewed-disposition-history.jsonl"

COLLECTED = "collected"
UNAVAILABLE = "unavailable"
DISMISSED = "dismissed"
AUTOMATIC_SECURITY_FIX_ALLOWED = "_".join(("automatic", "security", "fix", "allowed"))
AUTOMATIC_DISMISSAL_ALLOWED = "_".join(("automatic", "dismissal", "allowed"))
AUTOMATION_ALLOWED = "_".join(("automation", "allowed"))
MERGE_AUTHORIZED = "_".join(("merge", "authorized"))
HISTORICAL_DISPOSITION_AUTHORIZES_CURRENT_ACTION = "_".join(
    ("historical", "disposition", "authorizes", "current", "action")
)
PRIOR_HISTORY_READ_ONLY_INPUT = "_".join(("prior", "history", "is", "read", "only", "input"))

JsonObject = dict[str, Any]


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _bool(value: Any) -> bool:
    return value is True


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path | None) -> list[JsonObject]:
    if path is None or not path.exists():
        return []

    records: list[JsonObject] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError(f"expected JSON object on line {line_number} in {path}")
        records.append(payload)
    return records


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_hash(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(dict(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _decision_boundary() -> JsonObject:
    return {
        "reporting_only": True,
        AUTOMATIC_SECURITY_FIX_ALLOWED: False,
        AUTOMATIC_DISMISSAL_ALLOWED: False,
        AUTOMATION_ALLOWED: False,
        MERGE_AUTHORIZED: False,
        HISTORICAL_DISPOSITION_AUTHORIZES_CURRENT_ACTION: False,
        PRIOR_HISTORY_READ_ONLY_INPUT: True,
    }


def _assert_no_authority(boundary: Mapping[str, Any], *, source: str) -> None:
    enabled = [
        key
        for key in (
            AUTOMATIC_SECURITY_FIX_ALLOWED,
            AUTOMATIC_DISMISSAL_ALLOWED,
            AUTOMATION_ALLOWED,
            MERGE_AUTHORIZED,
            HISTORICAL_DISPOSITION_AUTHORIZES_CURRENT_ACTION,
        )
        if _bool(boundary.get(key))
    ]
    if enabled:
        raise ValueError(
            f"{source} expands security authority and cannot enter read-only history: "
            f"{', '.join(enabled)}"
        )


def _select_merged_pr(payload: Any, *, source_head_sha: str) -> JsonObject:
    candidates = payload if isinstance(payload, list) else [payload]
    matches = [
        _as_dict(item)
        for item in candidates
        if isinstance(item, dict)
        and _text(_as_dict(item).get("merged_at"))
        and _text(_as_dict(item).get("merge_commit_sha")) == source_head_sha
    ]
    if len(matches) > 1:
        raise ValueError("accepted-main commit maps to more than one merged pull request")
    return matches[0] if matches else {}


def _alert_payload(payload: Any) -> tuple[str, str, list[JsonObject]]:
    if isinstance(payload, list):
        return COLLECTED, "", [_as_dict(item) for item in payload if isinstance(item, dict)]

    data = _as_dict(payload)
    status = _text(data.get("collection_status") or COLLECTED)
    reason = _text(data.get("collection_reason"))
    alerts = [_as_dict(item) for item in _as_list(data.get("alerts")) if isinstance(item, dict)]
    if status not in {COLLECTED, UNAVAILABLE}:
        raise ValueError("dismissed alert collection status is not supported")
    if status == UNAVAILABLE and alerts:
        raise ValueError("unavailable dismissed alert collection cannot carry alerts")
    return status, reason, alerts


def _sanitize_dismissed_alert(alert: Mapping[str, Any], *, pull_number: int) -> JsonObject:
    if _text(alert.get("state")).lower() != DISMISSED:
        raise ValueError(
            "only dismissed code-scanning alerts may enter reviewed disposition history"
        )

    reviewer = _text(_as_dict(alert.get("dismissed_by")).get("login"))
    dismissed_at = _text(alert.get("dismissed_at"))
    dismissed_reason = _text(alert.get("dismissed_reason"))
    if not reviewer or not dismissed_at or not dismissed_reason:
        raise ValueError("dismissed security disposition lacks reviewer provenance")

    rule = _as_dict(alert.get("rule"))
    tool = _as_dict(alert.get("tool"))
    instance = _as_dict(alert.get("most_recent_instance"))
    location = _as_dict(instance.get("location"))
    stable = {
        "pull_number": pull_number,
        "alert_number": _int(alert.get("number")),
        "state": DISMISSED,
        "tool": _text(tool.get("name") or "unknown"),
        "rule_id": _text(rule.get("id") or "unknown"),
        "severity": _text(rule.get("security_severity_level") or rule.get("severity") or "unknown"),
        "path": _text(location.get("path") or "unknown"),
        "line": _int(location.get("start_line")),
        "dismissed_by": reviewer,
        "dismissed_at": dismissed_at,
        "dismissed_reason": dismissed_reason,
        "dismissed_comment_present": bool(_text(alert.get("dismissed_comment"))),
    }
    return {
        "disposition_id": _stable_hash(stable),
        **stable,
    }


def validate_record(record: Mapping[str, Any]) -> None:
    if _text(record.get("schema_version")) != RECORD_SCHEMA_VERSION:
        raise ValueError("reviewed security disposition record schema is not supported")
    _assert_no_authority(
        _as_dict(record.get("decision_boundary")),
        source="reviewed security disposition record",
    )
    for disposition in _as_list(record.get("reviewed_dispositions")):
        item = _as_dict(disposition)
        if _text(item.get("state")) != DISMISSED:
            raise ValueError("reviewed disposition record contains non-dismissed security state")
        if "dismissed_comment" in item:
            raise ValueError("reviewed disposition record must not persist dismissal comment text")


def build_history_record(
    *,
    associated_pr_payload: Any,
    dismissed_alerts_payload: Any,
    source_run_id: str,
    source_head_sha: str,
    recorded_at_utc: str | None = None,
) -> JsonObject:
    run_id = _text(source_run_id)
    head_sha = _text(source_head_sha)
    if not run_id:
        raise ValueError("source_run_id is required")
    if not head_sha:
        raise ValueError("source_head_sha is required")

    merged_pr = _select_merged_pr(associated_pr_payload, source_head_sha=head_sha)
    collection_status, collection_reason, alerts = _alert_payload(dismissed_alerts_payload)
    if alerts and not merged_pr:
        raise ValueError("dismissed alerts cannot be recorded without an associated merged PR")

    pull_number = _int(merged_pr.get("number"))
    dispositions = (
        sorted(
            [_sanitize_dismissed_alert(alert, pull_number=pull_number) for alert in alerts],
            key=lambda item: (
                _text(item.get("path")),
                _int(item.get("line")),
                _text(item.get("rule_id")),
                _int(item.get("alert_number")),
            ),
        )
        if merged_pr and collection_status == COLLECTED
        else []
    )
    source = {
        "workflow": "RepoMemory Profile History",
        "source_run_id": run_id,
        "source_head_sha": head_sha,
        "merged_pr_number": pull_number,
        "merged_pr_present": bool(merged_pr),
        "merged_pr_merged_at": _text(merged_pr.get("merged_at")),
        "collection_status": collection_status,
        "collection_reason": collection_reason,
    }
    stable = {
        "source": source,
        "reviewed_dispositions": dispositions,
        "decision_boundary": _decision_boundary(),
    }
    record = {
        "schema_version": RECORD_SCHEMA_VERSION,
        "record_id": _stable_hash(stable),
        "recorded_at_utc": recorded_at_utc or _utc_now(),
        **stable,
    }
    validate_record(record)
    return record


def merge_history_records(
    prior_records: list[Mapping[str, Any]],
    record: Mapping[str, Any],
) -> tuple[list[JsonObject], bool]:
    validate_record(record)
    records = [dict(item) for item in prior_records]
    for existing in records:
        validate_record(existing)

    record_id = _text(record.get("record_id"))
    existing_ids = {_text(item.get("record_id")) for item in records}
    appended = record_id not in existing_ids
    if appended:
        records.append(dict(record))
    return records, appended


def write_history_jsonl(records: list[Mapping[str, Any]], *, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / HISTORY_JSONL
    path.write_text(
        "".join(json.dumps(dict(record), sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    return path


def build_summary(
    records: list[Mapping[str, Any]],
    *,
    appended: bool,
    history_path: Path,
    prior_history_collected: bool,
    prior_record_count: int,
) -> JsonObject:
    for record in records:
        validate_record(record)
    latest = _as_dict(records[-1]) if records else {}
    latest_source = _as_dict(latest.get("source"))
    latest_dispositions = [_as_dict(item) for item in _as_list(latest.get("reviewed_dispositions"))]
    status_counts = Counter(
        _text(_as_dict(record.get("source")).get("collection_status")) for record in records
    )
    total_dispositions = sum(
        len(_as_list(record.get("reviewed_dispositions"))) for record in records
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "_".join(("reviewed", "disposition", "history", "recorded")),
        "history_path": history_path.as_posix(),
        "prior_history_collected": prior_history_collected,
        "prior_record_count": prior_record_count,
        "appended": appended,
        "record_count": len(records),
        "collection_status_counts": dict(sorted(status_counts.items())),
        "reviewed_disposition_count": total_dispositions,
        "latest_record": {
            "record_id": _text(latest.get("record_id")),
            "source_run_id": _text(latest_source.get("source_run_id")),
            "source_head_sha": _text(latest_source.get("source_head_sha")),
            "merged_pr_number": _int(latest_source.get("merged_pr_number")),
            "merged_pr_present": _bool(latest_source.get("merged_pr_present")),
            "collection_status": _text(latest_source.get("collection_status")),
            "reviewed_disposition_count": len(latest_dispositions),
        },
        "decision_boundary": _decision_boundary(),
    }


def render_markdown(summary: Mapping[str, Any]) -> str:
    latest = _as_dict(summary.get("latest_record"))
    boundary = _as_dict(summary.get("decision_boundary"))
    return "\n".join(
        [
            "# Security reviewed disposition history",
            "",
            f"- Status: `{_text(summary.get('status'))}`",
            f"- Records: `{_int(summary.get('record_count'))}`",
            f"- Reviewed dispositions: `{_int(summary.get('reviewed_disposition_count'))}`",
            f"- Latest accepted main head: `{_text(latest.get('source_head_sha'))}`",
            f"- Latest merged PR: `{_int(latest.get('merged_pr_number'))}`",
            (f"- Latest reviewed dispositions: `{_int(latest.get('reviewed_disposition_count'))}`"),
            "",
            "## Boundary",
            "",
            (
                "- Historical disposition authorizes current action: "
                f"`{str(_bool(boundary.get(HISTORICAL_DISPOSITION_AUTHORIZES_CURRENT_ACTION))).lower()}`"
            ),
            (
                "- Automatic security fix allowed: "
                f"`{str(_bool(boundary.get(AUTOMATIC_SECURITY_FIX_ALLOWED))).lower()}`"
            ),
            (
                "- Automatic dismissal allowed: "
                f"`{str(_bool(boundary.get(AUTOMATIC_DISMISSAL_ALLOWED))).lower()}`"
            ),
            f"- Automation allowed: `{str(_bool(boundary.get(AUTOMATION_ALLOWED))).lower()}`",
            f"- Merge authorized: `{str(_bool(boundary.get(MERGE_AUTHORIZED))).lower()}`",
            (
                "- Prior history is read-only input: "
                f"`{str(_bool(boundary.get(PRIOR_HISTORY_READ_ONLY_INPUT))).lower()}`"
            ),
            "",
        ]
    )


def write_summary(summary: Mapping[str, Any], *, out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / SUMMARY_JSON
    markdown_path = out_dir / SUMMARY_MD
    json_path.write_text(
        json.dumps(dict(summary), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(summary), encoding="utf-8")
    return {
        "summary_json": json_path.as_posix(),
        "summary_markdown": markdown_path.as_posix(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.security_reviewed_disposition_history")
    parser.add_argument("--associated-pr-json", type=Path, required=True)
    parser.add_argument("--dismissed-alerts-json", type=Path, required=True)
    parser.add_argument("--prior-history-jsonl", type=Path)
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--source-head-sha", required=True)
    parser.add_argument("--recorded-at-utc")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.prior_history_jsonl is not None and not args.prior_history_jsonl.exists():
            raise ValueError(
                f"prior disposition history input does not exist: {args.prior_history_jsonl}"
            )
        prior_records = _read_jsonl(args.prior_history_jsonl)
        record = build_history_record(
            associated_pr_payload=_read_json(args.associated_pr_json),
            dismissed_alerts_payload=_read_json(args.dismissed_alerts_json),
            source_run_id=args.source_run_id,
            source_head_sha=args.source_head_sha,
            recorded_at_utc=args.recorded_at_utc,
        )
        records, appended = merge_history_records(prior_records, record)
        history_path = write_history_jsonl(records, out_dir=args.out_dir)
        summary = build_summary(
            records,
            appended=appended,
            history_path=history_path,
            prior_history_collected=args.prior_history_jsonl is not None,
            prior_record_count=len(prior_records),
        )
        artifacts = write_summary(summary, out_dir=args.out_dir)
        artifacts["history_jsonl"] = history_path.as_posix()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stdout.write(f"error={exc}\n")
        return 2

    output = {
        "status": summary["status"],
        "record_count": summary["record_count"],
        "reviewed_disposition_count": summary["reviewed_disposition_count"],
        "appended": summary["appended"],
        "artifacts": artifacts,
    }
    if args.format == "json":
        sys.stdout.write(json.dumps(output, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write("\n".join(f"{key}={value}" for key, value in output.items()) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
