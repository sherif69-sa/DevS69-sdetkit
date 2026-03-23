from __future__ import annotations

from typing import cast

from .base import CheckProfile, CheckProfileName, RegistrySnapshot, normalize_ids
from .builtin import BUILTIN_CHECKS

DEFAULT_CHECKS = BUILTIN_CHECKS

DEFAULT_PROFILES: tuple[CheckProfile, ...] = (
    CheckProfile(
        name="quick",
        description="Fast local confidence / smoke profile.",
        default_truth_level="smoke",
        merge_truth=False,
        check_ids=("repo_layout", "format_check", "lint", "typing", "tests_smoke"),
        notes="Honest smoke lane for developers; passing does not imply merge readiness.",
    ),
    CheckProfile(
        name="standard",
        description="Default repository validation profile.",
        default_truth_level="standard",
        merge_truth=False,
        check_ids=(
            "repo_layout",
            "doctor_core",
            "format_check",
            "lint",
            "typing",
            "tests_smoke",
            "security_source_scan",
        ),
        notes="Balanced default for daily repo validation with advisory doctor/security signal.",
    ),
    CheckProfile(
        name="strict",
        description="Merge/release truth profile.",
        default_truth_level="merge",
        merge_truth=True,
        check_ids=(
            "repo_layout",
            "doctor_core",
            "format_check",
            "lint",
            "typing",
            "tests_full",
            "security_source_scan",
        ),
        notes="Full verification lane for merge and release decisions; full tests replace smoke tests.",
    ),
    CheckProfile(
        name="adaptive",
        description="Planner-selected profile based on repo/input context.",
        default_truth_level="adaptive",
        merge_truth=False,
        check_ids=(
            "repo_layout",
            "doctor_core",
            "format_check",
            "lint",
            "typing",
            "tests_smoke",
            "security_source_scan",
        ),
        planner_selected=True,
        notes="Phase-2 adaptive mode resolves conservatively to quick, standard, or strict.",
    ),
)


class CheckRegistry:
    def __init__(
        self,
        checks=DEFAULT_CHECKS,
        profiles: tuple[CheckProfile, ...] = DEFAULT_PROFILES,
    ) -> None:
        self._snapshot = RegistrySnapshot(
            profiles={profile.name: profile for profile in profiles},
            checks={check.id: check for check in checks},
        )

    def snapshot(self) -> RegistrySnapshot:
        return self._snapshot

    def profile_names(self) -> tuple[str, ...]:
        return tuple(self._snapshot.profiles)

    def profile_check_ids(self, profile: str) -> tuple[str, ...]:
        return self._snapshot.profile(cast(CheckProfileName, profile)).check_ids

    def check_ids(self) -> tuple[str, ...]:
        return tuple(self._snapshot.checks)

    def planner_seed(self, profile: str = "adaptive") -> dict[str, object]:
        profile_def = self._snapshot.profile(cast(CheckProfileName, profile))
        return {
            "profile": profile_def.name,
            "planner_selected": profile_def.planner_selected,
            "check_ids": list(profile_def.check_ids),
            "notes": profile_def.notes,
            "categories": list(self._snapshot.categories()),
        }


def default_registry() -> CheckRegistry:
    return CheckRegistry()


def profile_definitions() -> tuple[CheckProfile, ...]:
    return DEFAULT_PROFILES


def registry_snapshot() -> RegistrySnapshot:
    return default_registry().snapshot()


def planner_seed(profile: str = "adaptive") -> dict[str, object]:
    return default_registry().planner_seed(profile)


def check_ids_for_profile(profile: str) -> tuple[str, ...]:
    return normalize_ids(default_registry().profile_check_ids(profile))
