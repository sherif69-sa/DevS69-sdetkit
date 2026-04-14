from __future__ import annotations

import os

LEGACY_NAMESPACE_COMMANDS: tuple[str, ...] = (
    "weekly-review-lane",
    "phase1-hardening",
    "phase1-wrap",
    "phase2-kickoff",
    "release-cadence",
    "demo-asset",
    "demo-asset2",
    "kpi-instrumentation",
    "experiment-lane",
    "distribution-batch",
    "playbook-post",
    "scale-lane",
    "expansion-automation",
    "optimization-closeout-foundation",
)


LEGACY_COMMAND_MODULES: dict[str, str] = {
    "weekly-review-lane": "sdetkit.weekly_review_28",
    "phase1-hardening": "sdetkit.phase1_hardening_29",
    "phase1-wrap": "sdetkit.phase1_wrap_30",
    "phase2-kickoff": "sdetkit.phase2_kickoff_31",
    "release-cadence": "sdetkit.release_cadence_32",
    "demo-asset": "sdetkit.demo_asset_33",
    "demo-asset2": "sdetkit.demo_asset2_34",
    "kpi-instrumentation": "sdetkit.kpi_instrumentation_35",
    "distribution-closeout": "sdetkit.distribution_closeout_36",
    "experiment-lane": "sdetkit.experiment_lane_37",
    "distribution-batch": "sdetkit.distribution_batch_38",
    "playbook-post": "sdetkit.playbook_post_39",
    "scale-lane": "sdetkit.scale_lane_40",
    "expansion-automation": "sdetkit.expansion_automation_41",
    "optimization-closeout-foundation": "sdetkit.optimization_closeout_42",
    "acceleration-closeout": "sdetkit.acceleration_closeout_43",
    "scale-closeout": "sdetkit.scale_closeout_44",
    "expansion-closeout": "sdetkit.expansion_closeout_45",
    "optimization-closeout": "sdetkit.optimization_closeout_46",
    "reliability-closeout": "sdetkit.reliability_closeout_47",
    "objection-closeout": "sdetkit.objection_closeout_48",
    "weekly-review-closeout": "sdetkit.weekly_review_closeout_49",
    "execution-prioritization-closeout": "sdetkit.execution_prioritization_closeout_50",
    "case-snippet-closeout": "sdetkit.case_snippet_closeout_51",
    "narrative-closeout": "sdetkit.narrative_closeout_52",
    "docs-loop-closeout": "sdetkit.docs_loop_closeout_53",
    "contributor-activation-closeout": "sdetkit.contributor_activation_closeout_55",
    "stabilization-closeout": "sdetkit.stabilization_closeout_56",
    "kpi-deep-audit-closeout": "sdetkit.kpi_deep_audit_closeout_57",
    "phase2-hardening-closeout": "sdetkit.phase2_hardening_closeout_58",
    "phase3-preplan-closeout": "sdetkit.phase3_preplan_closeout_59",
    "phase2-wrap-handoff-closeout": "sdetkit.phase2_wrap_handoff_closeout_60",
    "phase3-kickoff-closeout": "sdetkit.phase3_kickoff_closeout_61",
    "community-program-closeout": "sdetkit.community_program_closeout_62",
    "onboarding-activation-closeout": "sdetkit.onboarding_activation_closeout_63",
    "integration-expansion-closeout": "sdetkit.integration_expansion_closeout_64",
    "weekly-review-closeout-2": "sdetkit.weekly_review_closeout_65",
    "integration-expansion2-closeout": "sdetkit.integration_expansion2_closeout_66",
    "integration-expansion3-closeout": "sdetkit.integration_expansion3_closeout_67",
    "integration-expansion4-closeout": "sdetkit.integration_expansion4_closeout_68",
    "case-study-prep1-closeout": "sdetkit.case_study_prep1_closeout_69",
    "case-study-prep2-closeout": "sdetkit.case_study_prep2_closeout_70",
    "case-study-prep3-closeout": "sdetkit.case_study_prep3_closeout_71",
    "case-study-prep4-closeout": "sdetkit.case_study_prep4_closeout_72",
    "case-study-launch-closeout": "sdetkit.case_study_launch_closeout_73",
    "distribution-scaling-closeout": "sdetkit.distribution_scaling_closeout_74",
    "trust-assets-refresh-closeout": "sdetkit.trust_assets_refresh_closeout_75",
    "contributor-recognition-closeout": "sdetkit.contributor_recognition_closeout_76",
    "community-touchpoint-closeout": "sdetkit.community_touchpoint_closeout_77",
    "ecosystem-priorities-closeout": "sdetkit.ecosystem_priorities_closeout_78",
    "scale-upgrade-closeout": "sdetkit.scale_upgrade_closeout_79",
    "partner-outreach-closeout": "sdetkit.partner_outreach_closeout_80",
    "growth-campaign-closeout": "sdetkit.growth_campaign_closeout_81",
    "integration-feedback-closeout": "sdetkit.integration_feedback_closeout_82",
    "trust-faq-expansion-closeout": "sdetkit.trust_faq_expansion_closeout_83",
    "evidence-narrative-closeout": "sdetkit.evidence_narrative_closeout_84",
    "release-prioritization-closeout": "sdetkit.release_prioritization_closeout_85",
    "launch-readiness-closeout": "sdetkit.launch_readiness_closeout_86",
    "governance-handoff-closeout": "sdetkit.governance_handoff_closeout_87",
    "governance-priorities-closeout": "sdetkit.governance_priorities_closeout_88",
    "governance-scale-closeout": "sdetkit.governance_scale_closeout_89",
    "phase3-wrap-publication-closeout": "sdetkit.phase3_wrap_publication_closeout_90",
    "continuous-upgrade-closeout-1": "sdetkit.continuous_upgrade_closeout_1",
    "continuous-upgrade-closeout-2": "sdetkit.continuous_upgrade_closeout_2",
    "continuous-upgrade-closeout-3": "sdetkit.continuous_upgrade_closeout_3",
    "continuous-upgrade-closeout-4": "sdetkit.continuous_upgrade_closeout_4",
    "continuous-upgrade-closeout-5": "sdetkit.continuous_upgrade_closeout_5",
    "continuous-upgrade-closeout-6": "sdetkit.continuous_upgrade_closeout_6",
    "continuous-upgrade-closeout-7": "sdetkit.continuous_upgrade_closeout_7",
    "continuous-upgrade-closeout-8": "sdetkit.continuous_upgrade_closeout_8",
    "continuous-upgrade-closeout-9": "sdetkit.continuous_upgrade_closeout_9",
    "continuous-upgrade-closeout-10": "sdetkit.continuous_upgrade_closeout_10",
    "continuous-upgrade-closeout-11": "sdetkit.continuous_upgrade_closeout_11",
}


