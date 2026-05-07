from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.operator_brief.v1"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_text(value: Any, limit: int = 240) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _load_optional_json(path: str) -> dict[str, Any]:
    if not path:
        return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _prefixed_value(values: Any, prefix: str) -> str:
    for value in _as_list(values):
        text = str(value or "")
        if text.startswith(prefix):
            return text.removeprefix(prefix)
    return ""


def _gate_result(gate: dict[str, Any]) -> dict[str, Any]:
    if not gate:
        return {
            "status": "unknown",
            "decision": "UNKNOWN",
            "ok": None,
            "summary": "No gate artifact supplied.",
        }
    ok = gate.get("ok")
    decision = str(gate.get("decision") or gate.get("status") or "UNKNOWN").upper()
    failed_steps = _as_list(gate.get("failed_steps")) or _as_list(gate.get("failures"))
    if ok is True or decision in {"SHIP", "PASS", "PASSED", "OK"}:
        status = "ship"
    elif ok is False or failed_steps or decision in {"NO_SHIP", "FAIL", "FAILED"}:
        status = "no_ship"
    else:
        status = "unknown"
    summary = f"Gate status is {status}."
    if failed_steps:
        summary += f" Failed steps: {', '.join(_safe_text(step, 80) for step in failed_steps[:5])}."
    return {"status": status, "decision": decision, "ok": ok, "summary": summary}


def _primary_diagnosis(diagnosis: dict[str, Any]) -> dict[str, Any]:
    diagnoses = [_as_dict(item) for item in _as_list(diagnosis.get("diagnoses"))]
    primary = diagnoses[0] if diagnoses else {}
    evidence = _as_list(primary.get("evidence"))
    proof_commands = _as_list(primary.get("proof_commands"))
    return {
        "status": str(diagnosis.get("status", "unknown")),
        "summary": _safe_text(diagnosis.get("summary") or "No adaptive diagnosis supplied.", 500),
        "code": str(primary.get("code", "NONE")),
        "title": _safe_text(primary.get("title") or "No diagnosis", 240),
        "severity": str(primary.get("severity", "unknown")),
        "confidence": str(primary.get("confidence", "unknown")),
        "candidate_scenarios": _prefixed_value(evidence, "candidate_scenarios="),
        "candidate_calibration": _prefixed_value(evidence, "candidate_calibration="),
        "first_proof_command": _safe_text(proof_commands[0] if proof_commands else "", 300),
        "recommended_fix": [
            _safe_text(item, 260) for item in _as_list(primary.get("recommended_fix"))[:4]
        ],
    }


def _safe_fix_decision(diagnosis: dict[str, Any], safe_fix_plan: dict[str, Any]) -> dict[str, Any]:
    plan = _as_dict(safe_fix_plan)
    if plan:
        safe = bool(plan.get("safe_to_auto_fix", False))
        requires_review = bool(plan.get("requires_human_review", not safe))
        return {
            "safe_to_auto_fix": safe,
            "requires_human_review": requires_review,
            "source": "safe_fix_plan",
            "reason": _safe_text(
                plan.get("reason") or plan.get("title") or "safe-fix plan supplied", 300
            ),
        }
    fix_plan = [_as_dict(item) for item in _as_list(diagnosis.get("fix_plan"))]
    if fix_plan:
        first = fix_plan[0]
        safe = bool(first.get("safe_to_auto_fix", False))
        return {
            "safe_to_auto_fix": safe,
            "requires_human_review": not safe,
            "source": "adaptive_diagnosis.fix_plan",
            "reason": _safe_text(
                first.get("title") or first.get("code") or "adaptive fix plan", 300
            ),
        }
    return {
        "safe_to_auto_fix": False,
        "requires_human_review": True,
        "source": "none",
        "reason": "No safe-fix plan supplied; keep review-first posture.",
    }


def _next_owner_action(
    gate: dict[str, Any], diagnosis: dict[str, Any], safe_fix: dict[str, Any]
) -> str:
    gate_status = str(gate.get("status", "unknown"))
    diagnosis_status = str(diagnosis.get("status", "unknown"))
    if gate_status == "ship" and diagnosis_status in {"clear", "monitor", "unknown"}:
        return "Owner action: proceed with normal release review; no adaptive remediation block is present."
    if bool(safe_fix.get("safe_to_auto_fix")):
        return "Owner action: review the scoped safe-fix plan, run the first proof command, and only then use guarded remediation."
    first_proof = diagnosis.get("first_proof_command")
    if first_proof:
        return f"Owner action: run `{first_proof}` and review the candidate scenario before changing code."
    return "Owner action: collect a focused failing log or gate artifact before remediation."


