from __future__ import annotations

from scripts import phase3_quality_engine as q


def _summary() -> dict[str, object]:
    return {
        "schema_version": "sdetkit.phase1_baseline.v1",
        "checks": [
            {"id": "doctor", "ok": False, "rc": 1},
            {"id": "enterprise_contracts", "ok": False, "rc": 1},
            {"id": "pytest", "ok": False, "rc": 1},
            {"id": "ruff", "ok": True, "rc": 0},
        ],
    }


def test_remediation_payload_v2_contract_fields() -> None:
    adaptive = q.build_adaptive_planning(_summary(), ["src/a.py", "README.md"])
    payload = q.build_remediation_v2(_summary(), adaptive)

    assert payload["schema_version"] == q.REMEDIATION_V2_SCHEMA_VERSION
    assert sorted(payload["actions"]) == ["monitor", "next", "now"]
    assert isinstance(payload["top_risks"], list)
    assert isinstance(payload["blocking_conditions"], list)

    first_now = payload["actions"]["now"][0]
    assert {
        "action_id",
        "summary",
        "owner_hint",
        "blast_radius",
        "rollback_guardrail",
        "acceptance_check",
        "priority",
        "reason_code",
    }.issubset(first_now)


def test_remediation_payload_deterministic_ordering() -> None:
    adaptive = q.build_adaptive_planning(_summary())
    payload1 = q.build_remediation_v2(_summary(), adaptive)
    payload2 = q.build_remediation_v2(_summary(), adaptive)

    assert payload1["actions"] == payload2["actions"]
    assert q.validate_sorted_actions(payload1) == []


def test_remediation_payload_missing_required_key_fails_contract() -> None:
    adaptive = q.build_adaptive_planning(_summary())
    remediation = q.build_remediation_v2(_summary(), adaptive)
    remediation["actions"]["now"][0].pop("owner_hint")
    trend = {
        "schema_version": q.TREND_SCHEMA_VERSION,
        "compared_artifacts": {"current": "a", "previous": "b"},
        "status": "stable",
        "regressions": [],
        "improvements": [],
        "unchanged_signals": [],
        "recommended_immediate_actions": [],
        "generated_at": "2026-01-01T00:00:00Z",
    }
    next_pass = q.build_next_pass_handoff(remediation, adaptive)

    failures = q.validate_phase3_payloads(adaptive, remediation, trend, next_pass)
    assert any("missing key: owner_hint" in failure for failure in failures)
