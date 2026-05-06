from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sdetkit import adaptive_diagnosis
from sdetkit.investigation_safe_fix_policy import route_investigation_safe_fix_policy

SCHEMA_VERSION = "sdetkit.pr_investigation_summary.v1"


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _first_diagnosis(payload: dict[str, Any]) -> dict[str, Any]:
    diagnoses = _as_list(payload.get("diagnoses"))
    first = diagnoses[0] if diagnoses and isinstance(diagnoses[0], dict) else {}
    return first


def _first_proof_commands(first: dict[str, Any]) -> list[str]:
    commands = _as_list(first.get("proof_commands"))
    return [str(command) for command in commands[:4]]


def _next_command(proof_commands: list[str]) -> str:
    return proof_commands[0] if proof_commands else "python -m sdetkit investigate failure --log <log> --format markdown"


def _safe_fix_status(policy: dict[str, Any]) -> str:
    if bool(policy.get("auto_fix_allowed_now")):
        return "allowed_now"
    if bool(policy.get("candidate_later")):
        return "candidate later"
    return "review required"


def build_pr_investigation_summary(
    *,
    log_text: str,
    surface: str = "",
    memory_seen_count: int = 0,
    memory_fixed_count: int = 0,
) -> dict[str, Any]:
    diagnosis = adaptive_diagnosis.analyze_evidence(log_text=log_text)
    first = _first_diagnosis(diagnosis)
    classification = str(first.get("code", "UNKNOWN_REVIEW_REQUIRED"))
    policy = route_investigation_safe_fix_policy(classification)
    proof_commands = _first_proof_commands(first)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "diagnostic_only": True,
        "automation_allowed": False,
        "command": "pr investigation summary",
        "classification": classification,
        "confidence": str(first.get("confidence", diagnosis.get("confidence", "medium"))),
        "surface": surface.strip(),
        "safe_fix_status": _safe_fix_status(policy),
        "auto_fix_allowed_now": False,
        "requires_human_review": True,
        "next_command": _next_command(proof_commands),
        "proof_commands": proof_commands,
        "memory": {
            "seen_count": max(0, int(memory_seen_count)),
            "manual_fix_count": max(0, int(memory_fixed_count)),
        },
        "safe_fix_policy": policy,
        "diagnosis": diagnosis,
    }
    payload["markdown"] = render_pr_investigation_summary_markdown(payload)
    return payload


def render_pr_investigation_summary_markdown(payload: dict[str, Any]) -> str:
    memory = payload.get("memory", {}) if isinstance(payload.get("memory"), dict) else {}
    lines = [
        "### Failure investigation",
        "",
        f"- classification: **{payload.get('classification', 'UNKNOWN_REVIEW_REQUIRED')}**",
        f"- confidence: **{payload.get('confidence', 'medium')}**",
        f"- safe-fix status: **{payload.get('safe_fix_status', 'review required')}**",
        f"- automation allowed: **{payload.get('automation_allowed', False)}**",
        f"- next command: `{payload.get('next_command', '')}`",
        "- memory: seen {seen} time(s), fixed manually {fixed} time(s)".format(
            seen=memory.get("seen_count", 0), fixed=memory.get("manual_fix_count", 0)
        ),
    ]
    surface = str(payload.get("surface", "")).strip()
    if surface:
        lines.append(f"- surface: **{surface}**")
    proof = _as_list(payload.get("proof_commands"))
    if proof:
        lines.extend(["", "#### Proof commands", "", "```bash"])
        lines.extend(str(command) for command in proof[:4])
        lines.append("```")
    return "\n".join(lines).rstrip() + "\n"


def write_pr_investigation_summary(payload: dict[str, Any], out: str | Path) -> Path:
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        path.write_text(render_pr_investigation_summary_markdown(payload), encoding="utf-8")
    return path
