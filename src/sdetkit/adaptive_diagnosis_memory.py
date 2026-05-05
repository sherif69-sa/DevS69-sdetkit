from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.adaptive_diagnosis.memory.v1"
RECORD_SCHEMA_VERSION = "sdetkit.adaptive_diagnosis.learning_record.v1"
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
