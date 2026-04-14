from __future__ import annotations

from collections.abc import Callable, Sequence

_PARSED_MODULE_SHORTCUTS: tuple[tuple[str, str], ...] = (
    ("patch", "sdetkit.patch"),
    ("repo", "sdetkit.repo"),
    ("feature-registry", "sdetkit.feature_registry_cli"),
    ("report", "sdetkit.report"),
    ("maintenance", "sdetkit.maintenance"),
    ("agent", "sdetkit.agent.cli"),
    ("security", "sdetkit.security_gate"),
    ("ops", "sdetkit.ops"),
    ("notify", "sdetkit.notify"),
    ("policy", "sdetkit.policy"),
    ("author", "sdetkit.author_problem"),
    ("forensics", "sdetkit.forensics"),
    ("kv", "sdetkit.kvcli"),
    ("evidence", "sdetkit.evidence"),
    ("onboarding", "sdetkit.onboarding"),
    ("onboarding-optimization", "sdetkit.onboarding_optimization"),
    ("community-activation", "sdetkit.community_activation"),
    ("external-contribution", "sdetkit.external_contribution"),
    ("kpi-audit", "sdetkit.kpi_audit"),
    ("kpi-report", "sdetkit.kpi_report"),
    ("objection-handling", "sdetkit.objection_handling"),
    ("demo", "sdetkit.demo"),
    ("first-contribution", "sdetkit.first_contribution"),
    ("contributor-funnel", "sdetkit.contributor_funnel"),
    ("evidence-assets", "sdetkit.proof"),
    ("triage-templates", "sdetkit.triage_templates"),
    ("docs-quality", "sdetkit.docs_qa"),
    ("weekly-review", "sdetkit.weekly_review"),
    ("docs-governance", "sdetkit.docs_navigation"),
    ("roadmap", "sdetkit.roadmap"),
    ("startup-readiness", "sdetkit.startup_readiness"),
    ("upgrade-hub", "sdetkit.upgrade_hub"),
    ("sdet-package", "sdetkit.sdet_package"),
    ("enterprise-readiness", "sdetkit.enterprise_readiness"),
    ("github-actions-onboarding", "sdetkit.github_actions_quickstart"),
    ("gitlab-ci-onboarding", "sdetkit.gitlab_ci_quickstart"),
    ("contribution-quality-report", "sdetkit.quality_contribution_delta"),
    ("reliability-evidence-pack", "sdetkit.reliability_evidence_pack"),
    ("release-readiness", "sdetkit.release_readiness"),
    ("release-communications", "sdetkit.release_communications"),
    ("trust-assets", "sdetkit.trust_assets"),
)


def dispatch_parsed_shortcut(
    cmd: str,
    args: Sequence[str],
    *,
    run_module_main: Callable[[str, Sequence[str]], int],
) -> int | None:
    if cmd == "dev":
        return run_module_main("sdetkit.repo", ["dev", *list(args)])
    for shortcut, module in _PARSED_MODULE_SHORTCUTS:
        if cmd == shortcut:
            return run_module_main(module, list(args))
    return None
