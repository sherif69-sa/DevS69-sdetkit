from __future__ import annotations

from scripts import phase3_quality_engine as q


def _summary() -> dict[str, object]:
    return {
        "schema_version": "sdetkit.phase1_baseline.v1",
        "checks": [
            {"id": "pytest", "ok": False, "rc": 1},
            {"id": "doctor", "ok": False, "rc": 1},
            {"id": "ruff", "ok": True, "rc": 0},
        ],
    }


def test_next_pass_recommendations_deterministic_and_reasoned() -> None:
    adaptive = q.build_adaptive_planning(_summary())
    remediation = q.build_remediation_v2(_summary(), adaptive)

    p1 = q.build_next_pass_handoff(remediation, adaptive)
    p2 = q.build_next_pass_handoff(remediation, adaptive)

    assert p1["stable_payload"] == p2["stable_payload"]
    assert p1["stable_payload"] == [
        {
            "recommendation_id": row["recommendation_id"],
            "priority_tier": row["priority_tier"],
            "priority": row["priority"],
            "reason_code": row["reason_code"],
            "command_hint": row["command_hint"],
        }
        for row in p1["recommendations"]
    ]
    assert all(row["reason_code"] for row in p1["recommendations"])


def test_next_pass_contract_fails_on_missing_reason_code() -> None:
    adaptive = q.build_adaptive_planning(_summary())
    remediation = q.build_remediation_v2(_summary(), adaptive)
    next_pass = q.build_next_pass_handoff(remediation, adaptive)
    next_pass["recommendations"][0]["reason_code"] = ""

    failures = q.validate_phase3_payloads(
        adaptive,
        remediation,
        {"schema_version": q.TREND_SCHEMA_VERSION, "compared_artifacts": {}, "status": "stable", "regressions": [], "improvements": [], "unchanged_signals": [], "recommended_immediate_actions": [], "generated_at": "2026-01-01T00:00:00Z"},
        next_pass,
    )

    assert any("reason_code missing" in failure for failure in failures)


def test_next_pass_contract_fails_on_nondeterministic_ordering() -> None:
    adaptive = q.build_adaptive_planning(_summary())
    remediation = q.build_remediation_v2(_summary(), adaptive)
    next_pass = q.build_next_pass_handoff(remediation, adaptive)
    next_pass["recommendations"] = list(reversed(next_pass["recommendations"]))

    failures = q.validate_phase3_payloads(
        adaptive,
        remediation,
        {
            "schema_version": q.TREND_SCHEMA_VERSION,
            "compared_artifacts": {"current": "a", "previous": "b"},
            "status": "stable",
            "regressions": [],
            "improvements": [],
            "unchanged_signals": [],
            "recommended_immediate_actions": [],
            "generated_at": "2026-01-01T00:00:00Z",
        },
        next_pass,
    )

    assert any("not deterministically sorted" in failure for failure in failures)
