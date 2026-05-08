from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.adaptive.fix_audit.v1"
SUMMARY_SCHEMA_VERSION = "sdetkit.adaptive.fix_audit.summary.v1"
SUPPORTED_PLAN_SCHEMAS = {
    "sdetkit.adaptive_safe_fix.v1": "safe_fix",
    "sdetkit.adaptive.patch_plan.v1": "assisted_patch_plan",
}
VALID_OUTCOMES = {"planned", "applied", "proof_passed", "proof_failed", "reverted", "rejected"}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_text(value: Any, limit: int = 300) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _plan_kind(payload: dict[str, Any]) -> str:
    schema = str(payload.get("schema_version", ""))
    if schema not in SUPPORTED_PLAN_SCHEMAS:
        raise ValueError(f"unsupported remediation plan schema: {schema}")
    return SUPPORTED_PLAN_SCHEMAS[schema]


def _proof_commands(payload: dict[str, Any]) -> list[str]:
    return [_safe_text(value, 240) for value in _as_list(payload.get("proof_commands"))][:6]


def _rollback_notes(payload: dict[str, Any]) -> list[str]:
    notes = [_safe_text(value, 240) for value in _as_list(payload.get("rollback_notes"))]
    if notes:
        return notes[:6]
    if bool(payload.get("safe_to_auto_fix")):
        return ["Revert the safe-fix commit if proof fails."]
    return ["Keep patch review scoped; revert human changes if focused proof fails."]


def _guardrails(payload: dict[str, Any]) -> dict[str, Any]:
    guardrails = _as_dict(payload.get("guardrails"))
    if guardrails:
        return guardrails
    return {
        "deterministic_reproduction_required": True,
        "post_fix_proof_required": True,
        "automation_mutation_allowed": bool(payload.get("safe_to_auto_fix")),
    }


def build_audit_record(
    plan: dict[str, Any], *, source_path: str = "", outcome: str = "planned", note: str = ""
) -> dict[str, Any]:
    if outcome not in VALID_OUTCOMES:
        raise ValueError(f"outcome must be one of {', '.join(sorted(VALID_OUTCOMES))}")
    kind = _plan_kind(plan)
    source_code = str(plan.get("source_code", "UNKNOWN") or "UNKNOWN")
    return {
        "schema_version": SCHEMA_VERSION,
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "outcome": outcome,
        "plan_kind": kind,
        "plan_schema_version": str(plan.get("schema_version", "")),
        "source_path": source_path,
        "source_code": source_code,
        "source_status": str(plan.get("source_status", "unknown")),
        "action_type": str(plan.get("fix_type", plan.get("status", kind))),
        "safe_to_auto_fix": bool(plan.get("safe_to_auto_fix")),
        "requires_human_review": bool(plan.get("requires_human_review", True)),
        "dry_run_only": bool(plan.get("dry_run_only", not bool(plan.get("safe_to_auto_fix")))),
        "changed_file_scope": _as_list(plan.get("affected_files"))[:8],
        "guardrails": _guardrails(plan),
        "proof_commands": _proof_commands(plan),
        "rollback_notes": _rollback_notes(plan),
        "reason": _safe_text(plan.get("reason"), 600),
        "note": _safe_text(note, 500),
    }


def append_record(db_path: Path, record: dict[str, Any]) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with db_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def read_records(db_path: Path) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(db_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at line {line_number}: {exc}") from exc
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _record_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("source_path", "")),
        str(row.get("plan_kind", "unknown")),
        str(row.get("source_code", "UNKNOWN")),
        str(row.get("action_type", "unknown")),
    )


def _proof_enforcement(records: list[dict[str, Any]]) -> dict[str, Any]:
    terminal_by_key: dict[tuple[str, str, str, str], set[str]] = {}
    pending_records: list[dict[str, Any]] = []
    failed_records: list[dict[str, Any]] = []
    for row in records:
        outcome = str(row.get("outcome", "unknown"))
        key = _record_key(row)
        if outcome in {"proof_passed", "proof_failed", "reverted", "rejected"}:
            terminal_by_key.setdefault(key, set()).add(outcome)
        if outcome in {"planned", "applied"}:
            pending_records.append(row)
        if outcome == "proof_failed":
            failed_records.append(row)
    missing_proof = [
        row
        for row in pending_records
        if not terminal_by_key.get(_record_key(row), set()).intersection(
            {"proof_passed", "proof_failed", "reverted", "rejected"}
        )
    ]
    if failed_records:
        recommendation = "NO_SHIP"
        next_owner_action = (
            "Block release signoff until failed remediation proof is fixed or reverted."
        )
    elif missing_proof:
        recommendation = "SHIP_WITH_CONTROLS"
        next_owner_action = (
            "Collect post-fix proof or rejection/revert records before final release signoff."
        )
    else:
        recommendation = "SHIP"
        next_owner_action = "Proof outcomes are complete for recorded remediation decisions."
    return {
        "recommendation": recommendation,
        "next_owner_action": next_owner_action,
        "missing_proof_count": len(missing_proof),
        "proof_failed_count": len(failed_records),
        "missing_proof_records": missing_proof[:10],
        "proof_failed_records": failed_records[:10],
    }


