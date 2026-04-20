#!/usr/bin/env python3
"""Deterministic Phase 3 quality payload builders and validators."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ADAPTIVE_SCHEMA_VERSION = "sdetkit.phase3_adaptive_planning.v1"
REMEDIATION_V2_SCHEMA_VERSION = "sdetkit.phase3_remediation.v2"
NEXT_PASS_SCHEMA_VERSION = "sdetkit.phase3_next_pass.v1"
TREND_SCHEMA_VERSION = "sdetkit.phase3_trend_delta.v1"

REASON_CODES = (
    "critical_required_check_failed",
    "required_check_failed",
    "optional_check_failed",
    "check_recovered",
    "no_action_required",
)

PRIORITY_TIERS = ("now", "next", "monitor")
IMPACT_AREA_BY_CHECK = {
    "gate_fast": "release_gates",
    "gate_release": "release_gates",
    "doctor": "diagnostics",
    "enterprise_contracts": "enterprise_contracts",
    "primary_docs_map": "docs_surface",
    "ruff": "code_quality",
    "pytest": "test_reliability",
}
REQUIRED_CHECK_IDS = ("doctor", "enterprise_contracts", "primary_docs_map")

TREND_DELTA_IMPROVING_THRESHOLD = -1
TREND_DELTA_WORSENING_THRESHOLD = 1
TREND_STATUSES = ("bootstrap", "improving", "stable", "worsening")
CONFIDENCE_KEYS = (
    "base_confidence",
    "required_check_penalty",
    "optional_check_penalty",
    "signal_coverage_bonus",
    "final_confidence",
)
REMEDIATION_ACTION_KEYS = (
    "action_id",
    "summary",
    "owner_hint",
    "blast_radius",
    "rollback_guardrail",
    "acceptance_check",
    "priority",
    "reason_code",
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _checks(summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows = summary.get("checks", [])
    if not isinstance(rows, list):
        return []
    only_rows = [row for row in rows if isinstance(row, dict)]
    return sorted(only_rows, key=lambda row: str(row.get("id", "")))


def _reason_for_check(check_id: str, ok: bool) -> str:
    if ok:
        return "check_recovered"
    if check_id in REQUIRED_CHECK_IDS:
        return "critical_required_check_failed" if check_id == "doctor" else "required_check_failed"
    return "optional_check_failed"


def _priority_for_reason(reason_code: str) -> tuple[str, int]:
    if reason_code == "critical_required_check_failed":
        return "now", 10
    if reason_code == "required_check_failed":
        return "now", 20
    if reason_code == "optional_check_failed":
        return "next", 30
    if reason_code == "check_recovered":
        return "monitor", 80
    return "monitor", 90


def build_adaptive_planning(
    summary: dict[str, Any], changed_paths: list[str] | None = None
) -> dict[str, Any]:
    check_rows = _checks(summary)
    normalized_paths = sorted({p.strip() for p in (changed_paths or []) if p and p.strip()})
    impact_areas = sorted(
        {IMPACT_AREA_BY_CHECK.get(str(row.get("id", "")), "other") for row in check_rows}
    )

    selection_rationale: list[dict[str, Any]] = []
    reason_counts = {code: 0 for code in REASON_CODES}
    failed_count = 0
    required_failed_count = 0

    for row in check_rows:
        check_id = str(row.get("id", "")).strip()
        ok = bool(row.get("ok", False))
        reason = _reason_for_check(check_id, ok)
        tier, _ = _priority_for_reason(reason)
        evidence_signal = f"rc={int(row.get('rc', 0))};ok={str(ok).lower()}"
        selection_rationale.append(
            {
                "check_id": check_id,
                "reason_code": reason,
                "evidence_signal": evidence_signal,
                "priority_tier": tier,
            }
        )
        reason_counts[reason] += 1
        if not ok:
            failed_count += 1
            if check_id in REQUIRED_CHECK_IDS:
                required_failed_count += 1

    selection_rationale.sort(
        key=lambda row: (
            PRIORITY_TIERS.index(str(row["priority_tier"])),
            str(row["reason_code"]),
            str(row["check_id"]),
        )
    )

    confidence_breakdown = {
        "base_confidence": 50.0,
        "required_check_penalty": float(required_failed_count * -20),
        "optional_check_penalty": float((failed_count - required_failed_count) * -7),
        "signal_coverage_bonus": float(len(selection_rationale) * 1.5),
    }
    confidence_breakdown["final_confidence"] = max(
        0.0, min(100.0, sum(confidence_breakdown.values()))
    )

    return {
        "schema_version": ADAPTIVE_SCHEMA_VERSION,
        "summary_source": str(summary.get("_source", "")),
        "changed_paths": normalized_paths,
        "impact_areas": impact_areas,
        "selection_rationale": selection_rationale,
        "confidence_breakdown": confidence_breakdown,
        "reason_code_vocabulary": list(REASON_CODES),
        "generated_at": _now_utc(),
    }


def build_remediation_v2(summary: dict[str, Any], adaptive: dict[str, Any]) -> dict[str, Any]:
    check_rows = _checks(summary)
    by_id = {str(row.get("id", "")): row for row in check_rows}

    actions = {"now": [], "next": [], "monitor": []}
    for rationale in adaptive.get("selection_rationale", []):
        if not isinstance(rationale, dict):
            continue
        check_id = str(rationale.get("check_id", "")).strip()
        reason_code = str(rationale.get("reason_code", "")).strip()
        tier = str(rationale.get("priority_tier", "monitor")).strip()
        _, priority = _priority_for_reason(reason_code)
        row = by_id.get(check_id, {})
        ok = bool(row.get("ok", False))
        action = {
            "action_id": f"phase3.{check_id}.{reason_code}",
            "summary": (
                f"Re-run and remediate {check_id}"
                if not ok
                else f"Monitor {check_id} for regression"
            ),
            "owner_hint": "repo-ops" if check_id in REQUIRED_CHECK_IDS else "service-owner",
            "blast_radius": IMPACT_AREA_BY_CHECK.get(check_id, "other"),
            "rollback_guardrail": f"Do not merge if {check_id} fails in rerun baseline.",
            "acceptance_check": f"{check_id}=ok",
            "priority": priority,
            "reason_code": reason_code,
        }
        actions[tier if tier in actions else "monitor"].append(action)

    for lane in ("now", "next", "monitor"):
        actions[lane].sort(key=lambda row: (int(row["priority"]), str(row["action_id"])))

    now_risks = [a["blast_radius"] for a in actions["now"]]
    top_risks = sorted({risk for risk in now_risks})
    blocking_conditions = sorted({a["acceptance_check"] for a in actions["now"]})

    legacy_bundle = [
        {
            "check_id": action["action_id"].split(".")[1],
            "action": action["summary"],
            "owner_hint": action["owner_hint"],
            "reason_code": action["reason_code"],
        }
        for action in actions["now"]
    ]

    return {
        "schema_version": REMEDIATION_V2_SCHEMA_VERSION,
        "actions": actions,
        "top_risks": top_risks,
        "blocking_conditions": blocking_conditions,
        "legacy_remediation_bundle": legacy_bundle,
        "generated_at": _now_utc(),
    }


def build_next_pass_handoff(
    remediation_v2: dict[str, Any], adaptive: dict[str, Any]
) -> dict[str, Any]:
    recommendations: list[dict[str, Any]] = []
    for lane in ("now", "next", "monitor"):
        lane_actions = remediation_v2.get("actions", {}).get(lane, [])
        if not isinstance(lane_actions, list):
            continue
        for action in lane_actions:
            if not isinstance(action, dict):
                continue
            recommendations.append(
                {
                    "recommendation_id": str(action.get("action_id", "")),
                    "priority_tier": lane,
                    "priority": int(action.get("priority", 0)),
                    "reason_code": str(action.get("reason_code", "")),
                    "command_hint": f"make phase1-baseline # validate {action.get('acceptance_check', '')}",
                    # Stable fields above are consumed by equality-sensitive operators.
                    # Volatile fields below are diagnostics-only and excluded from stable_payload.
                    "volatile_diagnostics": {
                        "generated_from": str(adaptive.get("summary_source", "")),
                        "generated_at": _now_utc(),
                    },
                }
            )

    recommendations.sort(
        key=lambda row: (
            PRIORITY_TIERS.index(str(row["priority_tier"])),
            int(row["priority"]),
            str(row["recommendation_id"]),
        )
    )

    stable_payload = [
        {
            "recommendation_id": row["recommendation_id"],
            "priority_tier": row["priority_tier"],
            "priority": row["priority"],
            "reason_code": row["reason_code"],
            "command_hint": row["command_hint"],
        }
        for row in recommendations
    ]

    return {
        "schema_version": NEXT_PASS_SCHEMA_VERSION,
        "recommendations": recommendations,
        "stable_payload": stable_payload,
        "generated_at": _now_utc(),
    }


def build_trend_delta(
    current_summary: dict[str, Any], previous_summary: dict[str, Any] | None
) -> dict[str, Any]:
    current_checks = _checks(current_summary)
    current_failed = sorted(
        str(row.get("id", "")) for row in current_checks if not bool(row.get("ok", False))
    )

    if not previous_summary:
        return {
            "schema_version": TREND_SCHEMA_VERSION,
            "compared_artifacts": {
                "current": str(current_summary.get("_source", "")),
                "previous": "",
            },
            "status": "bootstrap",
            "regressions": [],
            "improvements": [],
            "unchanged_signals": current_failed,
            "recommended_immediate_actions": [
                "Run a second baseline to establish comparison history."
            ],
            "generated_at": _now_utc(),
        }

    previous_checks = _checks(previous_summary)
    previous_failed = sorted(
        str(row.get("id", "")) for row in previous_checks if not bool(row.get("ok", False))
    )

    regressions = sorted(set(current_failed) - set(previous_failed))
    improvements = sorted(set(previous_failed) - set(current_failed))
    unchanged = sorted(set(current_failed) & set(previous_failed))

    failed_delta = len(current_failed) - len(previous_failed)
    if regressions and failed_delta >= TREND_DELTA_WORSENING_THRESHOLD:
        status = "worsening"
    elif improvements and failed_delta <= TREND_DELTA_IMPROVING_THRESHOLD:
        status = "improving"
    else:
        status = "stable"

    recommendations = [f"Remediate regression: {check_id}" for check_id in regressions]
    if not recommendations and unchanged:
        recommendations = [f"Stabilize recurring failure: {unchanged[0]}"]

    return {
        "schema_version": TREND_SCHEMA_VERSION,
        "compared_artifacts": {
            "current": str(current_summary.get("_source", "")),
            "previous": str(previous_summary.get("_source", "")),
        },
        "status": status,
        "regressions": regressions,
        "improvements": improvements,
        "unchanged_signals": unchanged,
        "recommended_immediate_actions": sorted(recommendations),
        "generated_at": _now_utc(),
    }


def validate_sorted_actions(payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    actions = payload.get("actions", {})
    if not isinstance(actions, dict):
        return ["actions must be an object"]
    for lane in ("now", "next", "monitor"):
        rows = actions.get(lane, [])
        if not isinstance(rows, list):
            failures.append(f"actions.{lane} must be a list")
            continue
        sorted_rows = sorted(
            rows, key=lambda row: (int(row.get("priority", 0)), str(row.get("action_id", "")))
        )
        if rows != sorted_rows:
            failures.append(f"actions.{lane} is not deterministically sorted")
    return failures


def validate_phase3_payloads(
    adaptive: dict[str, Any],
    remediation_v2: dict[str, Any],
    trend: dict[str, Any],
    next_pass: dict[str, Any],
) -> list[str]:
    failures: list[str] = []

    if adaptive.get("schema_version") != ADAPTIVE_SCHEMA_VERSION:
        failures.append("adaptive schema_version mismatch")
    for key, expected_type in {
        "changed_paths": list,
        "impact_areas": list,
        "selection_rationale": list,
        "confidence_breakdown": dict,
    }.items():
        if not isinstance(adaptive.get(key), expected_type):
            failures.append(f"adaptive missing/invalid key: {key}")

    for row in adaptive.get("selection_rationale", []):
        if not isinstance(row, dict):
            failures.append("adaptive selection_rationale rows must be objects")
            continue
        for key in ("check_id", "reason_code", "evidence_signal", "priority_tier"):
            if key not in row:
                failures.append(f"adaptive selection_rationale missing {key}")
        reason = str(row.get("reason_code", ""))
        tier = str(row.get("priority_tier", ""))
        if reason not in REASON_CODES:
            failures.append(f"adaptive invalid reason_code: {reason}")
        if tier not in PRIORITY_TIERS:
            failures.append(f"adaptive invalid priority_tier: {tier}")
    expected_selection = sorted(
        [row for row in adaptive.get("selection_rationale", []) if isinstance(row, dict)],
        key=lambda row: (
            PRIORITY_TIERS.index(str(row.get("priority_tier", "monitor"))),
            str(row.get("reason_code", "")),
            str(row.get("check_id", "")),
        ),
    )
    if adaptive.get("selection_rationale", []) != expected_selection:
        failures.append("adaptive selection_rationale is not deterministically sorted")
    confidence_breakdown = adaptive.get("confidence_breakdown", {})
    if isinstance(confidence_breakdown, dict):
        if tuple(confidence_breakdown.keys()) != CONFIDENCE_KEYS:
            failures.append("adaptive confidence_breakdown keys are not deterministic")
        for key in CONFIDENCE_KEYS:
            if not isinstance(confidence_breakdown.get(key), (int, float)):
                failures.append(f"adaptive confidence_breakdown[{key}] must be numeric")

    if remediation_v2.get("schema_version") != REMEDIATION_V2_SCHEMA_VERSION:
        failures.append("remediation_v2 schema_version mismatch")
    for key in ("actions", "top_risks", "blocking_conditions"):
        if key not in remediation_v2:
            failures.append(f"remediation_v2 missing key: {key}")
    actions = remediation_v2.get("actions", {})
    if isinstance(actions, dict):
        for lane in PRIORITY_TIERS:
            rows = actions.get(lane, [])
            if not isinstance(rows, list):
                continue
            for action in rows:
                if not isinstance(action, dict):
                    failures.append(f"remediation_v2 actions.{lane} rows must be objects")
                    continue
                for key in REMEDIATION_ACTION_KEYS:
                    if key not in action:
                        failures.append(f"remediation_v2 actions.{lane} missing key: {key}")
                if str(action.get("reason_code", "")) not in REASON_CODES:
                    failures.append(
                        f"remediation_v2 actions.{lane} invalid reason_code: {action.get('reason_code', '')}"
                    )
                if not isinstance(action.get("priority"), int):
                    failures.append(f"remediation_v2 actions.{lane} priority must be int")
    failures.extend(validate_sorted_actions(remediation_v2))

    if trend.get("schema_version") != TREND_SCHEMA_VERSION:
        failures.append("trend schema_version mismatch")
    for key in (
        "compared_artifacts",
        "status",
        "regressions",
        "improvements",
        "unchanged_signals",
        "recommended_immediate_actions",
        "generated_at",
    ):
        if key not in trend:
            failures.append(f"trend missing key: {key}")
    compared_artifacts = trend.get("compared_artifacts", {})
    if not isinstance(compared_artifacts, dict):
        failures.append("trend compared_artifacts must be object")
    else:
        for key in ("current", "previous"):
            if key not in compared_artifacts:
                failures.append(f"trend compared_artifacts missing key: {key}")
    trend_status = str(trend.get("status", ""))
    if trend_status not in TREND_STATUSES:
        failures.append(f"trend invalid status: {trend_status}")

    if next_pass.get("schema_version") != NEXT_PASS_SCHEMA_VERSION:
        failures.append("next_pass schema_version mismatch")
    recommendations = next_pass.get("recommendations", [])
    if not isinstance(recommendations, list):
        failures.append("next_pass recommendations must be a list")
        recommendations = []
    for row in recommendations:
        if not isinstance(row, dict):
            failures.append("next_pass recommendation row must be object")
            continue
        for key in (
            "recommendation_id",
            "priority_tier",
            "priority",
            "reason_code",
            "command_hint",
        ):
            if key not in row:
                failures.append(f"next_pass recommendation missing {key}")
        if not str(row.get("reason_code", "")).strip():
            failures.append("next_pass recommendation reason_code missing")
    expected_recommendations = sorted(
        [row for row in recommendations if isinstance(row, dict)],
        key=lambda row: (
            PRIORITY_TIERS.index(str(row.get("priority_tier", "monitor"))),
            int(row.get("priority", 0)),
            str(row.get("recommendation_id", "")),
        ),
    )
    if recommendations != expected_recommendations:
        failures.append("next_pass recommendations are not deterministically sorted")

    stable_payload = next_pass.get("stable_payload", [])
    if not isinstance(stable_payload, list):
        failures.append("next_pass stable_payload must be a list")
    if isinstance(recommendations, list) and isinstance(stable_payload, list):
        mirror = [
            {
                "recommendation_id": str(r.get("recommendation_id", "")),
                "priority_tier": str(r.get("priority_tier", "")),
                "priority": int(r.get("priority", 0)),
                "reason_code": str(r.get("reason_code", "")),
                "command_hint": str(r.get("command_hint", "")),
            }
            for r in recommendations
            if isinstance(r, dict)
        ]
        if stable_payload != mirror:
            failures.append(
                "next_pass stable_payload does not match deterministic recommendation slice"
            )
    return failures
