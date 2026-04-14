from __future__ import annotations

from collections.abc import Callable, Sequence

from .legacy_cli import emit_legacy_migration_hint
from .legacy_commands import LEGACY_COMMAND_MODULES

_MODULE_SHORTCUTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("patch",), "sdetkit.patch"),
    (("repo",), "sdetkit.repo"),
    (("report",), "sdetkit.report"),
    (("contract",), "sdetkit.contract"),
    (("maintenance",), "sdetkit.maintenance"),
    (("agent",), "sdetkit.agent.cli"),
    (("security",), "sdetkit.security_gate"),
    (("ops",), "sdetkit.ops"),
    (("notify",), "sdetkit.notify"),
    (("policy",), "sdetkit.policy"),
    (("evidence",), "sdetkit.evidence"),
    (("onboarding",), "sdetkit.onboarding"),
    (("onboarding-optimization",), "sdetkit.onboarding_optimization"),
    (("phase-boost",), "sdetkit.phase_boost"),
    (("production-readiness",), "sdetkit.production_readiness"),
    (("community-activation",), "sdetkit.community_activation"),
    (("external-contribution",), "sdetkit.external_contribution"),
    (("kpi-audit",), "sdetkit.kpi_audit"),
    (("kpi-report",), "sdetkit.kpi_report"),
    (("objection-handling",), "sdetkit.objection_handling"),
    (("first-contribution",), "sdetkit.first_contribution"),
    (("demo",), "sdetkit.demo"),
    (("contributor-funnel",), "sdetkit.contributor_funnel"),
    (("evidence-assets", "proof"), "sdetkit.proof"),
    (("triage-templates",), "sdetkit.triage_templates"),
    (("docs-quality", "docs-qa"), "sdetkit.docs_qa"),
    (("weekly-review",), "sdetkit.weekly_review"),
    (("docs-governance", "docs-nav"), "sdetkit.docs_navigation"),
    (("roadmap",), "sdetkit.roadmap"),
    (("startup-readiness",), "sdetkit.startup_readiness"),
    (("upgrade-hub",), "sdetkit.upgrade_hub"),
    (("sdet-package",), "sdetkit.sdet_package"),
    (("enterprise-readiness",), "sdetkit.enterprise_readiness"),
    (("github-actions-onboarding", "github-actions-quickstart"), "sdetkit.github_actions_quickstart"),
    (("gitlab-ci-onboarding", "gitlab-ci-quickstart"), "sdetkit.gitlab_ci_quickstart"),
    (("contribution-quality-report", "quality-contribution-delta"), "sdetkit.quality_contribution_delta"),
    (("reliability-evidence-pack",), "sdetkit.reliability_evidence_pack"),
    (("release-readiness",), "sdetkit.release_readiness"),
    (("release-communications",), "sdetkit.release_communications"),
    (("trust-assets",), "sdetkit.trust_assets"),
    (("feature-registry",), "sdetkit.feature_registry_cli"),
)


def dispatch_preparse_shortcut(
    argv: Sequence[str],
    *,
    no_legacy_hint: bool,
    run_module_main: Callable[[str, Sequence[str]], int],
) -> int | None:
    if not argv:
        return None
    command = str(argv[0])
    args = list(argv[1:])

    if command == "dev":
        return run_module_main("sdetkit.repo", ["dev", *args])

    for aliases, module in _MODULE_SHORTCUTS:
        if command in aliases:
            return run_module_main(module, args)

    legacy_module = LEGACY_COMMAND_MODULES.get(command)
    if legacy_module:
        if not no_legacy_hint:
            emit_legacy_migration_hint(command)
        return run_module_main(legacy_module, args)

    return None
