from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.maintenance.proof_checklist.v1"

DIAGNOSTIC_ONLY = True
AUTOMATION_ALLOWED = False

PROOF_BY_DIAGNOSIS = {
    "PRE_COMMIT_FORMAT_DRIFT": {
        "required_proof": "Attach clean pre-commit output after formatter changes.",
        "proof_commands": ["python -m pre_commit run -a"],
        "required_artifacts": ["pre-commit output", "git diff/stat"],
    },
    "RUFF_FIXABLE_LINT": {
        "required_proof": "Attach clean Ruff check and format output after the fix.",
        "proof_commands": [
            "python -m ruff check src tests",
            "python -m ruff format --check src tests",
        ],
        "required_artifacts": ["ruff check output", "ruff format output"],
    },
    "MISSING_TEST_DEPENDENCY": {
        "required_proof": "Attach dependency installation output and rerun the failed test command.",
        "proof_commands": ["python -m pip install -r requirements-test.txt", "python -m pytest -q"],
        "required_artifacts": ["install output", "pytest output"],
    },
    "PYTHON_RUNTIME_COMPATIBILITY": {
        "required_proof": "Attach supported Python version output and focused compatibility test results.",
        "proof_commands": ["python --version", "python -m pytest -q"],
        "required_artifacts": ["python version", "pytest output"],
    },
    "LOCAL_ENVIRONMENT_FRICTION": {
        "required_proof": "Attach rerun evidence from a native filesystem or clean environment.",
        "proof_commands": ["python -m venv .venv", "python -m pytest -q"],
        "required_artifacts": ["environment note", "rerun output"],
    },
    "BROKEN_TEST_DOUBLE": {
        "required_proof": "Attach focused test output proving the test harness fix.",
        "proof_commands": ["python -m pytest -q <focused-test>"],
        "required_artifacts": ["focused pytest output"],
    },
    "MISSING_PUBLIC_API_PARITY": {
        "required_proof": "Attach focused parity tests for the missing public surface.",
        "proof_commands": ["python -m pytest -q <focused-parity-test>"],
        "required_artifacts": ["parity test output"],
    },
    "GIT_BRANCH_DIVERGED": {
        "required_proof": "Attach fetch/rebase proof and rerun checks after the branch is synchronized.",
        "proof_commands": ["git fetch origin <branch>", "git rebase origin/<branch>", "python -m pre_commit run -a"],
        "required_artifacts": ["git rebase output", "pre-commit output"],
    },
    "REMOTE_BRANCH_DRIFT": {
        "required_proof": "Attach proof rerun after rebasing on the updated remote branch.",
        "proof_commands": ["git rebase origin/<branch>", "python -m pre_commit run -a"],
        "required_artifacts": ["git rebase output", "pre-commit output"],
    },
    "PRODUCT_LOGIC_FAILURE": {
        "required_proof": "Attach the focused failing test before the fix and passing output after the fix.",
        "proof_commands": ["python -m pytest -q <focused-test>"],
        "required_artifacts": ["before/after focused pytest output"],
    },
    "UNKNOWN_REVIEW_REQUIRED": {
        "required_proof": "Attach the first actionable traceback or command log before progressing.",
        "proof_commands": ["python -m pre_commit run -a"],
        "required_artifacts": ["failure log", "review note"],
    },
}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


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


def _proof_for_diagnosis(diagnosis_class: str) -> dict[str, Any]:
    return PROOF_BY_DIAGNOSIS.get(diagnosis_class, PROOF_BY_DIAGNOSIS["UNKNOWN_REVIEW_REQUIRED"])


def _proof_status(item: dict[str, Any]) -> str:
    explicit = _text(item.get("proof_status"))
    if explicit:
        return explicit
    evidence = _as_list(item.get("proof_evidence")) or _as_list(item.get("attached_proof"))
    return "complete" if evidence else "missing"


def _checklist_item(item: dict[str, Any]) -> dict[str, Any]:
    diagnosis_class = _text(item.get("diagnosis_class")) or "UNKNOWN_REVIEW_REQUIRED"
    proof = _proof_for_diagnosis(diagnosis_class)
    status = _proof_status(item)
    can_progress = status == "complete"

    return {
        "rank": item.get("rank", ""),
        "signal": _text(item.get("signal")) or _text(item.get("memory_lookup_key")),
        "memory_lookup_key": _text(item.get("memory_lookup_key")),
        "diagnosis_class": diagnosis_class,
        "category": _text(item.get("category")),
        "risk_level": _text(item.get("risk_level")),
        "safe_fix_route": _text(item.get("safe_fix_route")),
        "required_proof": proof["required_proof"],
        "proof_status": status,
        "proof_commands": list(proof["proof_commands"]),
        "required_artifacts": list(proof["required_artifacts"]),
        "can_progress_to_candidate": can_progress,
        "blocking_reason": "" if can_progress else "Required proof has not been attached.",
    }


def build_proof_checklist(action_categories_payload: dict[str, Any]) -> dict[str, Any]:
    items = [
        _checklist_item(_as_dict(item))
        for item in _as_list(action_categories_payload.get("items"))
        if _as_dict(item)
    ]
    complete_count = sum(1 for item in items if item["proof_status"] == "complete")
    missing_count = sum(1 for item in items if item["proof_status"] != "complete")

    return {
        "schema_version": SCHEMA_VERSION,
        "ok": bool(action_categories_payload.get("ok", True)),
        "source_schema_version": _text(action_categories_payload.get("schema_version")),
        "diagnostic_only": DIAGNOSTIC_ONLY,
        "automation_allowed": AUTOMATION_ALLOWED,
        "proof_item_count": len(items),
        "complete_count": complete_count,
        "missing_count": missing_count,
        "items": items,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Maintenance proof checklist",
        "",
        f"- diagnostic only: **{payload.get('diagnostic_only', True)}**",
        f"- automation allowed: **{payload.get('automation_allowed', False)}**",
        f"- proof items: **{payload.get('proof_item_count', 0)}**",
        f"- complete proof: **{payload.get('complete_count', 0)}**",
        f"- missing proof: **{payload.get('missing_count', 0)}**",
    ]

    items = _as_list(payload.get("items"))
    if not items:
        lines.extend(["", "No maintenance proof items were generated."])
        return "\n".join(lines).rstrip() + "\n"

    lines.extend(
        [
            "",
            "## Proof checklist",
            "",
            "| Rank | Signal | Diagnosis | Proof status | Required proof | Can progress |",
            "|---:|---|---|---|---|---|",
        ]
    )
    for item in items:
        row = _as_dict(item)
        lines.append(
            f"| {row.get('rank', '')} | {_cell(row.get('signal'))} | "
            f"{_cell(row.get('diagnosis_class'))} | {_cell(row.get('proof_status'))} | "
            f"{_cell(row.get('required_proof'))} | {bool(row.get('can_progress_to_candidate'))} |"
        )

    lines.extend(["", "## Proof commands", ""])
    for item in items[:8]:
        row = _as_dict(item)
        commands = ", ".join(f"`{cmd}`" for cmd in _as_list(row.get("proof_commands")))
        lines.append(f"- **{_cell(row.get('signal'))}**: {commands}")

    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.maintenance_proof_checklist")
    parser.add_argument("--action-categories-json", required=True)
    parser.add_argument("--out-json")
    parser.add_argument("--out-md")
    parser.add_argument("--format", choices=["json", "md"], default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = build_proof_checklist(_read_json(args.action_categories_json) or {})
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
