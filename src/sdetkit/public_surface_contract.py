from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandFamilyContract:
    """Repo-specific contract for major public command families.

    This contract is intentionally small and only covers top-level families.
    It is used for discoverability surfaces (CLI/docs) during productization.
    """

    name: str
    role: str
    stability_tier: str
    first_time_recommended: bool
    transition_legacy_oriented: bool
    top_level_commands: tuple[str, ...]


PUBLIC_SURFACE_CONTRACT: tuple[CommandFamilyContract, ...] = (
    CommandFamilyContract(
        name="stable-core-release-confidence",
        role="Primary release-confidence and shipping-readiness go/no-go path.",
        stability_tier="Stable/Core",
        first_time_recommended=True,
        transition_legacy_oriented=False,
        top_level_commands=("gate", "doctor", "security", "evidence", "playbooks"),
    ),
    CommandFamilyContract(
        name="stable-core-engineering-workflows",
        role="Stable day-to-day engineering and repository utility workflows.",
        stability_tier="Stable/Core",
        first_time_recommended=True,
        transition_legacy_oriented=False,
        top_level_commands=(
            "repo",
            "dev",
            "maintenance",
            "ci",
            "policy",
            "report",
            "kv",
            "apiget",
            "cassette-get",
            "patch",
        ),
    ),
    CommandFamilyContract(
        name="integrations",
        role="Environment-dependent connectors and delivery-system extensions.",
        stability_tier="Integrations",
        first_time_recommended=False,
        transition_legacy_oriented=False,
        top_level_commands=("ops", "notify", "agent", "docs-qa", "docs-nav", "roadmap"),
    ),
    CommandFamilyContract(
        name="playbooks",
        role="Guided adoption and rollout lanes for operational outcomes.",
        stability_tier="Playbooks",
        first_time_recommended=True,
        transition_legacy_oriented=False,
        top_level_commands=(
            "onboarding",
            "weekly-review",
            "first-contribution",
            "contributor-funnel",
            "triage-templates",
            "startup-use-case",
            "enterprise-use-case",
            "demo",
            "proof",
            "quality-contribution-delta",
            "reliability-evidence-pack",
            "release-readiness-board",
            "release-narrative",
            "trust-signal-upgrade",
            "faq-objections",
            "community-activation",
            "external-contribution-push",
            "kpi-audit",
            "github-actions-quickstart",
            "gitlab-ci-quickstart",
        ),
    ),
    CommandFamilyContract(
        name="experimental-transition-lanes",
        role="Transition-era and legacy-oriented lanes retained for compatibility.",
        stability_tier="Experimental",
        first_time_recommended=False,
        transition_legacy_oriented=True,
        top_level_commands=("dayNN-*", "*-closeout", "continuous-upgrade-cycleX-closeout"),
    ),
)


def render_root_help_groups() -> str:
    """Render concise command-family guidance for root CLI help text."""
    lines = ["Command groups:", ""]
    for family in PUBLIC_SURFACE_CONTRACT:
        name = family.name.replace("-", " ")
        lines.append(
            f"  {name} [{family.stability_tier}]"
            f" (first-time: {'yes' if family.first_time_recommended else 'no'};"
            f" transition-era: {'yes' if family.transition_legacy_oriented else 'no'}):"
        )
        lines.append(f"    {family.role}")
        lines.append(f"    {', '.join(family.top_level_commands)}")
        lines.append("")
    lines.append("Run: sdetkit playbooks")
    lines.append("  to list additional playbook flows hidden from the main --help output.")
    return "\n".join(lines)
