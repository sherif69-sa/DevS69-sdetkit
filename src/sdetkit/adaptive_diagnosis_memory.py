from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sdetkit._datetime import UTC

SCHEMA_VERSION = "sdetkit.adaptive_diagnosis.memory.v1"
RECORD_SCHEMA_VERSION = "sdetkit.adaptive_diagnosis.learning_record.v1"
SAFE_FIX_ROLLUP_SCHEMA_VERSION = "sdetkit.adaptive_safe_fix.rollup.v1"
SOURCE_SCHEMA_VERSION = "sdetkit.adaptive.diagnosis.v1"
ACTIONABLE_STATUSES = {"needs_attention", "needs_fix"}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return 0


def _first(values: Any) -> str:
    for value in _as_list(values):
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _record_hash(parts: dict[str, Any]) -> str:
    encoded = json.dumps(parts, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_diagnosis(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    if payload.get("schema_version") != SOURCE_SCHEMA_VERSION:
        raise ValueError(f"unsupported adaptive diagnosis schema in {path}")
    return payload


def build_safe_fix_learning_record(
    *,
    plan: dict[str, Any],
    remediation_result: dict[str, Any] | None = None,
    commit_result: dict[str, Any] | None = None,
    learned_at_utc: str | None = None,
) -> dict[str, Any]:
    remediation = _as_dict(remediation_result)
    commit = _as_dict(commit_result)
    affected_files = [str(value) for value in _as_list(plan.get("affected_files"))]
    identity = {
        "source": "adaptive_safe_fix",
        "source_code": plan.get("source_code", "UNKNOWN"),
        "fix_type": plan.get("fix_type", "unknown"),
        "safe_to_auto_fix": bool(plan.get("safe_to_auto_fix", False)),
        "remediation_status": remediation.get("status", "not_attempted"),
        "commit_pushed": bool(commit.get("pushed", False)),
    }
    return {
        "schema_version": RECORD_SCHEMA_VERSION,
        "record_id": _record_hash(identity),
        "learned_at_utc": learned_at_utc or _timestamp(),
        "source": "adaptive_safe_fix",
        "source_schema_version": str(plan.get("schema_version", "")),
        "source_status": str(plan.get("source_status", "unknown")),
        "source_confidence": str(plan.get("confidence", "unknown")),
        "source_risk_score": 0,
        "code": str(plan.get("source_code", "UNKNOWN")),
        "signal": f"safe-fix-{plan.get('fix_type', 'unknown')}",
        "severity": "info",
        "confidence": str(plan.get("confidence", "unknown")),
        "title": f"Safe fix outcome for {plan.get('fix_type', 'unknown')}",
        "recommended_fix": _first(plan.get("commands")),
        "proof_command": _first(plan.get("proof_commands")),
        "risk_if_ignored": str(plan.get("reason", "")),
        "repeat_count": 0,
        "affected_files": affected_files,
        "fix_type": str(plan.get("fix_type", "unknown")),
        "safe_to_auto_fix": bool(plan.get("safe_to_auto_fix", False)),
        "requires_human_review": bool(plan.get("requires_human_review", True)),
        "affected_file_count": len(affected_files),
        "remediation_attempted": bool(remediation.get("attempted", False)),
        "remediation_ok": bool(remediation.get("ok", False)),
        "remediation_status": str(remediation.get("status", "not_attempted")),
        "remediation_command_count": _as_int(remediation.get("command_count")),
        "commit_attempted": bool(commit.get("attempted", False)),
        "commit_ok": bool(commit.get("ok", False)),
        "commit_pushed": bool(commit.get("pushed", False)),
        "commit_reason": str(commit.get("reason", "")),
    }


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def build_safe_fix_memory_rollup(records: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    safe_fix_records = 0

    for record in records:
        row = _as_dict(record)
        if row.get("source") != "adaptive_safe_fix":
            continue

        safe_fix_records += 1
        fix_type = str(row.get("fix_type", "unknown"))
        code = str(row.get("code", "UNKNOWN"))
        key = (fix_type, code)
        group = groups.setdefault(
            key,
            {
                "fix_type": fix_type,
                "code": code,
                "records": 0,
                "affected_file_count": 0,
                "remediation_attempts": 0,
                "remediation_successes": 0,
                "commit_attempts": 0,
                "commit_pushes": 0,
                "latest_record_id": "",
                "latest_learned_at_utc": "",
                "latest_remediation_status": "unknown",
                "latest_commit_reason": "",
            },
        )

        group["records"] += 1
        group["affected_file_count"] += _as_int(row.get("affected_file_count"))
        if bool(row.get("remediation_attempted", False)):
            group["remediation_attempts"] += 1
        if bool(row.get("remediation_ok", False)):
            group["remediation_successes"] += 1
        if bool(row.get("commit_attempted", False)):
            group["commit_attempts"] += 1
        if bool(row.get("commit_pushed", False)):
            group["commit_pushes"] += 1
        group["latest_record_id"] = str(row.get("record_id", ""))
        group["latest_learned_at_utc"] = str(row.get("learned_at_utc", ""))
        group["latest_remediation_status"] = str(row.get("remediation_status", "unknown"))
        group["latest_commit_reason"] = str(row.get("commit_reason", ""))

    ordered_groups = []
    for group in sorted(groups.values(), key=lambda item: (item["fix_type"], item["code"])):
        group["remediation_success_rate"] = _rate(
            _as_int(group["remediation_successes"]), _as_int(group["remediation_attempts"])
        )
        group["commit_push_rate"] = _rate(
            _as_int(group["commit_pushes"]), _as_int(group["commit_attempts"])
        )
        ordered_groups.append(group)

    return {
        "schema_version": SAFE_FIX_ROLLUP_SCHEMA_VERSION,
        "ok": True,
        "source": "adaptive_safe_fix_memory",
        "input_records": len(records),
        "safe_fix_records": safe_fix_records,
        "group_count": len(ordered_groups),
        "groups": ordered_groups,
    }


def safe_fix_rollup_from_db(db_path: Path) -> dict[str, Any]:
    return build_safe_fix_memory_rollup(_read_jsonl(db_path))


def build_learning_records(
    payload: dict[str, Any],
    *,
    include_monitor: bool = False,
    learned_at_utc: str | None = None,
) -> list[dict[str, Any]]:
    status = str(payload.get("status", "unknown"))
    if status not in ACTIONABLE_STATUSES and not include_monitor:
        return []

    learned_at = learned_at_utc or _timestamp()
    records: list[dict[str, Any]] = []
    for diagnosis in _as_list(payload.get("diagnoses")):
        row = _as_dict(diagnosis)
        code = str(row.get("code", "UNKNOWN")).strip() or "UNKNOWN"
        signal = str(row.get("learning_signal", "")).strip() or code.lower()
        identity = {
            "source_status": status,
            "code": code,
            "signal": signal,
            "title": row.get("title", ""),
            "recommended_fix": _first(row.get("recommended_fix")),
            "proof_command": _first(row.get("proof_commands")),
        }
        records.append(
            {
                "schema_version": RECORD_SCHEMA_VERSION,
                "record_id": _record_hash(identity),
                "learned_at_utc": learned_at,
                "source": "adaptive_diagnosis",
                "source_schema_version": str(payload.get("schema_version", "")),
                "source_status": status,
                "source_confidence": str(payload.get("confidence", "unknown")),
                "source_risk_score": _as_int(payload.get("risk_score")),
                "code": code,
                "signal": signal,
                "severity": str(row.get("severity", "unknown")),
                "confidence": str(row.get("confidence", "unknown")),
                "title": str(row.get("title", "")),
                "recommended_fix": _first(row.get("recommended_fix")),
                "proof_command": _first(row.get("proof_commands")),
                "risk_if_ignored": str(row.get("risk_if_ignored", "")),
                "repeat_count": _as_int(row.get("repeat_count")),
                "affected_files": [str(value) for value in _as_list(row.get("affected_files"))],
            }
        )
    return records


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except ValueError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def append_learning_records(db_path: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    existing_ids = {str(row.get("record_id", "")) for row in _read_jsonl(db_path)}
    appended = 0
    with db_path.open("a", encoding="utf-8") as fh:
        for record in records:
            record_id = str(record.get("record_id", ""))
            if not record_id or record_id in existing_ids:
                continue
            fh.write(json.dumps(record, sort_keys=True) + "\n")
            existing_ids.add(record_id)
            appended += 1
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "db_path": db_path.as_posix(),
        "input_records": len(records),
        "appended_records": appended,
        "total_records": len(existing_ids),
    }


def learn_from_diagnosis(
    diagnosis_path: Path,
    db_path: Path,
    *,
    include_monitor: bool = False,
    learned_at_utc: str | None = None,
) -> dict[str, Any]:
    payload = load_diagnosis(diagnosis_path)
    records = build_learning_records(
        payload, include_monitor=include_monitor, learned_at_utc=learned_at_utc
    )
    summary = append_learning_records(db_path, records)
    summary["source_path"] = diagnosis_path.as_posix()
    summary["source_status"] = str(payload.get("status", "unknown"))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.adaptive_diagnosis_memory")
    parser.add_argument("diagnosis_json")
    parser.add_argument("--db", default=".sdetkit/adaptive-diagnosis-memory.jsonl")
    parser.add_argument("--include-monitor", action="store_true")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        summary = learn_from_diagnosis(
            Path(args.diagnosis_json),
            Path(args.db),
            include_monitor=bool(args.include_monitor),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"adaptive diagnosis learning db: {summary['db_path']}")
        print(f"source status: {summary['source_status']}")
        print(f"appended records: {summary['appended_records']}/{summary['input_records']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
