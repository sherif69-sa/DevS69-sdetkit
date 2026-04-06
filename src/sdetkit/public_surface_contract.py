from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandFamilyContract:
    """Repo-specific contract for major public command families."""

    name: str
    role: str
    stability_tier: str
    first_time_recommended: bool
    transition_legacy_oriented: bool
    top_level_commands: tuple[str, ...]


PUBLIC_SURFACE_CONTRACT: tuple[CommandFamilyContract, ...] = (
    CommandFamilyContract(
        name="umbrella-kits",
        role="Primary product surface for release confidence, test intelligence, integration assurance, and failure forensics.",
        stability_tier="Advanced but supported",
        first_time_recommended=True,
        transition_legacy_oriented=False,
        top_level_commands=("kits", "release", "intelligence", "integration", "forensics"),
    ),
    CommandFamilyContract(
        name="compatibility-aliases",
        role="Backward-compatible direct lanes preserved for existing automation and muscle memory.",
        stability_tier="Public / stable",
        first_time_recommended=False,
        transition_legacy_oriented=False,
        top_level_commands=("gate", "doctor", "security", "repo", "evidence", "report", "policy"),
    ),
    CommandFamilyContract(
        name="supporting-utilities-and-automation",
        role="Supporting utilities and automation lanes; useful but intentionally secondary to flagship kits.",
        stability_tier="Advanced but supported",
        first_time_recommended=False,
        transition_legacy_oriented=False,
        top_level_commands=(
            "repo",
            "dev",
            "maintenance",
            "ci",
            "kv",
            "apiget",
            "cassette-get",
            "patch",
            "ops",
            "notify",
            "agent",
            "feature-registry",
        ),
    ),
    CommandFamilyContract(
        name="playbooks",
        role="Guided adoption and rollout lanes for operational outcomes.",
        stability_tier="Advanced but supported",
        first_time_recommended=False,
        transition_legacy_oriented=False,
        top_level_commands=(
            "playbooks",
            "onboarding",
            "weekly-review",
            "first-contribution",
            "demo",
        ),
    ),
    CommandFamilyContract(
        name="experimental-transition-lanes",
        role="Transition-era and legacy-oriented lanes retained for compatibility.",
        stability_tier="Experimental / incubator",
        first_time_recommended=False,
        transition_legacy_oriented=True,
        top_level_commands=("legacy compatibility lanes", "archived transition commands"),
    ),
)


def render_root_help_groups() -> str:
    """Render concise command-family guidance for root CLI help text."""
    lines = ["Command groups:", ""]
    for family in PUBLIC_SURFACE_CONTRACT:
        name = family.name.replace("-", " ")
        lines.append(
            f"  {name} [{family.stability_tier}]"
            f" (use first: {'yes' if family.first_time_recommended else 'no'};"
            f" transition-era: {'yes' if family.transition_legacy_oriented else 'no'}):"
        )
        lines.append(f"    {family.role}")
        lines.append(f"    {', '.join(family.top_level_commands)}")
        lines.append("")
    lines.append("Start with: python -m sdetkit gate fast -> gate release -> doctor")
    lines.append("Then expand: python -m sdetkit kits list")
    return "\n".join(lines)