def legacy_hints_enabled() -> bool:
    raw = os.environ.get("SDETKIT_LEGACY_HINTS", "1")
    return str(raw).strip().lower() not in {"0", "false", "no", "off"}


def legacy_preferred_surface(command: str) -> str:
    if command.startswith("weekly-review"):
        return "python -m sdetkit weekly-review"
    if command.startswith(("phase1-", "phase2-", "phase3-")):
        return "python -m sdetkit playbooks --help"
    if command.endswith("-closeout"):
        return "python -m sdetkit playbooks --help"
    return "python -m sdetkit kits list"


def legacy_deprecation_horizon(command: str) -> str:
    if command.startswith(("phase1-", "phase2-", "phase3-")):
        return "transition lane: migrate within 1-2 release cycles"
    if command.endswith("-closeout"):
        return "transition lane: migrate within 1-2 release cycles"
    if command.startswith("weekly-review"):
        return "compatibility lane: review migration quarterly"
    return "compatibility lane: migrate when feasible"


def legacy_migration_hint(command: str) -> str:
    preferred = legacy_preferred_surface(command)
    horizon = legacy_deprecation_horizon(command)
    return (
        f"[legacy-hint] '{command}' is a compatibility lane. "
        f"Preferred next surface: {preferred}. "
        f"Deprecation horizon: {horizon}. "
        "Canonical release-confidence path: python -m sdetkit gate fast -> gate release -> doctor."
    )
