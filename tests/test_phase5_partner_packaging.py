from __future__ import annotations

from scripts import check_phase5_ecosystem_contract as contract


def test_phase5_partner_packaging_incomplete_when_missing_artifacts() -> None:
    payload = {
        "partner_packaging_contract": {
            "required_artifacts": ["zzz.txt", "aaa.txt"],
            "support_surface": ["b", "a"],
            "auditability_status": "pass",
        }
    }

    packaging = contract._build_partner_packaging(payload)
    assert packaging["required_artifacts"] == ["aaa.txt", "zzz.txt"]
    assert packaging["missing_artifacts"] == ["aaa.txt", "zzz.txt"]
    assert packaging["support_surface"] == ["a", "b"]
    assert packaging["packaging_status"] == "incomplete"


def test_phase5_partner_packaging_missing_required_keys_fails() -> None:
    failures = contract._validate_output_contracts(
        ecosystem_payload={
            "schema_version": contract.SCHEMA_VERSION,
            "ecosystem_checks": [],
            "extension_policy": [],
            "plugin_reliability_contract": {
                "supported_extension_modes": ["entry_points"],
                "failure_isolation_guards": ["guard"],
                "compatibility_guards": ["guard"],
            },
            "partner_packaging_contract": {
                "required_artifacts": ["pyproject.toml"],
                "support_surface": ["make phase5-ecosystem-contract"],
                "auditability_status": "pass",
            },
            "generated_at": "2026-04-20T00:00:00Z",
        },
        packaging_payload={
            "schema_version": contract.PARTNER_PACKAGING_SCHEMA_VERSION,
            "required_artifacts": ["a"],
            "discovered_artifacts": ["a"],
            "packaging_status": "complete",
            "generated_at": "2026-04-20T00:00:00Z",
        },
        reliability_payload={
            "schema_version": contract.RELIABILITY_SCHEMA_VERSION,
            "plugin_reliability_status": "stable",
            "integration_playbook_status": "ready",
            "certification_readiness": "ready",
            "blockers": [],
            "recommended_actions": [],
            "generated_at": "2026-04-20T00:00:00Z",
        },
        drift_payload={
            "schema_version": contract.DRIFT_ALERTS_SCHEMA_VERSION,
            "drift_status": "healthy",
            "alerts": [],
            "drift_score": 0,
            "drift_threshold": 2,
            "generated_at": "2026-04-20T00:00:00Z",
        },
    )

    assert "partner packaging payload missing key: missing_artifacts" in failures
    assert "partner packaging payload missing key: support_surface" in failures
