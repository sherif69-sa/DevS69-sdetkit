from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sdetkit.trajectory_history_report import (
    build_history_summary,
    load_trajectory_records,
)

SCHEMA_VERSION = "sdetkit.trajectory_pattern_insights.v1"

JsonObject = dict[str, Any]


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _string(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes"}


def _decision(record: Mapping[str, Any]) -> JsonObject:
    return _as_dict(record.get("decision"))


def _diagnosis(record: Mapping[str, Any]) -> JsonObject:
    return _as_dict(record.get("diagnosis"))


def _risk_surface(record: Mapping[str, Any]) -> str:
    diagnosis = _diagnosis(record)
    return _string(diagnosis.get("risk_surface") or record.get("risk_surface") or "unknown")


def _failure_class(record: Mapping[str, Any]) -> str:
    diagnosis = _diagnosis(record)
    return _string(diagnosis.get("failure_class") or record.get("failure_class") or "unknown")


def _action(record: Mapping[str, Any]) -> str:
    return _string(record.get("action") or "unknown")


def _counter_rows(counter: Counter[str], *, minimum_count: int = 1) -> list[JsonObject]:
    return [
        {"value": value, "count": count}
        for value, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
        if count >= minimum_count
    ]


def _dominant(counter: Counter[str], *, total: int) -> JsonObject:
    if not counter:
        return {"value": "none", "count": 0, "share": 0.0, "repeated": False}

    value, count = sorted(counter.items(), key=lambda item: (-item[1], item[0]))[0]
    return {
        "value": value,
        "count": count,
        "share": round(count / total, 4) if total else 0.0,
        "repeated": count >= 2,
    }


def _safe_fix_patterns(
    rows: list[JsonObject],
    *,
    minimum_repeat: int,
) -> list[JsonObject]:
    counter: Counter[tuple[str, str]] = Counter(
        (_failure_class(row), _action(row))
        for row in rows
        if _bool(_decision(row).get("auto_fix_allowed"))
    )
    return [
        {
            "failure_class": failure_class,
            "action": action,
            "count": count,
        }
        for (failure_class, action), count in sorted(
            counter.items(),
            key=lambda item: (-item[1], item[0][0], item[0][1]),
        )
        if count >= minimum_repeat
    ]


def _authority_boundary_evidence(rows: list[JsonObject]) -> JsonObject:
    authority_rows = [
        _as_dict(row.get("authority_boundary"))
        for row in rows
        if _as_dict(row.get("authority_boundary"))
    ]
    denied_keys = (
        "automation_allowed",
        "patch_application_allowed",
        "merge_authorized",
        "semantic_equivalence_proven",
        "automatic_security_fix_allowed",
        "automatic_dismissal_allowed",
    )
    denied = {key: False for key in denied_keys}
    if not authority_rows:
        return {
            "collection_status": "not_collected",
            "status": "not_collected",
            "source": "trajectory.authority_boundary",
            "record_count": 0,
            "review_first_count": 0,
            "auto_fix_allowed_count": 0,
            "reporting_only_count": 0,
            "sources": [],
            "decision_boundary": denied,
        }

    return {
        "collection_status": "collected",
        "status": "authority_boundary_evidence_observed",
        "source": "trajectory.authority_boundary",
        "record_count": len(authority_rows),
        "review_first_count": sum(1 for row in authority_rows if _bool(row.get("review_first"))),
        "auto_fix_allowed_count": sum(
            1 for row in authority_rows if _bool(row.get("auto_fix_allowed"))
        ),
        "reporting_only_count": sum(
            1 for row in authority_rows if _bool(row.get("reporting_only"))
        ),
        "sources": sorted(
            {_string(row.get("source")) for row in authority_rows if _string(row.get("source"))}
        ),
        "decision_boundary": {
            key: any(_bool(row.get(key)) for row in authority_rows) for key in denied_keys
        },
    }


def _safety_gate_evidence(rows: list[JsonObject]) -> JsonObject:
    safety_rows = [
        _as_dict(row.get("safety_gate")) for row in rows if _as_dict(row.get("safety_gate"))
    ]
    if not safety_rows:
        return {
            "collection_status": "not_collected",
            "status": "not_collected",
            "source": "trajectory.safety_gate",
            "record_count": 0,
            "review_first_count": 0,
            "safe_fix_allowed_count": 0,
            "reporting_only_count": 0,
            "report_paths": [],
            "decision_boundary": {
                "automation_allowed": False,
                "patch_application_allowed": False,
                "merge_authorized": False,
                "semantic_equivalence_proven": False,
            },
        }

    return {
        "collection_status": "collected",
        "status": "safety_gate_evidence_observed",
        "source": "trajectory.safety_gate",
        "record_count": len(safety_rows),
        "review_first_count": sum(1 for row in safety_rows if _bool(row.get("review_first"))),
        "safe_fix_allowed_count": sum(
            1 for row in safety_rows if _bool(row.get("safe_fix_allowed"))
        ),
        "reporting_only_count": sum(1 for row in safety_rows if _bool(row.get("reporting_only"))),
        "report_paths": sorted(
            {
                _string(row.get("report_path"))
                for row in safety_rows
                if _string(row.get("report_path"))
            }
        ),
        "decision_boundary": {
            "automation_allowed": any(_bool(row.get("automation_allowed")) for row in safety_rows),
            "patch_application_allowed": any(
                _bool(row.get("patch_application_allowed")) for row in safety_rows
            ),
            "merge_authorized": any(_bool(row.get("merge_authorized")) for row in safety_rows),
            "semantic_equivalence_proven": any(
                _bool(row.get("semantic_equivalence_proven")) for row in safety_rows
            ),
        },
    }


def _failure_vector_contract_evidence(rows: list[JsonObject]) -> JsonObject:
    contract_rows = [
        _as_dict(row.get("failure_vector_contract"))
        for row in rows
        if _as_dict(row.get("failure_vector_contract"))
    ]
    denied_keys = (
        "automation_allowed",
        "patch_application_allowed",
        "security_dismissal_allowed",
        "merge_authorized",
        "semantic_equivalence_claim",
    )
    denied = {key: False for key in denied_keys}
    if not contract_rows:
        return {
            "collection_status": "not_collected",
            "status": "not_collected",
            "source": "trajectory.failure_vector_contract",
            "record_count": 0,
            "security_relevance_count": 0,
            "authority_boundary_preserved_count": 0,
            "failure_kinds": [],
            "affected_surfaces": [],
            "decision_boundary": denied,
        }

    return {
        "collection_status": "collected",
        "status": "failure_vector_contract_evidence_observed",
        "source": "trajectory.failure_vector_contract",
        "record_count": len(contract_rows),
        "security_relevance_count": sum(
            1 for row in contract_rows if _bool(row.get("security_relevance"))
        ),
        "authority_boundary_preserved_count": sum(
            1 for row in contract_rows if _bool(row.get("authority_boundary_preserved"))
        ),
        "failure_kinds": _counter_rows(
            Counter(_string(row.get("failure_kind")) for row in contract_rows)
        ),
        "affected_surfaces": _counter_rows(
            Counter(_string(row.get("affected_surface")) for row in contract_rows)
        ),
        "decision_boundary": {
            key: any(_bool(row.get(key)) for row in contract_rows) for key in denied_keys
        },
    }


def _operator_focus(
    *,
    record_count: int,
    recurring_review_surfaces: list[JsonObject],
    review_first_count: int,
    recurring_safe_fixes: list[JsonObject],
    auto_fix_allowed_count: int,
) -> JsonObject:
    if recurring_review_surfaces:
        surface = _string(recurring_review_surfaces[0].get("value"))
        return {
            "priority": "review_first_recurrence",
            "surface": surface,
            "reason": f"Repeated review-first decisions were recorded on {surface}.",
            "recommended_next_action": (
                "Inspect repeated review-first evidence before expanding automation."
            ),
        }

    if review_first_count:
        return {
            "priority": "review_first_observed",
            "surface": "mixed",
            "reason": "Review-first decisions exist but no repeated surface is proven yet.",
            "recommended_next_action": "Collect more trajectory history before automation changes.",
        }

    if recurring_safe_fixes:
        failure_class = _string(recurring_safe_fixes[0].get("failure_class"))
        return {
            "priority": "safe_fix_recurrence",
            "surface": "quality",
            "reason": f"Repeated safe-fix decisions were recorded for {failure_class}.",
            "recommended_next_action": (
                "Use this proven pattern as an input for the future PatchScorer prototype."
            ),
        }

    if auto_fix_allowed_count:
        return {
            "priority": "safe_fix_observed",
            "surface": "quality",
            "reason": "A safe-fix decision exists but repetition is not proven yet.",
            "recommended_next_action": "Collect more trajectory history before scoring patterns.",
        }

    if record_count:
        return {
            "priority": "observe_more_history",
            "surface": "unknown",
            "reason": "Trajectory records exist without a repeated operator pattern.",
            "recommended_next_action": "Continue collecting deterministic trajectory records.",
        }

    return {
        "priority": "no_history",
        "surface": "none",
        "reason": "No trajectory records were supplied.",
        "recommended_next_action": "Generate trajectory records before evaluating patterns.",
    }


def build_pattern_insights(
    records: list[Mapping[str, Any]],
    *,
    minimum_repeat: int = 2,
    recent_limit: int = 5,
) -> JsonObject:
    if minimum_repeat < 1:
        msg = "minimum_repeat must be at least 1"
        raise ValueError(msg)

    rows = [_as_dict(record) for record in records if _as_dict(record)]
    review_first_rows = [row for row in rows if _bool(_decision(row).get("review_first"))]
    auto_fix_rows = [row for row in rows if _bool(_decision(row).get("auto_fix_allowed"))]

    surfaces = Counter(_risk_surface(row) for row in rows)
    failure_classes = Counter(_failure_class(row) for row in rows)
    actions = Counter(_action(row) for row in rows)
    review_surfaces = Counter(_risk_surface(row) for row in review_first_rows)

    recurring_review_surfaces = _counter_rows(
        review_surfaces,
        minimum_count=minimum_repeat,
    )
    recurring_safe_fixes = _safe_fix_patterns(
        auto_fix_rows,
        minimum_repeat=minimum_repeat,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "record_count": len(rows),
        "minimum_repeat": minimum_repeat,
        "history_summary": build_history_summary(rows, recent_limit=recent_limit),
        "dominant_risk_surface": _dominant(surfaces, total=len(rows)),
        "dominant_failure_class": _dominant(failure_classes, total=len(rows)),
        "dominant_action": _dominant(actions, total=len(rows)),
        "recurring_review_first_surfaces": recurring_review_surfaces,
        "recurring_safe_fix_patterns": recurring_safe_fixes,
        "safety_gate_evidence": _safety_gate_evidence(rows),
        "authority_boundary_evidence": _authority_boundary_evidence(rows),
        "failure_vector_contract_evidence": _failure_vector_contract_evidence(rows),
        "operator_focus": _operator_focus(
            record_count=len(rows),
            recurring_review_surfaces=recurring_review_surfaces,
            review_first_count=len(review_first_rows),
            recurring_safe_fixes=recurring_safe_fixes,
            auto_fix_allowed_count=len(auto_fix_rows),
        ),
    }


def render_pattern_markdown(insights: Mapping[str, Any]) -> str:
    history = _as_dict(insights.get("history_summary"))
    focus = _as_dict(insights.get("operator_focus"))
    safety_gate = _as_dict(insights.get("safety_gate_evidence"))
    boundary = _as_dict(safety_gate.get("decision_boundary"))
    authority = _as_dict(insights.get("authority_boundary_evidence"))
    authority_boundary = _as_dict(authority.get("decision_boundary"))
    vector_contract = _as_dict(insights.get("failure_vector_contract_evidence"))
    vector_boundary = _as_dict(vector_contract.get("decision_boundary"))

    lines = [
        "# Trajectory pattern insights",
        "",
        f"- Schema: `{_string(insights.get('schema_version'))}`",
        f"- Records analyzed: `{int(insights.get('record_count', 0) or 0)}`",
        f"- Minimum repeat threshold: `{int(insights.get('minimum_repeat', 0) or 0)}`",
        f"- Review-first decisions: `{int(history.get('review_first_count', 0) or 0)}`",
        f"- Auto-fix allowed decisions: `{int(history.get('auto_fix_allowed_count', 0) or 0)}`",
        "",
        "## Dominant patterns",
        "",
    ]

    for title, key in (
        ("Risk surface", "dominant_risk_surface"),
        ("Failure class", "dominant_failure_class"),
        ("Action", "dominant_action"),
    ):
        item = _as_dict(insights.get(key))
        lines.append(
            f"- {title}: `{_string(item.get('value'))}` "
            f"(count=`{int(item.get('count', 0) or 0)}`, "
            f"share=`{float(item.get('share', 0.0) or 0.0):.4f}`)"
        )

    lines.extend(["", "## Recurring review-first surfaces", ""])
    review_surfaces = insights.get("recurring_review_first_surfaces")
    if isinstance(review_surfaces, list) and review_surfaces:
        for item in review_surfaces:
            row = _as_dict(item)
            lines.append(f"- `{_string(row.get('value'))}`: `{int(row.get('count', 0) or 0)}`")
    else:
        lines.append("- none")

    lines.extend(["", "## Recurring safe-fix patterns", ""])
    safe_patterns = insights.get("recurring_safe_fix_patterns")
    if isinstance(safe_patterns, list) and safe_patterns:
        for item in safe_patterns:
            row = _as_dict(item)
            lines.append(
                f"- class=`{_string(row.get('failure_class'))}`, "
                f"action=`{_string(row.get('action'))}`, "
                f"count=`{int(row.get('count', 0) or 0)}`"
            )
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## SafetyGate evidence",
            "",
            f"- Collection status: `{_string(safety_gate.get('collection_status'))}`",
            f"- Status: `{_string(safety_gate.get('status'))}`",
            f"- Records: `{int(safety_gate.get('record_count', 0) or 0)}`",
            f"- Safe-fix allowed records: `{int(safety_gate.get('safe_fix_allowed_count', 0) or 0)}`",
            f"- Review-first records: `{int(safety_gate.get('review_first_count', 0) or 0)}`",
            f"- Reporting-only records: `{int(safety_gate.get('reporting_only_count', 0) or 0)}`",
            (
                "- Automation allowed by SafetyGate evidence: "
                f"`{str(_bool(boundary.get('automation_allowed'))).lower()}`"
            ),
            (
                "- Merge authorized by SafetyGate evidence: "
                f"`{str(_bool(boundary.get('merge_authorized'))).lower()}`"
            ),
        ]
    )

    lines.extend(
        [
            "",
            "## FailureVector contract evidence",
            "",
            f"- Collection status: `{_string(vector_contract.get('collection_status'))}`",
            f"- Status: `{_string(vector_contract.get('status'))}`",
            f"- Records: `{int(vector_contract.get('record_count', 0) or 0)}`",
            (
                "- Authority boundary preserved records: "
                f"`{int(vector_contract.get('authority_boundary_preserved_count', 0) or 0)}`"
            ),
            (
                "- Security-relevant records: "
                f"`{int(vector_contract.get('security_relevance_count', 0) or 0)}`"
            ),
            (
                "- Patch application allowed by FailureVector contract evidence: "
                f"`{str(_bool(vector_boundary.get('patch_application_allowed'))).lower()}`"
            ),
            (
                "- Security dismissal allowed by FailureVector contract evidence: "
                f"`{str(_bool(vector_boundary.get('security_dismissal_allowed'))).lower()}`"
            ),
            (
                "- Merge authorized by FailureVector contract evidence: "
                f"`{str(_bool(vector_boundary.get('merge_authorized'))).lower()}`"
            ),
            "",
            "## Trajectory authority boundary evidence",
            "",
            f"- Collection status: `{_string(authority.get('collection_status'))}`",
            f"- Status: `{_string(authority.get('status'))}`",
            f"- Records: `{int(authority.get('record_count', 0) or 0)}`",
            f"- Review-first records: `{int(authority.get('review_first_count', 0) or 0)}`",
            f"- Auto-fix evidence records: `{int(authority.get('auto_fix_allowed_count', 0) or 0)}`",
            f"- Reporting-only records: `{int(authority.get('reporting_only_count', 0) or 0)}`",
            (
                "- Patch automation allowed by trajectory authority evidence: "
                f"`{str(_bool(authority_boundary.get('patch_application_allowed'))).lower()}`"
            ),
            (
                "- Security dismissal allowed by trajectory authority evidence: "
                f"`{str(_bool(authority_boundary.get('automatic_dismissal_allowed'))).lower()}`"
            ),
            (
                "- Merge authorized by trajectory authority evidence: "
                f"`{str(_bool(authority_boundary.get('merge_authorized'))).lower()}`"
            ),
            "",
            "## Operator focus",
            "",
            f"- Priority: `{_string(focus.get('priority'))}`",
            f"- Surface: `{_string(focus.get('surface'))}`",
            f"- Reason: {_string(focus.get('reason'))}",
            f"- Next action: {_string(focus.get('recommended_next_action'))}",
            "",
        ]
    )
    return "\n".join(lines)


