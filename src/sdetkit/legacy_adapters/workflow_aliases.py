from __future__ import annotations

LEGACY_CLOSEOUT_COMMAND_MODULES: dict[str, str] = {
    "acceleration-closeout": "sdetkit.acceleration",
    "scale-closeout": "sdetkit.scale",
    "expansion-closeout": "sdetkit.expansion",
    "optimization-closeout": "sdetkit.optimization",
    "reliability-closeout": "sdetkit.reliability",
    "objection-closeout": "sdetkit.objection_handling",
    "weekly-review-closeout": "sdetkit.weekly_review",
    "execution-prioritization-closeout": "sdetkit.execution_prioritization",
    "case-snippet-closeout": "sdetkit.case_snippet_51",
    "narrative-closeout": "sdetkit.narrative_52",
    "docs-loop-closeout": "sdetkit.docs_loop",
    "contributor-activation-closeout": "sdetkit.contributor_activation",
    "stabilization-closeout": "sdetkit.stabilization",
    "kpi-deep-audit-closeout": "sdetkit.kpi_deep_audit",
    "phase2-hardening-closeout": "sdetkit.release_readiness_hardening",
    "phase3-preplan-closeout": "sdetkit.platform_readiness_preplan",
    "phase2-wrap-handoff-closeout": "sdetkit.release_readiness_wrap_handoff",
    "phase3-kickoff-closeout": "sdetkit.platform_readiness_kickoff",
    "community-program-closeout": "sdetkit.community_program",
    "onboarding-activation-closeout": "sdetkit.onboarding_activation_63",
    "integration-expansion-closeout": "sdetkit.integration_expansion_64",
    "weekly-review-closeout-2": "sdetkit.weekly_review_continuity",
    "integration-expansion2-closeout": "sdetkit.gitlab_integration_expansion",
    "integration-expansion3-closeout": "sdetkit.tekton_integration_expansion",
    "integration-expansion4-closeout": "sdetkit.self_hosted_integration_expansion",
    "case-study-prep1-closeout": "sdetkit.reliability_case_study_prep",
    "case-study-prep2-closeout": "sdetkit.triage_speed_case_study_prep",
    "case-study-prep3-closeout": "sdetkit.escalation_quality_case_study_prep",
    "case-study-prep4-closeout": "sdetkit.publication_case_study_prep",
    "case-study-launch-closeout": "sdetkit.case_study_launch",
    "distribution-scaling-closeout": "sdetkit.distribution_scaling",
    "trust-assets-refresh-closeout": "sdetkit.trust_assets_refresh",
    "contributor-recognition-closeout": "sdetkit.contributor_recognition",
    "community-touchpoint-closeout": "sdetkit.community_touchpoint",
    "ecosystem-priorities-closeout": "sdetkit.ecosystem_priorities",
    "scale-upgrade-closeout": "sdetkit.scale_upgrade",
    "partner-outreach-closeout": "sdetkit.partner_outreach",
    "growth-campaign-closeout": "sdetkit.growth_campaign",
    "integration-feedback-closeout": "sdetkit.integration_feedback",
    "trust-faq-expansion-closeout": "sdetkit.trust_faq_expansion",
    "evidence-narrative-closeout": "sdetkit.evidence_narrative",
    "release-prioritization-closeout": "sdetkit.release_prioritization",
    "launch-readiness-closeout": "sdetkit.launch_readiness",
    "governance-handoff-closeout": "sdetkit.governance_handoff",
    "governance-priorities-closeout": "sdetkit.governance_priorities",
    "governance-scale-closeout": "sdetkit.governance_scale",
    "phase3-wrap-publication-closeout": "sdetkit.platform_readiness_wrap_publication",
}


_PHASE_COMMAND_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("phase1", "baseline"),
    ("phase2", "release-readiness"),
    ("phase3", "platform-readiness"),
    ("phase4", "operational-readiness"),
    ("phase5", "adoption-readiness"),
    ("phase6", "scale-readiness"),
)


def professional_canonical_command_for(command: str) -> str:
    canonical = command.replace("closeout", "completion-report")
    for legacy, replacement in _PHASE_COMMAND_REPLACEMENTS:
        canonical = canonical.replace(legacy, replacement)
    return canonical


_PHASE_MODULE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("sdetkit.phase1_", "sdetkit.baseline_"),
    ("sdetkit.phase2_", "sdetkit.release_readiness_"),
    ("sdetkit.phase3_", "sdetkit.platform_readiness_"),
)


def professional_canonical_module_for(module: str) -> str:
    for legacy_prefix, replacement_prefix in _PHASE_MODULE_REPLACEMENTS:
        if module.startswith(legacy_prefix):
            return replacement_prefix + module.removeprefix(legacy_prefix)
    return module


CANONICAL_CLOSEOUT_COMMAND_MODULES: dict[str, str] = {
    professional_canonical_command_for(command): professional_canonical_module_for(module)
    for command, module in LEGACY_CLOSEOUT_COMMAND_MODULES.items()
}
