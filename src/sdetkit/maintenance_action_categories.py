from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.maintenance.action_categories.v1"

DIAGNOSTIC_ONLY = True
AUTOMATION_ALLOWED = False

REVIEW_FIRST = "review_first"
CANDIDATE_LATER = "candidate_later"
COMMAND_GUIDANCE = "command_guidance"
POLICY_REQUIRED = "policy_required"

CATEGORY_BY_DIAGNOSIS = {
    "PRE_COMMIT_FORMAT_DRIFT": ("formatting", "low", CANDIDATE_LATER),
    "RUFF_FIXABLE_LINT": ("lint", "low", CANDIDATE_LATER),
    "MISSING_TEST_DEPENDENCY": ("dependency", "medium", REVIEW_FIRST),
    "PYTHON_RUNTIME_COMPATIBILITY": ("runtime", "high", REVIEW_FIRST),
    "LOCAL_ENVIRONMENT_FRICTION": ("environment", "medium", COMMAND_GUIDANCE),
    "BROKEN_TEST_DOUBLE": ("tests", "medium", REVIEW_FIRST),
    "MISSING_PUBLIC_API_PARITY": ("product_api", "high", REVIEW_FIRST),
    "GIT_BRANCH_DIVERGED": ("git_workflow", "medium", COMMAND_GUIDANCE),
    "REMOTE_BRANCH_DRIFT": ("git_workflow", "medium", COMMAND_GUIDANCE),
    "PRODUCT_LOGIC_FAILURE": ("product_logic", "high", REVIEW_FIRST),
    "PYTEST_ASSERTION_FAILURE": ("tests", "high", REVIEW_FIRST),
    "PYTEST_IMPORT_FAILURE": ("tests", "high", REVIEW_FIRST),
    "RUFF_LINT_FAILURE": ("lint", "medium", REVIEW_FIRST),
    "MYPY_TYPE_CONTRACT_DRIFT": ("typing", "medium", REVIEW_FIRST),
    "UNKNOWN_REVIEW_REQUIRED": ("unknown", "medium", REVIEW_FIRST),
}

