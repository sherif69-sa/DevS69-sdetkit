from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sdetkit import adaptive_diagnosis

SCHEMA_VERSION = "sdetkit.investigate.failure.v1"


def _read_log(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _payload_for_failure(log_text: str) -> dict[str, Any]:
    diagnosis_payload = adaptive_diagnosis.analyze_evidence(log_text=log_text)
    diagnoses = diagnosis_payload.get("diagnoses", [])
    first = diagnoses[0] if diagnoses and isinstance(diagnoses[0], dict) else {}

    fix_plan = diagnosis_payload.get("fix_plan", [])
    first_plan = fix_plan[0] if fix_plan and isinstance(fix_plan[0], dict) else {}

    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "diagnostic_only": True,
        "automation_allowed": False,
        "command": "investigate failure",
        "classification": str(first.get("code", "UNKNOWN_REVIEW_REQUIRED")),
        "confidence": str(first.get("confidence", "medium")),
        "safe_to_auto_fix": bool(first_plan.get("safe_to_auto_fix", False)),
        "requires_human_review": bool(first_plan.get("requires_human_review", True)),
        "summary": str(first.get("summary", "")),
        "why_it_matters": str(first.get("why_it_matters", "")),
        "next_actions": list(first.get("next_actions", []))
        if isinstance(first.get("next_actions"), list)
        else [],
        "proof_commands": list(first.get("proof_commands", []))
        if isinstance(first.get("proof_commands"), list)
        else [],
        "memory_lookup_key": str(first.get("memory_lookup_key", "")),
        "diagnosis": diagnosis_payload,
    }


def render_failure_markdown(payload: dict[str, Any]) -> str:
    proof = payload.get("proof_commands", [])
    actions = payload.get("next_actions", [])
    lines = [
        "# Failure investigation",
        "",
        f"- classification: **{payload.get('classification', 'UNKNOWN_REVIEW_REQUIRED')}**",
        f"- confidence: **{payload.get('confidence', 'medium')}**",
        f"- diagnostic only: **{payload.get('diagnostic_only', True)}**",
        f"- automation allowed: **{payload.get('automation_allowed', False)}**",
        f"- safe to auto-fix: **{payload.get('safe_to_auto_fix', False)}**",
        f"- requires human review: **{payload.get('requires_human_review', True)}**",
        "",
        "## Summary",
        "",
        str(payload.get("summary", "") or "No summary was available."),
        "",
        "## Why it matters",
        "",
        str(payload.get("why_it_matters", "") or "No additional context was available."),
    ]

    if actions:
        lines.extend(["", "## Next actions", ""])
        for action in actions:
            lines.append(f"- {action}")

    if proof:
        lines.extend(["", "## Proof commands", ""])
        lines.append("```bash")
        for command in proof:
            lines.append(str(command))
        lines.append("```")

    key = str(payload.get("memory_lookup_key", "")).strip()
    if key:
        lines.extend(["", "## Memory lookup key", "", f"`{key}`"])

    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit investigate")
    sub = parser.add_subparsers(dest="cmd", required=True)

    failure = sub.add_parser("failure", help="Classify a failure log with adaptive diagnosis")
    failure.add_argument("--log", required=True, help="Path to a text log to investigate")
    failure.add_argument("--format", choices=["json", "markdown"], default="json")
    failure.add_argument("--out", default="", help="Optional output file")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd != "failure":
        return 2

    try:
        payload = _payload_for_failure(_read_log(args.log))
    except OSError as exc:
        print(f"error={exc}", file=sys.stderr)
        return 2

    rendered = (
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
        if args.format == "json"
        else render_failure_markdown(payload)
    )

    if args.out:
        Path(args.out).write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
