#!/usr/bin/env python3
"""Build deterministic owner escalation payloads from adaptive postcheck artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = ROOT / "docs" / "artifacts"

_SEVERITY_PRIORITY = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "warn": 4,
}

_PRIORITY_ORDER = {
    "p0": 0,
    "critical": 0,
    "p1": 1,
    "high": 1,
    "p2": 2,
    "medium": 2,
    "p3": 3,
    "low": 3,
    "warn": 4,
}

_ACTION_TEMPLATES: dict[str, tuple[str, str]] = {
    "critical": ("P0", "Open an immediate escalation ticket and page the on-call owner."),
    "high": ("P1", "Create a high-priority ticket with remediation owner and ETA."),
    "medium": ("P2", "Add to planned remediation backlog and track in weekly ops review."),
    "low": ("P3", "Track as routine quality debt and monitor for regression."),
    "warn": ("P3", "Track as advisory action and reassess in the next postcheck cycle."),
}


def _extract_suggestions(postcheck: dict[str, Any]) -> list[dict[str, str]]:
    rows = postcheck.get("follow_up_enhancements", [])
    if not isinstance(rows, list):
        return []
    suggestions: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        suggestions.append(
            {
                "id": str(row.get("id", "unknown")),
                "priority": str(row.get("priority", "medium")),
                "suggestion": str(row.get("feature", "")),
                "follow_up_command": str(row.get("next_command", "")),
            }
        )
    return sorted(
        suggestions,
        key=lambda item: (
            _PRIORITY_ORDER.get(item["priority"].lower(), 99),
            item["id"],
            item["suggestion"],
            item["follow_up_command"],
        ),
    )


def _extract_follow_up_plan(postcheck: dict[str, Any]) -> list[dict[str, str]]:
    rows = postcheck.get("next_follow_up_plan", [])
    if not isinstance(rows, list):
        return []
    plan: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        plan.append(
            {
                "id": str(row.get("id", "unknown")),
                "priority": str(row.get("priority", "medium")),
                "task": str(row.get("task", "")),
                "command": str(row.get("command", "")),
            }
        )
    return sorted(
        plan,
        key=lambda item: (
            _PRIORITY_ORDER.get(item["priority"].lower(), 99),
            item["id"],
            item["task"],
            item["command"],
        ),
    )


def _latest_postcheck_path() -> Path:
    matches = sorted(ARTIFACTS_DIR.glob("adaptive-postcheck-*.json"))
    if not matches:
        raise SystemExit("missing adaptive postcheck artifact: docs/artifacts/adaptive-postcheck-*.json")
    return matches[-1]


def _normalize_severity(value: Any) -> str:
    candidate = str(value or "medium").strip().lower()
    return candidate if candidate in _SEVERITY_PRIORITY else "medium"


def _severity_sort_key(route: dict[str, str]) -> tuple[int, str, str, str, str]:
    severity = _normalize_severity(route.get("severity"))
    return (
        _SEVERITY_PRIORITY.get(severity, 99),
        str(route.get("owner", "")),
        str(route.get("check", "")),
        str(route.get("sla", "")),
        str(route.get("details", "")),
    )


def _build_routes(postcheck: dict[str, Any]) -> list[dict[str, str]]:
    scenario = str(postcheck.get("scenario", "unknown"))
    owner_routing = postcheck.get("owner_routing", [])
    if not isinstance(owner_routing, list):
        return []

    routes: list[dict[str, str]] = []
    for row in owner_routing:
        if not isinstance(row, dict):
            continue
        routes.append(
            {
                "check": str(row.get("check", "unknown")),
                "owner": str(row.get("owner", "platform-ops")),
                "severity": _normalize_severity(row.get("severity", "medium")),
                "sla": str(row.get("sla", "7d")),
                "details": str(row.get("details", "")),
                "source_scenario": str(row.get("source_scenario", scenario)),
            }
        )
    return sorted(routes, key=_severity_sort_key)


def _build_summary(routes: list[dict[str, str]]) -> dict[str, int]:
    return {
        "total_routes": len(routes),
        "critical": sum(1 for row in routes if row.get("severity") == "critical"),
        "high": sum(1 for row in routes if row.get("severity") == "high"),
        "medium": sum(1 for row in routes if row.get("severity") == "medium"),
    }


def _build_recommendations(
    routes: list[dict[str, str]],
    *,
    suggestions: list[dict[str, str]],
    follow_up_plan: list[dict[str, str]],
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, list[dict[str, str]]]] = {}
    for row in routes:
        owner = row["owner"]
        severity = _normalize_severity(row.get("severity"))
        owner_bucket = grouped.setdefault(owner, {})
        owner_bucket.setdefault(severity, []).append(row)

    recommendations: list[dict[str, Any]] = []
    for owner in sorted(grouped):
        severities = grouped[owner]
        prioritized_actions: list[dict[str, Any]] = []
        for severity in sorted(severities, key=lambda item: _SEVERITY_PRIORITY.get(item, 99)):
            rows = sorted(severities[severity], key=lambda row: (row["check"], row["sla"], row["details"]))
            priority, action = _ACTION_TEMPLATES.get(severity, _ACTION_TEMPLATES["medium"])
            prioritized_actions.append(
                {
                    "priority": priority,
                    "severity": severity,
                    "action": action,
                    "route_count": len(rows),
                    "checks": [row["check"] for row in rows],
                    "sla_targets": sorted({row["sla"] for row in rows}),
                }
            )
        recommendations.append(
            {
                "owner": owner,
                "total_routes": sum(len(rows) for rows in severities.values()),
                "prioritized_actions": prioritized_actions,
                "suggestions": [dict(item) for item in suggestions],
                "follow_up_plan": [dict(item) for item in follow_up_plan],
            }
        )

    if not recommendations and (suggestions or follow_up_plan):
        recommendations.append(
            {
                "owner": "unassigned",
                "total_routes": 0,
                "prioritized_actions": [],
                "suggestions": [dict(item) for item in suggestions],
                "follow_up_plan": [dict(item) for item in follow_up_plan],
            }
        )

    return recommendations


def build_payload(postcheck: dict[str, Any]) -> dict[str, Any]:
    routes = _build_routes(postcheck)
    suggestions = _extract_suggestions(postcheck)
    follow_up_plan = _extract_follow_up_plan(postcheck)
    return {
        "schema_version": "sdetkit.owner-escalation-payload.v1",
        "generated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "summary": _build_summary(routes),
        "routes": routes,
        "recommendations": _build_recommendations(
            routes, suggestions=suggestions, follow_up_plan=follow_up_plan
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--postcheck",
        default=None,
        help="Adaptive postcheck JSON input path (default: latest docs/artifacts/adaptive-postcheck-*.json)",
    )
    parser.add_argument(
        "--out",
        default="build/owner-escalation-payload.json",
        help="Output escalation payload path.",
    )
    args = parser.parse_args()

    postcheck_path = Path(args.postcheck) if args.postcheck else _latest_postcheck_path()
    postcheck = json.loads(postcheck_path.read_text(encoding="utf-8"))
    payload = build_payload(postcheck)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "postcheck": postcheck_path.as_posix(),
                "out": out_path.as_posix(),
                "total_routes": payload["summary"]["total_routes"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
