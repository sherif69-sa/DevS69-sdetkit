from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast


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
        role="Umbrella kits are fully supported expansion surfaces for release, intelligence, integration, and forensics workflows after the canonical first-time path.",
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
            "inspect",
            "review",
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


def load_public_command_surface_contract() -> dict[str, object]:
    contract_path = Path(__file__).with_name("public_command_surface.json")
    loaded = json.loads(contract_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        return {}
    return cast(dict[str, object], loaded)


def render_root_help_groups() -> str:
    """Render concise command-family guidance for root CLI help text."""
    contract = load_public_command_surface_contract()
    canonical_obj = contract.get(
        "canonical_first_path",
        [
            "python -m sdetkit gate fast",
            "python -m sdetkit gate release",
            "python -m sdetkit doctor",
        ],
    )
    canonical = canonical_obj if isinstance(canonical_obj, list) else []
    next_step = contract.get("advanced_supported_next_step", "python -m sdetkit kits list")
    tier_a = contract.get("tier_a_contract_commands", [])
    tier_b = contract.get("tier_b_contract_commands", [])
    best_effort = contract.get("best_effort_compatibility_commands", [])
    canonical_summary = " -> ".join(
        cmd.replace("python -m sdetkit ", "") if isinstance(cmd, str) else str(cmd)
        for cmd in canonical
    )
    lines = [
        "Command discovery (stability-aware):",
        "",
        "  Canonical first-time path (public / stable):",
        f"    {canonical_summary}",
        "",
        "  Frozen command contracts:",
        f"    Tier A (public/stable): {', '.join(tier_a) if isinstance(tier_a, list) else ''}",
        f"    Tier B (advanced/supported): {', '.join(tier_b) if isinstance(tier_b, list) else ''}",
        "    Remaining lanes: best-effort compatibility (subject to change).",
        (
            f"      {', '.join(best_effort)}"
            if isinstance(best_effort, list)
            else "      legacy compatibility lanes"
        ),
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
    lines.append(f"Next step (advanced but supported): {next_step}")
    return "\n".join(lines)