DIAGNOSIS_HINTS = {
    "ruff": "RUFF_FIXABLE_LINT",
    "format": "PRE_COMMIT_FORMAT_DRIFT",
    "pre-commit": "PRE_COMMIT_FORMAT_DRIFT",
    "pytest": "PRODUCT_LOGIC_FAILURE",
    "test": "PRODUCT_LOGIC_FAILURE",
    "dependency": "MISSING_TEST_DEPENDENCY",
    "python-version": "PYTHON_RUNTIME_COMPATIBILITY",
    "runtime": "PYTHON_RUNTIME_COMPATIBILITY",
    "annotation": "UNKNOWN_REVIEW_REQUIRED",
    "workflow": "UNKNOWN_REVIEW_REQUIRED",
    "security": "UNKNOWN_REVIEW_REQUIRED",
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


def _item_text(item: dict[str, Any]) -> str:
    parts = [
        item.get("diagnosis_class"),
        item.get("diagnosis_code"),
        item.get("code"),
        item.get("source_code"),
        item.get("memory_lookup_key"),
        item.get("signal"),
        item.get("title"),
        item.get("source"),
        item.get("proof_needed"),
        item.get("recommended_action"),
    ]
    return " ".join(_text(part) for part in parts).lower()


def infer_diagnosis_class(item: dict[str, Any]) -> str:
    for key in ("diagnosis_class", "diagnosis_code", "code", "source_code"):
        value = _text(item.get(key))
        if value in CATEGORY_BY_DIAGNOSIS:
            return value

    text = _item_text(item)
    for hint, diagnosis in DIAGNOSIS_HINTS.items():
        if hint in text:
            return diagnosis

    return "UNKNOWN_REVIEW_REQUIRED"


def _route_for_item(item: dict[str, Any], diagnosis_class: str, default_route: str) -> str:
    eligibility = _text(item.get("eligibility"))
    readiness = _text(item.get("automation_readiness"))

    if default_route == CANDIDATE_LATER:
        if eligibility == "ELIGIBLE_PENDING_POLICY" and readiness == "AUTOMATION_READY":
            return POLICY_REQUIRED
        return CANDIDATE_LATER

    if default_route == COMMAND_GUIDANCE:
        return COMMAND_GUIDANCE

    return REVIEW_FIRST


def _reason(diagnosis_class: str, category: str, route: str) -> str:
    if route == CANDIDATE_LATER:
        return (
            f"{diagnosis_class} is a narrow mechanical class, but it still needs "
            "proof, trend history, and policy gates before automation."
        )
    if route == POLICY_REQUIRED:
        return (
            f"{diagnosis_class} has enough readiness signal to require an explicit "
            "policy PR before any auto-fix behavior."
        )
    if route == COMMAND_GUIDANCE:
        return (
            f"{diagnosis_class} is {category} guidance. It should explain the next "
            "operator command but must not mutate files."
        )
    return f"{diagnosis_class} is review-first and must not be auto-fixed."


def _category_item(item: dict[str, Any]) -> dict[str, Any]:
    diagnosis_class = infer_diagnosis_class(item)
    category, risk_level, default_route = CATEGORY_BY_DIAGNOSIS.get(
        diagnosis_class,
        CATEGORY_BY_DIAGNOSIS["UNKNOWN_REVIEW_REQUIRED"],
    )
    safe_fix_route = _route_for_item(item, diagnosis_class, default_route)
    review_required = safe_fix_route not in {CANDIDATE_LATER, POLICY_REQUIRED}

    return {
        "rank": item.get("rank", ""),
        "signal": _text(item.get("signal")) or _text(item.get("title")) or _text(item.get("memory_lookup_key")),
        "source": _text(item.get("source")),
        "memory_lookup_key": _text(item.get("memory_lookup_key")),
        "diagnosis_class": diagnosis_class,
        "category": category,
        "risk_level": risk_level,
        "safe_fix_route": safe_fix_route,
        "review_required": review_required,
        "reason": _reason(diagnosis_class, category, safe_fix_route),
    }


def build_action_categories(action_plan_payload: dict[str, Any]) -> dict[str, Any]:
    source_actions = _as_list(action_plan_payload.get("actions"))
    items = [_category_item(_as_dict(item)) for item in source_actions if _as_dict(item)]

    counts_by_category: dict[str, int] = {}
    counts_by_diagnosis: dict[str, int] = {}
    counts_by_route: dict[str, int] = {}
    for item in items:
        category = _text(item.get("category")) or "unknown"
        diagnosis = _text(item.get("diagnosis_class")) or "UNKNOWN_REVIEW_REQUIRED"
        route = _text(item.get("safe_fix_route")) or REVIEW_FIRST
        counts_by_category[category] = counts_by_category.get(category, 0) + 1
        counts_by_diagnosis[diagnosis] = counts_by_diagnosis.get(diagnosis, 0) + 1
        counts_by_route[route] = counts_by_route.get(route, 0) + 1

    return {
        "schema_version": SCHEMA_VERSION,
        "ok": bool(action_plan_payload.get("ok", True)),
        "source_schema_version": _text(action_plan_payload.get("schema_version")),
        "diagnostic_only": DIAGNOSTIC_ONLY,
        "automation_allowed": AUTOMATION_ALLOWED,
        "category_count": len(counts_by_category),
        "item_count": len(items),
        "counts_by_category": dict(sorted(counts_by_category.items())),
        "counts_by_diagnosis": dict(sorted(counts_by_diagnosis.items())),
        "counts_by_route": dict(sorted(counts_by_route.items())),
        "items": items,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Maintenance action categories",
        "",
        f"- diagnostic only: **{payload.get('diagnostic_only', True)}**",
        f"- automation allowed: **{payload.get('automation_allowed', False)}**",
        f"- categories: **{payload.get('category_count', 0)}**",
        f"- items: **{payload.get('item_count', 0)}**",
    ]

    categories = _as_dict(payload.get("counts_by_category"))
    if categories:
        lines.extend(
            [
                "",
                "## Category mix",
                "",
                "| Category | Count |",
                "|---|---:|",
            ]
        )
        for category, count in sorted(categories.items()):
            lines.append(f"| {_cell(category)} | {count} |")

    routes = _as_dict(payload.get("counts_by_route"))
    if routes:
        lines.extend(
            [
                "",
                "## Safe-fix route mix",
                "",
                "| Route | Count |",
                "|---|---:|",
            ]
        )
        for route, count in sorted(routes.items()):
            lines.append(f"| {_cell(route)} | {count} |")

    items = _as_list(payload.get("items"))
    if not items:
        lines.extend(["", "No maintenance actions were categorized."])
        return "\n".join(lines).rstrip() + "\n"

    lines.extend(
        [
            "",
            "## Classified actions",
            "",
            "| Rank | Category | Diagnosis | Risk | Route | Signal |",
            "|---:|---|---|---|---|---|",
        ]
    )
    for item in items:
        row = _as_dict(item)
        lines.append(
            f"| {row.get('rank', '')} | {_cell(row.get('category'))} | "
            f"{_cell(row.get('diagnosis_class'))} | {_cell(row.get('risk_level'))} | "
            f"{_cell(row.get('safe_fix_route'))} | {_cell(row.get('signal'))} |"
        )

    lines.extend(["", "## Review notes", ""])
    for item in items[:8]:
        row = _as_dict(item)
        lines.append(f"- **{_cell(row.get('signal'))}**: {_cell(row.get('reason'))}")

    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.maintenance_action_categories")
    parser.add_argument("--action-plan-json", required=True)
    parser.add_argument("--out-json")
    parser.add_argument("--out-md")
    parser.add_argument("--format", choices=["json", "md"], default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = build_action_categories(_read_json(args.action_plan_json) or {})
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
