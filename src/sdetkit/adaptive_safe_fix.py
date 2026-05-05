from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.adaptive_safe_fix.v1"
SOURCE_SCHEMA_VERSION = "sdetkit.adaptive.diagnosis.v1"
SAFE_FORMAT_CODE = "PRE_COMMIT_FORMAT_DRIFT"
SAFE_RUFF_FIXABLE_CODE = "RUFF_FIXABLE_LINT"
ACTIONABLE_STATUSES = {"needs_attention", "needs_fix"}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_text(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _load_diagnosis(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    if payload.get("schema_version") != SOURCE_SCHEMA_VERSION:
        raise ValueError(f"unsupported adaptive diagnosis schema in {path}")
    return payload


def _target_files(diagnosis: dict[str, Any]) -> list[str]:
    files = [_safe_text(value) for value in _as_list(diagnosis.get("affected_files"))]
    return [value for value in files if value]


def _format_targets(diagnosis: dict[str, Any]) -> str:
    files = _target_files(diagnosis)
    return " ".join(files) if files else "<touched-python-files>"


def _first_diagnosis(payload: dict[str, Any]) -> dict[str, Any]:
    for item in _as_list(payload.get("diagnoses")):
        row = _as_dict(item)
        if row:
            return row
    return {}


def _is_safe_format_plan(payload: dict[str, Any], diagnosis: dict[str, Any]) -> bool:
    status = str(payload.get("status", "unknown"))
    if status not in ACTIONABLE_STATUSES:
        return False
    if diagnosis.get("code") != SAFE_FORMAT_CODE:
        return False
    if diagnosis.get("severity") not in {"low", "medium"}:
        return False
    if diagnosis.get("confidence") != "high":
        return False
    return True


def _is_safe_ruff_fixable_plan(payload: dict[str, Any], diagnosis: dict[str, Any]) -> bool:
    status = str(payload.get("status", "unknown"))
    if status not in ACTIONABLE_STATUSES:
        return False
    if diagnosis.get("code") != SAFE_RUFF_FIXABLE_CODE:
        return False
    if diagnosis.get("severity") not in {"low", "medium"}:
        return False
    if diagnosis.get("confidence") != "high":
        return False
    return bool(_target_files(diagnosis))


def build_plan(payload: dict[str, Any]) -> dict[str, Any]:
    diagnosis = _first_diagnosis(payload)
    code = str(diagnosis.get("code", "UNKNOWN") or "UNKNOWN")
    targets = _format_targets(diagnosis)
    safe = _is_safe_format_plan(payload, diagnosis)
    ruff_safe = _is_safe_ruff_fixable_plan(payload, diagnosis)

    if safe:
        commands = [
            f"PYTHONPATH=src python -m ruff format {targets}",
            f"PYTHONPATH=src python -m ruff format --check {targets}",
            f"PYTHONPATH=src python -m ruff check {targets}",
        ]
        proof_commands = [
            f"PYTHONPATH=src python -m ruff format --check {targets}",
            "PYTHONPATH=src python -m pytest -q <targeted-tests>",
        ]
        return {
            "schema_version": SCHEMA_VERSION,
            "source_schema_version": str(payload.get("schema_version", "")),
            "ok": True,
            "source_status": str(payload.get("status", "unknown")),
            "source_code": code,
            "safe_to_auto_fix": True,
            "fix_type": "format_only",
            "confidence": "high",
            "requires_human_review": False,
            "reason": (
                "Formatter drift is safe to plan because the primary diagnosis is "
                "PRE_COMMIT_FORMAT_DRIFT with high confidence and low/medium severity."
            ),
            "commands": commands,
            "proof_commands": proof_commands,
            "affected_files": _as_list(diagnosis.get("affected_files")),
        }

    if ruff_safe:
        commands = [
            f"PYTHONPATH=src python -m ruff check --fix {targets}",
            f"PYTHONPATH=src python -m ruff format {targets}",
            f"PYTHONPATH=src python -m ruff check {targets}",
            f"PYTHONPATH=src python -m ruff format --check {targets}",
        ]
        proof_commands = [
            f"PYTHONPATH=src python -m ruff check {targets}",
            f"PYTHONPATH=src python -m ruff format --check {targets}",
            "PYTHONPATH=src python -m pytest -q <targeted-tests>",
        ]
        return {
            "schema_version": SCHEMA_VERSION,
            "source_schema_version": str(payload.get("schema_version", "")),
            "ok": True,
            "source_status": str(payload.get("status", "unknown")),
            "source_code": code,
            "safe_to_auto_fix": True,
            "fix_type": "ruff_fixable_lint",
            "confidence": "high",
            "requires_human_review": False,
            "reason": (
                "Ruff reported only narrow fixable lint with known affected files; "
                "F401 and I001 are treated as safe mechanical fixes after proof."
            ),
            "commands": commands,
            "proof_commands": proof_commands,
            "affected_files": _as_list(diagnosis.get("affected_files")),
        }

    reason = "No diagnosis was available to plan from."
    if diagnosis:
        reason = f"{code} requires human review; this planner only auto-plans formatter drift and narrow Ruff fixable lint."
    return {
        "schema_version": SCHEMA_VERSION,
        "source_schema_version": str(payload.get("schema_version", "")),
        "ok": True,
        "source_status": str(payload.get("status", "unknown")),
        "source_code": code,
        "safe_to_auto_fix": False,
        "fix_type": "review_required",
        "confidence": str(diagnosis.get("confidence", payload.get("confidence", "unknown"))),
        "requires_human_review": True,
        "reason": reason,
        "commands": [],
        "proof_commands": _as_list(diagnosis.get("proof_commands"))[:3],
        "affected_files": _as_list(diagnosis.get("affected_files")),
    }


def plan_from_file(diagnosis_path: Path, out_path: Path | None = None) -> dict[str, Any]:
    payload = _load_diagnosis(diagnosis_path)
    plan = build_plan(payload)
    plan["source_path"] = diagnosis_path.as_posix()
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return plan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.adaptive_safe_fix")
    parser.add_argument("diagnosis_json")
    parser.add_argument("--out", default="")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        plan = plan_from_file(Path(args.diagnosis_json), Path(args.out) if args.out else None)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(json.dumps(plan, indent=2, sort_keys=True))
    else:
        print(f"safe_to_auto_fix: {str(plan['safe_to_auto_fix']).lower()}")
        print(f"fix_type: {plan['fix_type']}")
        print(f"requires_human_review: {str(plan['requires_human_review']).lower()}")
        print(f"reason: {plan['reason']}")
        for command in plan.get("commands", []):
            print(f"command: {command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
