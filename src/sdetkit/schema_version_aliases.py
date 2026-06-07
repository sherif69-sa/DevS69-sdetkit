"""Schema-version compatibility aliases for professional naming migration."""

from __future__ import annotations

SCHEMA_VERSION_ALIASES: dict[str, str] = {
    "sdetkit.phase1_baseline.v1": "sdetkit.baseline_baseline.v1",
    "sdetkit.phase2-hotspot-baseline.v1": "sdetkit.release-readiness-hotspot-baseline.v1",
    "sdetkit.phase2-hotspot-delta.v1": "sdetkit.release-readiness-hotspot-delta.v1",
    "sdetkit.phase2.doctor-behavior.v1": "sdetkit.release_readiness.doctor-behavior.v1",
    "sdetkit.phase2.repo-behavior.v1": "sdetkit.release_readiness.repo-behavior.v1",
    "sdetkit.phase3-dependency-radar.v1": "sdetkit.platform-readiness-dependency-radar.v1",
    "sdetkit.phase3_adaptive_planning.v1": "sdetkit.platform_readiness_adaptive_planning.v1",
    "sdetkit.phase3_baseline_history.v1": "sdetkit.platform_readiness_baseline_history.v1",
    "sdetkit.phase3_next_pass.v1": "sdetkit.platform_readiness_next_pass.v1",
    "sdetkit.phase3_quality_contract.v1": "sdetkit.platform_readiness_quality_contract.v1",
    "sdetkit.phase3_remediation.v2": "sdetkit.platform_readiness_remediation.v2",
    "sdetkit.phase3_trend_delta.v1": "sdetkit.platform_readiness_trend_delta.v1",
    "sdetkit.phase4_compliance_overlay.v1": "sdetkit.operational_readiness_compliance_overlay.v1",
    "sdetkit.phase4_compliance_overlay_pack.v1": "sdetkit.operational_readiness_compliance_overlay_pack.v1",
    "sdetkit.phase4_governance_adherence.v1": "sdetkit.operational_readiness_governance_adherence.v1",
    "sdetkit.phase4_governance_contract.v1": "sdetkit.operational_readiness_governance_contract.v1",
    "sdetkit.phase4_governance_contract.v2": "sdetkit.operational_readiness_governance_contract.v2",
    "sdetkit.phase4_governance_drift_alerts.v1": "sdetkit.operational_readiness_governance_drift_alerts.v1",
    "sdetkit.phase4_policy_as_code_template.v1": "sdetkit.operational_readiness_policy_as_code_template.v1",
    "sdetkit.phase4_release_evidence.v1": "sdetkit.operational_readiness_release_evidence.v1",
    "sdetkit.phase5_ecosystem_contract.v1": "sdetkit.adoption_readiness_ecosystem_contract.v1",
    "sdetkit.phase5_ecosystem_contract.v2": "sdetkit.adoption_readiness_ecosystem_contract.v2",
    "sdetkit.phase5_ecosystem_drift_alerts.v1": "sdetkit.adoption_readiness_ecosystem_drift_alerts.v1",
    "sdetkit.phase5_ecosystem_reliability.v1": "sdetkit.adoption_readiness_ecosystem_reliability.v1",
    "sdetkit.phase5_partner_packaging.v1": "sdetkit.adoption_readiness_partner_packaging.v1",
    "sdetkit.phase6_commercial_scorecard.v1": "sdetkit.scale_readiness_commercial_scorecard.v1",
    "sdetkit.phase6_kpi_snapshot.v1": "sdetkit.scale_readiness_kpi_snapshot.v1",
    "sdetkit.phase6_metrics_contract.v1": "sdetkit.scale_readiness_metrics_contract.v1",
    "sdetkit.phase6_metrics_contract.v2": "sdetkit.scale_readiness_metrics_contract.v2",
    "sdetkit.phase6_metrics_drift_alerts.v1": "sdetkit.scale_readiness_metrics_drift_alerts.v1",
}

