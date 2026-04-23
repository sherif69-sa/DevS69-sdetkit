from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_owner_escalation_payload.py"
_SPEC = importlib.util.spec_from_file_location(
    "build_owner_escalation_payload_script", _SCRIPT_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
owner_escalation = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(owner_escalation)


def test_build_payload_handles_empty_owner_routing() -> None:
    payload = owner_escalation.build_payload({"scenario": "fast", "owner_routing": []})
    assert payload["schema_version"] == "sdetkit.owner-escalation-payload.v1"
    assert payload["summary"] == {"total_routes": 0, "critical": 0, "high": 0, "medium": 0}
    assert payload["routes"] == []
    assert payload["recommendations"] == []


def test_build_payload_summarizes_mixed_severities() -> None:
    payload = owner_escalation.build_payload(
        {
            "scenario": "strict",
            "owner_routing": [
                {
                    "check": "c-medium",
                    "owner": "team-b",
                    "severity": "medium",
                    "sla": "7d",
                    "details": "m",
                },
                {
                    "check": "c-critical",
                    "owner": "team-a",
                    "severity": "critical",
                    "sla": "24h",
                    "details": "x",
                },
                {
                    "check": "c-high",
                    "owner": "team-a",
                    "severity": "high",
                    "sla": "72h",
                    "details": "y",
                },
            ],
        }
    )

    assert payload["summary"] == {"total_routes": 3, "critical": 1, "high": 1, "medium": 1}
    assert [row["check"] for row in payload["routes"]] == ["c-critical", "c-high", "c-medium"]
    assert all(row["source_scenario"] == "strict" for row in payload["routes"])


def test_recommendations_group_by_owner_with_prioritized_actions() -> None:
    payload = owner_escalation.build_payload(
        {
            "scenario": "balanced",
            "owner_routing": [
                {
                    "check": "check-2",
                    "owner": "owner-x",
                    "severity": "high",
                    "sla": "72h",
                    "details": "high route",
                },
                {
                    "check": "check-1",
                    "owner": "owner-x",
                    "severity": "critical",
                    "sla": "24h",
                    "details": "critical route",
                },
                {
                    "check": "check-3",
                    "owner": "owner-y",
                    "severity": "medium",
                    "sla": "7d",
                    "details": "medium route",
                },
            ],
        }
    )

    assert [row["owner"] for row in payload["recommendations"]] == ["owner-x", "owner-y"]
    owner_x = payload["recommendations"][0]
    assert [row["priority"] for row in owner_x["prioritized_actions"]] == ["P0", "P1"]
    assert owner_x["prioritized_actions"][0]["checks"] == ["check-1"]
    assert owner_x["suggestions"] == []
    assert owner_x["follow_up_plan"] == []


def test_build_payload_is_deterministic_for_route_and_recommendation_ordering() -> None:
    postcheck = {
        "scenario": "balanced",
        "owner_routing": [
            {
                "check": "z-check",
                "owner": "owner-b",
                "severity": "high",
                "sla": "72h",
                "details": "z",
            },
            {
                "check": "a-check",
                "owner": "owner-a",
                "severity": "critical",
                "sla": "24h",
                "details": "a",
            },
            {
                "check": "m-check",
                "owner": "owner-a",
                "severity": "high",
                "sla": "72h",
                "details": "m",
            },
        ],
    }

    first = owner_escalation.build_payload(postcheck)
    second = owner_escalation.build_payload(postcheck)

    assert [row["check"] for row in first["routes"]] == ["a-check", "m-check", "z-check"]
    assert [row["owner"] for row in first["recommendations"]] == ["owner-a", "owner-b"]

    # Exclude runtime timestamp from strict comparison.
    first_fixed = dict(first)
    second_fixed = dict(second)
    first_fixed["generated_at_utc"] = "fixed"
    second_fixed["generated_at_utc"] = "fixed"
    assert json.dumps(first_fixed, sort_keys=True) == json.dumps(second_fixed, sort_keys=True)


def test_build_payload_prefers_route_level_source_scenario_when_present() -> None:
    payload = owner_escalation.build_payload(
        {
            "scenario": "balanced",
            "owner_routing": [
                {
                    "check": "check-1",
                    "owner": "owner-a",
                    "severity": "high",
                    "sla": "72h",
                    "details": "route detail",
                    "source_scenario": "strict",
                }
            ],
        }
    )
    assert payload["routes"][0]["source_scenario"] == "strict"


def test_build_payload_keeps_suggestion_and_follow_up_entries() -> None:
    payload = owner_escalation.build_payload(
        {
            "scenario": "balanced",
            "owner_routing": [
                {
                    "check": "check-1",
                    "owner": "owner-a",
                    "severity": "high",
                    "sla": "72h",
                    "details": "route detail",
                }
            ],
            "follow_up_enhancements": [
                {
                    "id": "b-item",
                    "priority": "high",
                    "feature": "Increase flake classification coverage.",
                    "next_command": "make adaptive-ops-bundle",
                },
                {
                    "id": "a-item",
                    "priority": "critical",
                    "feature": "Backfill owner mappings for strict checks.",
                    "next_command": "python scripts/adaptive_postcheck.py . --scenario strict",
                },
            ],
            "next_follow_up_plan": [
                {
                    "id": "weekly",
                    "priority": "medium",
                    "task": "Run weekly adaptive review.",
                    "command": "make adaptive-ops-bundle",
                }
            ],
        }
    )
    owner_a_recommendation = payload["recommendations"][0]
    assert [row["id"] for row in owner_a_recommendation["suggestions"]] == ["a-item", "b-item"]
    assert owner_a_recommendation["follow_up_plan"] == [
        {
            "id": "weekly",
            "priority": "medium",
            "task": "Run weekly adaptive review.",
            "command": "make adaptive-ops-bundle",
        }
    ]


def test_suggestion_priority_ordering_is_ranked_not_lexicographic() -> None:
    payload = owner_escalation.build_payload(
        {
            "scenario": "balanced",
            "owner_routing": [
                {
                    "check": "check-1",
                    "owner": "owner-a",
                    "severity": "high",
                    "sla": "72h",
                    "details": "route detail",
                }
            ],
            "follow_up_enhancements": [
                {
                    "id": "p2-item",
                    "priority": "P2",
                    "feature": "Later",
                    "next_command": "echo later",
                },
                {"id": "p0-item", "priority": "P0", "feature": "Now", "next_command": "echo now"},
            ],
        }
    )
    assert [row["id"] for row in payload["recommendations"][0]["suggestions"]] == [
        "p0-item",
        "p2-item",
    ]


def test_suggestions_and_followups_are_preserved_without_routes() -> None:
    payload = owner_escalation.build_payload(
        {
            "scenario": "balanced",
            "owner_routing": [],
            "follow_up_enhancements": [
                {
                    "id": "s1",
                    "priority": "high",
                    "feature": "Sync owners",
                    "next_command": "make adaptive-ops-bundle",
                }
            ],
            "next_follow_up_plan": [
                {
                    "id": "f1",
                    "priority": "P1",
                    "task": "Run strict postcheck",
                    "command": "make adaptive-postcheck",
                }
            ],
        }
    )
    assert payload["recommendations"] == [
        {
            "owner": "unassigned",
            "total_routes": 0,
            "prioritized_actions": [],
            "suggestions": [
                {
                    "id": "s1",
                    "priority": "high",
                    "suggestion": "Sync owners",
                    "follow_up_command": "make adaptive-ops-bundle",
                }
            ],
            "follow_up_plan": [
                {
                    "id": "f1",
                    "priority": "P1",
                    "task": "Run strict postcheck",
                    "command": "make adaptive-postcheck",
                }
            ],
        }
    ]


def test_generated_timestamp_uses_utc_z_suffix() -> None:
    payload = owner_escalation.build_payload({"scenario": "fast", "owner_routing": []})
    assert payload["generated_at_utc"].endswith("Z")
