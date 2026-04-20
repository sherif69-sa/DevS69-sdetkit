from __future__ import annotations

from scripts import check_phase5_ecosystem_contract as contract


def test_phase5_drift_alerts_deterministic_ordering() -> None:
    drift = contract._build_drift_alerts(
        ecosystem_payload={
            "ecosystem_checks": [
                {"check_id": "z", "status": "fail"},
                {"check_id": "a", "status": "fail"},
            ]
        },
        packaging={"missing_artifacts": ["z", "a"]},
        reliability={"blockers": ["z", "a"]},
    )

    assert drift["alerts"] == sorted(drift["alerts"])
    assert drift["drift_status"] == "drift"


def test_phase5_drift_alerts_missing_required_keys_fail() -> None:
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
            "plugin_reliability_status": "stable",
            "integration_playbook_status": "ready",
            "certification_readiness": "ready",
            "blockers": [],
            "recommended_actions": [],
            "generated_at": "2026-04-20T00:00:00Z",
        },
        drift_payload={
            "schema_version": contract.DRIFT_ALERTS_SCHEMA_VERSION,
            "alerts": ["z", "a"],
            "drift_score": 1,
            "generated_at": "2026-04-20T00:00:00Z",
        },
    )

    assert "drift payload missing key: drift_status" in failures
    assert "drift payload missing key: drift_threshold" in failures
    assert "drift alerts must be sorted list" in failures


def test_phase5_drift_alerts_schema_version_and_numeric_types_fail() -> None:
    failures = contract._validate_output_contracts(
        ecosystem_payload={
            "schema_version": "bad",
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
            "schema_version": "bad",
            "required_artifacts": ["a"],
            "discovered_artifacts": ["a"],
            "missing_artifacts": [],
            "support_surface": ["x"],
            "packaging_status": "complete",
            "generated_at": "2026-04-20T00:00:00Z",
        },
        reliability_payload={
            "schema_version": "bad",
            "plugin_reliability_status": "stable",
            "integration_playbook_status": "ready",
            "certification_readiness": "ready",
            "blockers": [],
            "recommended_actions": [],
            "generated_at": "2026-04-20T00:00:00Z",
        },
        drift_payload={
            "schema_version": "bad",
            "drift_status": "healthy",
            "alerts": [],
            "drift_score": "1",
            "drift_threshold": "2",
            "generated_at": "2026-04-20T00:00:00Z",
        },
    )

    assert f"ecosystem payload schema_version must be {contract.SCHEMA_VERSION}" in failures
    assert f"partner packaging schema_version must be {contract.PARTNER_PACKAGING_SCHEMA_VERSION}" in failures
    assert f"reliability schema_version must be {contract.RELIABILITY_SCHEMA_VERSION}" in failures
    assert f"drift schema_version must be {contract.DRIFT_ALERTS_SCHEMA_VERSION}" in failures
    assert "drift_score must be int" in failures
    assert "drift_threshold must be int" in failures
