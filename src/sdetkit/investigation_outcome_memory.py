from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.investigation.outcome_memory.v1"


def _clean_required(value: str, name: str) -> str:
    clean = value.strip()
    if not clean:
        raise OSError(f"{name} is required")
    return clean


def _clean_optional(value: str) -> str:
    return value.strip()


def _as_nonnegative_int(value: int | str) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _as_list(values: list[str] | tuple[str, ...] | None) -> list[str]:
    if not values:
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def build_investigation_outcome_record(
    *,
    classification: str,
    surface: str,
    proof_command: str,
    safe_fix_outcome: str = "not_attempted",
    manual_fix_outcome: str = "unknown",
    pr_number: int | str = 0,
    merged: bool = False,
    time_to_green_seconds: int | str = 0,
    affected_files: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    return {
        "classification": _clean_required(classification, "classification"),
        "surface": _clean_required(surface, "surface"),
        "affected_files": sorted(set(_as_list(affected_files))),
        "proof_command": _clean_required(proof_command, "proof_command"),
        "safe_fix_outcome": _clean_optional(safe_fix_outcome) or "not_attempted",
        "manual_fix_outcome": _clean_optional(manual_fix_outcome) or "unknown",
        "pr_number": _as_nonnegative_int(pr_number),
        "merged": bool(merged),
        "time_to_green_seconds": _as_nonnegative_int(time_to_green_seconds),
    }


def load_investigation_outcome_memory(path: str | Path) -> dict[str, Any]:
    memory_path = Path(path)
    if not memory_path.exists():
        return {
            "schema_version": SCHEMA_VERSION,
            "diagnostic_only": True,
            "automation_allowed": False,
            "records": [],
        }
    data = json.loads(memory_path.read_text(encoding="utf-8"))
    records = data.get("records", []) if isinstance(data, dict) else []
    return {
        "schema_version": SCHEMA_VERSION,
        "diagnostic_only": True,
        "automation_allowed": False,
        "records": records if isinstance(records, list) else [],
    }


def append_investigation_outcome_memory(path: str | Path, record: dict[str, Any]) -> dict[str, Any]:
    memory = load_investigation_outcome_memory(path)
    memory["records"].append(record)
    memory["records"] = sorted(
        memory["records"],
        key=lambda item: (
            str(item.get("classification", "")),
            str(item.get("surface", "")),
            int(item.get("pr_number", 0) or 0),
            str(item.get("proof_command", "")),
        ),
    )
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(memory, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return memory


def summarize_investigation_outcome_memory(memory: dict[str, Any]) -> dict[str, Any]:
    records = memory.get("records", []) if isinstance(memory.get("records"), list) else []
    merged_count = sum(1 for record in records if bool(record.get("merged")))
    manual_success_count = sum(
        1 for record in records if str(record.get("manual_fix_outcome", "")) == "merged"
    )
    safe_success_count = sum(
        1 for record in records if str(record.get("safe_fix_outcome", "")) == "manual_success"
    )
    classifications = sorted({str(record.get("classification", "")) for record in records})
    return {
        "schema_version": "sdetkit.investigation.outcome_memory.summary.v1",
        "diagnostic_only": True,
        "automation_allowed": False,
        "record_count": len(records),
        "merged_count": merged_count,
        "manual_success_count": manual_success_count,
        "safe_fix_success_count": safe_success_count,
        "classifications": [value for value in classifications if value],
    }