def summarize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    outcomes = Counter(str(row.get("outcome", "unknown")) for row in records)
    plan_kinds = Counter(str(row.get("plan_kind", "unknown")) for row in records)
    source_codes = Counter(str(row.get("source_code", "UNKNOWN")) for row in records)
    unsafe_mutation_attempts = [
        row
        for row in records
        if bool(_as_dict(row.get("guardrails")).get("automation_mutation_allowed"))
        and bool(row.get("requires_human_review"))
    ]
    proof = _proof_enforcement(records)
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "ok": not unsafe_mutation_attempts and proof["recommendation"] != "NO_SHIP",
        "recommendation": proof["recommendation"],
        "next_owner_action": proof["next_owner_action"],
        "record_count": len(records),
        "outcomes": dict(sorted(outcomes.items())),
        "plan_kinds": dict(sorted(plan_kinds.items())),
        "top_source_codes": [
            {"code": code, "count": count} for code, count in source_codes.most_common(10)
        ],
        "unsafe_mutation_attempt_count": len(unsafe_mutation_attempts),
        "missing_proof_count": proof["missing_proof_count"],
        "proof_failed_count": proof["proof_failed_count"],
        "missing_proof_records": proof["missing_proof_records"],
        "proof_failed_records": proof["proof_failed_records"],
        "latest_records": records[-5:],
    }


def render_text(payload: dict[str, Any]) -> str:
    if payload.get("schema_version") == SUMMARY_SCHEMA_VERSION:
        lines = [
            f"schema_version={payload['schema_version']}",
            f"ok={str(payload['ok']).lower()}",
            f"recommendation={payload['recommendation']}",
            f"record_count={payload['record_count']}",
            f"unsafe_mutation_attempt_count={payload['unsafe_mutation_attempt_count']}",
            f"missing_proof_count={payload['missing_proof_count']}",
            f"proof_failed_count={payload['proof_failed_count']}",
        ]
        for row in _as_list(payload.get("top_source_codes"))[:5]:
            item = _as_dict(row)
            lines.append(f"source_code={item.get('code')}|count={item.get('count')}")
        return "\n".join(lines) + "\n"
    return (
        f"schema_version={payload['schema_version']}\n"
        f"outcome={payload['outcome']}\n"
        f"plan_kind={payload['plan_kind']}\n"
        f"source_code={payload['source_code']}\n"
        f"safe_to_auto_fix={str(payload['safe_to_auto_fix']).lower()}\n"
        f"requires_human_review={str(payload['requires_human_review']).lower()}\n"
    )


def record_from_file(
    plan_path: Path, db_path: Path, *, outcome: str = "planned", note: str = ""
) -> dict[str, Any]:
    plan = _load_json(plan_path)
    record = build_audit_record(plan, source_path=plan_path.as_posix(), outcome=outcome, note=note)
    append_record(db_path, record)
    return record


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.adaptive_fix_audit")
    sub = parser.add_subparsers(dest="cmd", required=True)
    record = sub.add_parser("record", help="Append a remediation plan audit record")
    record.add_argument("plan_json")
    record.add_argument("--db", default=".sdetkit/adaptive-fix-audit.jsonl")
    record.add_argument("--outcome", choices=sorted(VALID_OUTCOMES), default="planned")
    record.add_argument("--note", default="")
    record.add_argument("--format", choices=["text", "json"], default="text")
    summarize = sub.add_parser("summarize", help="Summarize adaptive fix-audit records")
    summarize.add_argument("--db", default=".sdetkit/adaptive-fix-audit.jsonl")
    summarize.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "record":
            payload = record_from_file(
                Path(args.plan_json), Path(args.db), outcome=str(args.outcome), note=str(args.note)
            )
        else:
            payload = summarize_records(read_records(Path(args.db)))
        if args.format == "json":
            sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        else:
            sys.stdout.write(render_text(payload))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
