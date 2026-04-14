from __future__ import annotations

from sdetkit.legacy_commands import (
    LEGACY_COMMAND_MODULES,
    LEGACY_NAMESPACE_COMMANDS,
    legacy_deprecation_horizon,
    legacy_migration_hint,
    legacy_preferred_surface,
)


def test_legacy_namespace_subset_still_mapped() -> None:
    for command in LEGACY_NAMESPACE_COMMANDS:
        assert command in LEGACY_COMMAND_MODULES


def test_legacy_preferred_surface_routes_weekly_review() -> None:
    assert legacy_preferred_surface("weekly-review-lane") == "python -m sdetkit weekly-review"


def test_legacy_preferred_surface_routes_closeout_to_playbooks() -> None:
    assert legacy_preferred_surface("scale-closeout") == "python -m sdetkit playbooks --help"


def test_legacy_deprecation_horizon_phase_lane() -> None:
    assert (
        legacy_deprecation_horizon("phase1-hardening")
        == "transition lane: migrate within 1-2 release cycles"
    )


def test_legacy_migration_hint_mentions_canonical_path() -> None:
    hint = legacy_migration_hint("weekly-review-lane")
    assert "gate fast -> gate release -> doctor" in hint
