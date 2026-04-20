from __future__ import annotations

from scripts import check_phase5_ecosystem_contract as contract


def test_phase5_reliability_degraded_when_extension_diagnostics_missing() -> None:
    payload = {
        "ecosystem_checks": [
            {
                "check_id": "integration.playbook",
                "status": "pass",
                "reason_code": "contract_satisfied",
                "evidence_refs": ["docs/integrations-and-extension-boundary.md"],
                "owner_hint": "ecosystem-ops",
                "ecosystem_domain": "integration_playbook",
            }
        ],
        "plugin_reliability_contract": {
            "supported_extension_modes": ["entry_points"],
            "failure_isolation_guards": [],
            "compatibility_guards": [],
        },
    }

    reliability = contract._build_reliability(payload)
    assert reliability["plugin_reliability_status"] == "degraded"
    assert "extension_diagnostics_missing" in reliability["blockers"]
    assert reliability["recommended_actions"]


def test_phase5_reliability_output_requires_sorted_lists_and_valid_statuses() -> None:
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
            "missing_artifacts": [],
            "support_surface": ["x"],
            "packaging_status": "complete",
            "generated_at": "2026-04-20T00:00:00Z",
        },
        reliability_payload={
            "schema_version": contract.RELIABILITY_SCHEMA_VERSION,
            "plugin_reliability_status": "bad-status",
            "integration_playbook_status": "ready",
            "certification_readiness": "ready",
            "blockers": ["z", "a"],
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

    assert "invalid plugin_reliability_status" in failures
    assert "reliability blockers must be sorted list" in failures