def write_pattern_insights(
    *,
    records: list[Mapping[str, Any]],
    json_out: Path | None = None,
    markdown_out: Path | None = None,
    minimum_repeat: int = 2,
    recent_limit: int = 5,
) -> JsonObject:
    insights = build_pattern_insights(
        records,
        minimum_repeat=minimum_repeat,
        recent_limit=recent_limit,
    )

    if json_out is not None:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(
            json.dumps(insights, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    if markdown_out is not None:
        markdown_out.parent.mkdir(parents=True, exist_ok=True)
        markdown_out.write_text(render_pattern_markdown(insights), encoding="utf-8")

    return insights


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.trajectory_pattern_insights")
    parser.add_argument(
        "--trajectory-jsonl",
        type=Path,
        action="append",
        required=True,
        help="TrajectoryStore JSONL file. May be provided more than once.",
    )
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    parser.add_argument("--minimum-repeat", type=int, default=2)
    parser.add_argument("--recent-limit", type=int, default=5)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        records = load_trajectory_records(args.trajectory_jsonl)
        insights = write_pattern_insights(
            records=records,
            json_out=args.json_out,
            markdown_out=args.markdown_out,
            minimum_repeat=args.minimum_repeat,
            recent_limit=args.recent_limit,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(json.dumps({"insights": insights}, indent=2, sort_keys=True))
    else:
        print(render_pattern_markdown(insights))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
