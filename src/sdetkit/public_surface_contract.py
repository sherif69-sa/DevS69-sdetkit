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
        name="release-confidence-canonical-path",
        role="Primary first-time product surface for deterministic shipping readiness; one primary outcome (know if a change is ready to ship) and one canonical command path.",
        stability_tier="Public / stable",
        first_time_recommended=True,
        transition_legacy_oriented=False,
        top_level_commands=("gate", "doctor", "release"),
    ),
    CommandFamilyContract(
        name="umbrella-kits",
        role="Umbrella kits are fully supported expansion surfaces for release, intelligence, integration, and forensics workflows after the canonical first proof path.",
        stability_tier="Advanced but supported",
        first_time_recommended=False,
        transition_legacy_oriented=False,
        top_level_commands=("kits", "release", "intelligence", "integration", "forensics"),
    ),
    CommandFamilyContract(
        name="compatibility-aliases",
        role="Backward-compatible direct lanes preserved for existing automation and muscle memory; visible but secondary for first-time discovery.",
        stability_tier="Public / stable",
        first_time_recommended=False,
        transition_legacy_oriented=False,
        top_level_commands=("gate", "doctor", "security", "repo", "evidence", "report", "policy"),
    ),
    CommandFamilyContract(
        name="supporting-utilities-and-automation",
        role="Supporting utilities and automation lanes; useful but intentionally secondary to the canonical public/stable first-time path.",
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
        role="Transition-era and legacy-oriented lanes retained for compatibility and historical continuity.",
        stability_tier="Experimental / incubator",
        first_time_recommended=False,
        transition_legacy_oriented=True,
        top_level_commands=("legacy compatibility lanes", "archived transition commands"),
    ),
)


def render_root_help_groups() -> str:
    """Render concise command-family guidance for root CLI help text."""
    lines = [
        "Command discovery (stability-aware):",
        "",
        "  Canonical first-time path (public / stable):",
        "    python -m sdetkit gate fast -> gate release -> doctor",
        "",
        "  Then expand deliberately:",
    ]
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
    lines.append("Next step (advanced but supported): python -m sdetkit kits list")
    return "\n".join(lines)