def build_operator_brief(
    *,
    gate: dict[str, Any] | None = None,
    diagnosis: dict[str, Any] | None = None,
    learning_summary: dict[str, Any] | None = None,
    safe_fix_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    gate_result = _gate_result(_as_dict(gate))
    primary = _primary_diagnosis(_as_dict(diagnosis))
    learning = _as_dict(learning_summary)
    calibration_summary = _as_dict(learning.get("calibration_summary"))
    safe_fix = _safe_fix_decision(_as_dict(diagnosis), _as_dict(safe_fix_plan))
    next_action = _next_owner_action(gate_result, primary, safe_fix)
    ok = gate_result["status"] == "ship" and primary["status"] in {"clear", "monitor", "unknown"}
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": ok,
        "gate_result": gate_result,
        "adaptive_diagnosis": primary,
        "learning_calibration": {
            "schema_version": str(learning.get("schema_version", "")),
            "calibration_summary": calibration_summary,
            "top_recurring_count": len(_as_list(learning.get("top_recurring_scenarios"))),
            "weakest_lane_count": len(_as_list(learning.get("weakest_lanes"))),
        },
        "safe_fix_decision": safe_fix,
        "next_owner_action": next_action,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    gate = _as_dict(payload.get("gate_result"))
    diagnosis = _as_dict(payload.get("adaptive_diagnosis"))
    learning = _as_dict(payload.get("learning_calibration"))
    safe_fix = _as_dict(payload.get("safe_fix_decision"))
    lines = [
        "# SDETKit Operator Brief",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Overall OK: `{str(payload.get('ok')).lower()}`",
        "",
        "## Gate result",
        "",
        f"- Status: `{gate.get('status')}`",
        f"- Decision: `{gate.get('decision')}`",
        f"- Summary: {gate.get('summary')}",
        "",
        "## Adaptive diagnosis",
        "",
        f"- Status: `{diagnosis.get('status')}`",
        f"- Primary: `{diagnosis.get('code')}` — {diagnosis.get('title')}",
        f"- Severity / confidence: `{diagnosis.get('severity')}` / `{diagnosis.get('confidence')}`",
        f"- Summary: {diagnosis.get('summary')}",
    ]
    if diagnosis.get("candidate_scenarios"):
        lines.append(f"- Candidate scenarios: `{diagnosis.get('candidate_scenarios')}`")
    if diagnosis.get("candidate_calibration"):
        lines.append(f"- Candidate calibration: `{diagnosis.get('candidate_calibration')}`")
    if diagnosis.get("first_proof_command"):
        lines.append(f"- First proof command: `{diagnosis.get('first_proof_command')}`")
    fixes = _as_list(diagnosis.get("recommended_fix"))
    if fixes:
        lines += ["", "Recommended checks:"] + [f"- {fix}" for fix in fixes]
    lines += [
        "",
        "## Safe-fix decision",
        "",
        f"- Safe to auto-fix: `{str(safe_fix.get('safe_to_auto_fix')).lower()}`",
        f"- Requires human review: `{str(safe_fix.get('requires_human_review')).lower()}`",
        f"- Source: `{safe_fix.get('source')}`",
        f"- Reason: {safe_fix.get('reason')}",
        "",
        "## Learning calibration",
        "",
        f"- Summary schema: `{learning.get('schema_version')}`",
        f"- Calibration summary: `{json.dumps(_as_dict(learning.get('calibration_summary')), sort_keys=True)}`",
        f"- Top recurring scenarios: `{learning.get('top_recurring_count')}`",
        f"- Weakest lanes: `{learning.get('weakest_lane_count')}`",
        "",
        "## Next owner action",
        "",
        str(payload.get("next_owner_action", "")),
        "",
    ]
    return "\n".join(lines)


def render_pr_comment(payload: dict[str, Any]) -> str:
    gate = _as_dict(payload.get("gate_result"))
    diagnosis = _as_dict(payload.get("adaptive_diagnosis"))
    safe_fix = _as_dict(payload.get("safe_fix_decision"))
    gate_status = str(gate.get("status", "unknown"))
    diagnosis_status = str(diagnosis.get("status", "unknown"))

    if gate_status == "ship" and diagnosis_status in {"clear", "monitor", "unknown"}:
        return "### SDETKit release signal\n\n✅ Gate is ship-ready; no adaptive remediation block is present.\n"

    lines = [
        "### SDETKit adaptive handoff",
        "",
        f"- Gate: `{gate_status}`",
        f"- Adaptive status: `{diagnosis_status}`",
        f"- Primary: `{diagnosis.get('code')}` — {diagnosis.get('title')}",
    ]
    if diagnosis.get("candidate_scenarios"):
        lines.append(f"- Candidate scenarios: `{diagnosis.get('candidate_scenarios')}`")
    if diagnosis.get("candidate_calibration"):
        lines.append(f"- Calibration: `{diagnosis.get('candidate_calibration')}`")
    if diagnosis.get("first_proof_command"):
        lines.append(f"- First proof: `{diagnosis.get('first_proof_command')}`")

    lines += ["", "**Safe-fix status**"]
    if bool(safe_fix.get("safe_to_auto_fix")):
        lines.append(
            "- Scoped safe-fix path is available, but only after guardrails and proof artifacts pass."
        )
    else:
        lines.append("- Review-first: this evidence is not approved for automatic remediation.")

    lines += ["", "**Next owner action**", f"- {payload.get('next_owner_action', '')}"]
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.operator_brief")
    parser.add_argument("--gate", default="")
    parser.add_argument("--diagnosis", default="")
    parser.add_argument("--learning-summary", default="")
    parser.add_argument("--safe-fix-plan", default="")
    parser.add_argument("--format", choices=["md", "json", "comment"], default="md")
    parser.add_argument("--out", default="build/sdetkit/operator-brief.md")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    try:
        payload = build_operator_brief(
            gate=_load_optional_json(str(args.gate)),
            diagnosis=_load_optional_json(str(args.diagnosis)),
            learning_summary=_load_optional_json(str(args.learning_summary)),
            safe_fix_plan=_load_optional_json(str(args.safe_fix_plan)),
        )
        if args.format == "json":
            rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        elif args.format == "comment":
            rendered = render_pr_comment(payload)
        else:
            rendered = render_markdown(payload) + "\n"
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
