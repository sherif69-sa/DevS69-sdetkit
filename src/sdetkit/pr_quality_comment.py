from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _first_text(values: list[Any], fallback: str) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return fallback


def _matching_fix_plan(payload: dict[str, Any], code: str) -> dict[str, Any]:
    for item in _as_list(payload.get("fix_plan")):
        row = _as_dict(item)
        if str(row.get("code", "")) == code:
            return row
    return (
        _as_dict(_as_list(payload.get("fix_plan"))[0]) if _as_list(payload.get("fix_plan")) else {}
    )


REVIEW_FIRST_DIAGNOSIS_CODES = {"UNKNOWN", "UNKNOWN_REVIEW_REQUIRED"}


def _is_review_first_diagnosis(code: str) -> bool:
    return code in REVIEW_FIRST_DIAGNOSIS_CODES


def _diagnosis_heading(code: str) -> str:
    if _is_review_first_diagnosis(code):
        return "### Review-first Adaptive Diagnosis"
    return "### Adaptive Diagnosis"


def _next_step_heading(code: str) -> str:
    if _is_review_first_diagnosis(code):
        return "Human review route:"
    return "Smallest safe fix:"


def _auto_fix_status(code: str, fix_plan: dict[str, Any]) -> str:
    if fix_plan.get("safe_to_auto_fix") is not True:
        if _is_review_first_diagnosis(code):
            return "SDETKit will keep this review-first because the current evidence is not safe for automatic remediation."
        return "SDETKit will keep this as a human-reviewed adaptive diagnosis because the current evidence is not safe for automatic remediation."
    if code == "RUFF_FIXABLE_LINT":
        return "SDETKit can auto-fix this only when the safe plan, affected-file scope, remediation proof, and same-repo branch guards all pass."
    if code == "PRE_COMMIT_FORMAT_DRIFT":
        return "SDETKit can auto-fix this when the format-only safe plan, remediation proof, and same-repo branch guards all pass."
    return "SDETKit can auto-fix this only when the safe mechanical plan and proof gates pass."


def diagnosis_comment_contract(payload: dict[str, Any]) -> dict[str, Any]:
    status = str(payload.get("status", "unknown"))
    diagnoses = _as_list(payload.get("diagnoses"))
    if status in {"clear", "monitor"} or not diagnoses:
        return {
            "should_render": False,
            "status": status,
            "code": "",
            "review_first": False,
            "safe_to_auto_fix": False,
            "heading": "",
            "route_heading": "",
            "reason": "No actionable adaptive diagnosis comment is needed.",
        }

    first = _as_dict(diagnoses[0])
    code = str(first.get("code", "UNKNOWN"))
    fix_plan = _matching_fix_plan(payload, code)
    review_first = _is_review_first_diagnosis(code)
    safe_to_auto_fix = fix_plan.get("safe_to_auto_fix") is True

    return {
        "should_render": True,
        "status": status,
        "code": code,
        "review_first": review_first,
        "safe_to_auto_fix": safe_to_auto_fix,
        "heading": _diagnosis_heading(code),
        "route_heading": _next_step_heading(code),
        "reason": _auto_fix_status(code, fix_plan),
    }


def render_adaptive_diagnosis_comment(payload: dict[str, Any]) -> str:
    if payload.get("status") in {"clear", "monitor"}:
        return ""

    diagnoses = _as_list(payload.get("diagnoses"))
    if not diagnoses:
        return ""

    first = _as_dict(diagnoses[0])
    code = str(first.get("code", "UNKNOWN"))
    fixes = _as_list(first.get("recommended_fix"))
    commands = _as_list(first.get("proof_commands"))
    fix_plan = _matching_fix_plan(payload, code)

    lines = [
        _diagnosis_heading(code),
        f"- status: `{payload.get('status', 'unknown')}`",
        f"- risk score: `{payload.get('risk_score', 'unknown')}`",
        f"- confidence: `{payload.get('confidence', 'unknown')}`",
        f"- primary issue: **{first.get('title', 'Unknown issue')}**",
        f"- diagnosis code: `{code}`",
        "",
        "Why developers miss it:",
        str(first.get("why_developers_miss_it", "No hidden-risk explanation available.")),
        "",
        _next_step_heading(code),
        f"- {_first_text(fixes, 'Inspect the first failing evidence item and apply the smallest safe change.')}",
        "",
        "Proof command:",
        f"- `{_first_text(commands, 'PYTHONPATH=src python -m pytest -q <targeted-tests>')}`",
        "",
        "Auto-fix status:",
        f"- {_auto_fix_status(code, fix_plan)}",
    ]

    if code == "RUFF_FIXABLE_LINT":
        lines.extend(
            [
                "",
                "Ruff fixable lint route:",
                "- Applies only to the narrow F401/I001 mechanical allowlist.",
                "- Runs `ruff check --fix` only on affected files, then proves Ruff check and format check.",
                "- Logic-risk Ruff findings remain review-first.",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def render_from_file(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return render_adaptive_diagnosis_comment(payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.pr_quality_comment")
    parser.add_argument("adaptive_diagnosis_json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        rendered = render_from_file(Path(args.adaptive_diagnosis_json))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
