from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.pr_guardrail_outcome_memory.v1"
SUMMARY_SCHEMA_VERSION = "sdetkit.pr_guardrail_outcome_memory.summary.v1"


def _clean_required(value: str, name: str) -> str:
    clean = value.strip()
    if not clean:
        raise OSError(f"{name} is required")
    return clean


def _as_nonnegative_int(value: int | str) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _as_list(values: list[str] | tuple[str, ...] | None) -> list[str]:
    if not values:
        return []
    return sorted({str(value).strip() for value in values if str(value).strip()})


def build_pr_guardrail_outcome_record(
    *,
    candidate_key: str,
    decision_status: str,
    target_branch: str,
    outcome_status: str,
    pr_number: int | str = 0,
    merged: bool = False,
    approvals: list[str] | tuple[str, ...] | None = None,
    artifacts: list[str] | tuple[str, ...] | None = None,
    blockers: list[str] | tuple[str, ...] | None = None,
    elapsed_seconds: int | str = 0,
) -> dict[str, Any]:
    return {
        "candidate_key": _clean_required(candidate_key, "candidate_key"),
        "decision_status": _clean_required(decision_status, "decision_status"),
        "target_branch": _clean_required(target_branch, "target_branch"),
        "outcome_status": _clean_required(outcome_status, "outcome_status"),
        "pr_number": _as_nonnegative_int(pr_number),
        "merged": bool(merged),
        "approvals": _as_list(approvals),
        "artifacts": _as_list(artifacts),
        "blockers": _as_list(blockers),
        "elapsed_seconds": _as_nonnegative_int(elapsed_seconds),
    }


def load_pr_guardrail_outcome_memory(path: str | Path) -> dict[str, Any]:
    memory_path = Path(path)
    if not memory_path.exists():
        return {
            "schema_version": SCHEMA_VERSION,
            "automation_allowed": False,
            "change_allowed_now": False,
            "direct_to_main_allowed": False,
            "records": [],
        }
    data = json.loads(memory_path.read_text(encoding="utf-8"))
    records = data.get("records", []) if isinstance(data, dict) else []
    return {
        "schema_version": SCHEMA_VERSION,
        "automation_allowed": False,
        "change_allowed_now": False,
        "direct_to_main_allowed": False,
        "records": records if isinstance(records, list) else [],
    }


def append_pr_guardrail_outcome_memory(path: str | Path, record: dict[str, Any]) -> dict[str, Any]:
    memory = load_pr_guardrail_outcome_memory(path)
    memory["records"].append(record)
    memory["records"] = sorted(
        memory["records"],
        key=lambda item: (
            str(item.get("candidate_key", "")),
            int(item.get("pr_number", 0) or 0),
            str(item.get("target_branch", "")),
            str(item.get("outcome_status", "")),
        ),
    )
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(memory, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return memory


def summarize_pr_guardrail_outcome_memory(memory: dict[str, Any]) -> dict[str, Any]:
    records = memory.get("records", []) if isinstance(memory.get("records"), list) else []
    statuses = Counter(str(record.get("outcome_status", "")) for record in records)
    decisions = Counter(str(record.get("decision_status", "")) for record in records)
    merged_count = sum(1 for record in records if bool(record.get("merged")))
    blocked_count = sum(1 for record in records if str(record.get("outcome_status", "")).startswith("blocked"))
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "automation_allowed": False,
        "change_allowed_now": False,
        "direct_to_main_allowed": False,
        "record_count": len(records),
        "merged_count": merged_count,
        "blocked_count": blocked_count,
        "counts_by_outcome_status": dict(sorted(statuses.items())),
        "counts_by_decision_status": dict(sorted(decisions.items())),
    }


def render_pr_guardrail_outcome_summary_markdown(summary: dict[str, Any]) -> str:
    outcome_counts = summary.get("counts_by_outcome_status", {})
    decision_counts = summary.get("counts_by_decision_status", {})
    lines = [
        "# PR guardrail outcome memory",
        "",
        f"- automation allowed: **{summary.get('automation_allowed', False)}**",
        f"- change allowed now: **{summary.get('change_allowed_now', False)}**",
        f"- direct-to-main allowed: **{summary.get('direct_to_main_allowed', False)}**",
        f"- records: **{summary.get('record_count', 0)}**",
        f"- merged: **{summary.get('merged_count', 0)}**",
        f"- blocked: **{summary.get('blocked_count', 0)}**",
        "",
        "## Outcomes",
        "",
    ]
    if isinstance(outcome_counts, dict) and outcome_counts:
        for status, count in sorted(outcome_counts.items()):
            lines.append(f"- `{status}`: {count}")
    else:
        lines.append("- none")
    lines.extend(["", "## Decisions", ""])
    if isinstance(decision_counts, dict) and decision_counts:
        for status, count in sorted(decision_counts.items()):
            lines.append(f"- `{status}`: {count}")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "This memory records reviewed PR-guardrail outcomes only. It does not make repository changes.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