PROFESSIONAL_SCHEMA_VERSION_ALIASES: dict[str, str] = {
    "sdetkit.baseline_baseline.v1": "sdetkit.phase1_baseline.v1",
    "sdetkit.release-readiness-hotspot-baseline.v1": "sdetkit.phase2-hotspot-baseline.v1",
    "sdetkit.release-readiness-hotspot-delta.v1": "sdetkit.phase2-hotspot-delta.v1",
    "sdetkit.release_readiness.doctor-behavior.v1": "sdetkit.phase2.doctor-behavior.v1",
    "sdetkit.release_readiness.repo-behavior.v1": "sdetkit.phase2.repo-behavior.v1",
    "sdetkit.platform-readiness-dependency-radar.v1": "sdetkit.phase3-dependency-radar.v1",
    "sdetkit.platform_readiness_adaptive_planning.v1": "sdetkit.phase3_adaptive_planning.v1",
    "sdetkit.platform_readiness_baseline_history.v1": "sdetkit.phase3_baseline_history.v1",
    "sdetkit.platform_readiness_next_pass.v1": "sdetkit.phase3_next_pass.v1",
    "sdetkit.platform_readiness_quality_contract.v1": "sdetkit.phase3_quality_contract.v1",
    "sdetkit.platform_readiness_remediation.v2": "sdetkit.phase3_remediation.v2",
    "sdetkit.platform_readiness_trend_delta.v1": "sdetkit.phase3_trend_delta.v1",
    "sdetkit.operational_readiness_compliance_overlay.v1": "sdetkit.phase4_compliance_overlay.v1",
    "sdetkit.operational_readiness_compliance_overlay_pack.v1": "sdetkit.phase4_compliance_overlay_pack.v1",
    "sdetkit.operational_readiness_governance_adherence.v1": "sdetkit.phase4_governance_adherence.v1",
    "sdetkit.operational_readiness_governance_contract.v1": "sdetkit.phase4_governance_contract.v1",
    "sdetkit.operational_readiness_governance_contract.v2": "sdetkit.phase4_governance_contract.v2",
    "sdetkit.operational_readiness_governance_drift_alerts.v1": "sdetkit.phase4_governance_drift_alerts.v1",
    "sdetkit.operational_readiness_policy_as_code_template.v1": "sdetkit.phase4_policy_as_code_template.v1",
    "sdetkit.operational_readiness_release_evidence.v1": "sdetkit.phase4_release_evidence.v1",
    "sdetkit.adoption_readiness_ecosystem_contract.v1": "sdetkit.phase5_ecosystem_contract.v1",
    "sdetkit.adoption_readiness_ecosystem_contract.v2": "sdetkit.phase5_ecosystem_contract.v2",
    "sdetkit.adoption_readiness_ecosystem_drift_alerts.v1": "sdetkit.phase5_ecosystem_drift_alerts.v1",
    "sdetkit.adoption_readiness_ecosystem_reliability.v1": "sdetkit.phase5_ecosystem_reliability.v1",
    "sdetkit.adoption_readiness_partner_packaging.v1": "sdetkit.phase5_partner_packaging.v1",
    "sdetkit.scale_readiness_commercial_scorecard.v1": "sdetkit.phase6_commercial_scorecard.v1",
    "sdetkit.scale_readiness_kpi_snapshot.v1": "sdetkit.phase6_kpi_snapshot.v1",
    "sdetkit.scale_readiness_metrics_contract.v1": "sdetkit.phase6_metrics_contract.v1",
    "sdetkit.scale_readiness_metrics_contract.v2": "sdetkit.phase6_metrics_contract.v2",
    "sdetkit.scale_readiness_metrics_drift_alerts.v1": "sdetkit.phase6_metrics_drift_alerts.v1",
}


def professional_schema_version(schema_version: str) -> str:
    """Return the professional alias for a legacy schema version when known."""
    return SCHEMA_VERSION_ALIASES.get(schema_version, schema_version)


def legacy_schema_version(schema_version: str) -> str:
    """Return the legacy canonical schema version for a professional alias when known."""
    return PROFESSIONAL_SCHEMA_VERSION_ALIASES.get(schema_version, schema_version)


def accepted_schema_versions(schema_version: str) -> tuple[str, ...]:
    """Return all accepted schema-version spellings for a schema contract."""
    professional = professional_schema_version(schema_version)
    legacy = legacy_schema_version(schema_version)
    versions = []
    for value in (legacy, professional, schema_version):
        if value not in versions:
            versions.append(value)
    return tuple(versions)


def schema_versions_compatible(left: str, right: str) -> bool:
    """Return whether two schema-version spellings refer to the same contract."""
    return legacy_schema_version(left) == legacy_schema_version(right)
