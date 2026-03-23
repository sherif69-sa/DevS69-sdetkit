from __future__ import annotations

from typing import cast

from .base import CheckDefinition, CheckProfile, CheckProfileName, RegistrySnapshot, normalize_ids

DEFAULT_CHECKS: tuple[CheckDefinition, ...] = (
    CheckDefinition(
        id="repo_layout",
        title="Repository layout contract",
        category="repo",
        cost="cheap",
        truth_level="smoke",
        parallel_safe=True,
        required_tools=("python3",),
        required_paths=("scripts/check_repo_layout.py",),
        command=("python3", "scripts/check_repo_layout.py"),
        evidence_outputs=("stdout",),
        notes="Protects baseline repo structure before deeper checks run.",
    ),
    CheckDefinition(
        id="format_check",
        title="Ruff format check",
        category="format",
        cost="cheap",
        truth_level="standard",
        parallel_safe=True,
        required_tools=("ruff",),
        command=("python", "-m", "ruff", "format", "--check", "."),
        evidence_outputs=("stdout", "stderr"),
    ),
    CheckDefinition(
        id="lint",
        title="Ruff lint",
        category="lint",
        cost="cheap",
        truth_level="standard",
        parallel_safe=True,
        required_tools=("ruff",),
        command=("python", "-m", "ruff", "check", "."),
        evidence_outputs=("stdout", "stderr"),
    ),
    CheckDefinition(
        id="typing",
        title="Mypy typing",
        category="typing",
        cost="moderate",
        truth_level="standard",
        parallel_safe=True,
        required_tools=("mypy",),
        required_paths=("pyproject.toml", "src"),
        command=("python", "-m", "mypy", "--config-file", "pyproject.toml", "src"),
        evidence_outputs=("stdout", "stderr"),
    ),
    CheckDefinition(
        id="doctor",
        title="Doctor report",
        category="doctor",
        cost="moderate",
        truth_level="smoke",
        parallel_safe=True,
        required_tools=("python",),
        command=(
            "python",
            "-m",
            "sdetkit",
            "doctor",
            "--dev",
            "--ci",
            "--deps",
            "--repo",
            "--upgrade-audit",
            "--format",
            "md",
        ),
        evidence_outputs=("stdout",),
    ),
    CheckDefinition(
        id="tests_smoke",
        title="Fast/smoke tests",
        category="tests",
        cost="moderate",
        truth_level="smoke",
        parallel_safe=False,
        required_tools=("pytest",),
        command=("python", "-m", "sdetkit", "gate", "fast"),
        evidence_outputs=("stdout", "stderr", ".sdetkit/gate.fast.snapshot.json"),
        notes="Useful for local confidence only; never represents merge truth.",
    ),
    CheckDefinition(
        id="tests_full",
        title="Full pytest suite",
        category="tests",
        cost="expensive",
        truth_level="merge",
        dependencies=("format_check", "lint", "typing"),
        parallel_safe=False,
        required_tools=("pytest",),
        command=("python", "-m", "pytest", "-q", "-o", "addopts="),
        evidence_outputs=("stdout", "stderr"),
        notes="This is the full truth path for merge and release verification.",
    ),
    CheckDefinition(
        id="coverage",
        title="Coverage lane",
        category="tests",
        cost="expensive",
        truth_level="standard",
        dependencies=("tests_smoke",),
        parallel_safe=False,
        required_tools=("pytest",),
        command=("python", "-m", "pytest", "--cov=sdetkit"),
        evidence_outputs=("stdout", "stderr"),
    ),
    CheckDefinition(
        id="security_scan",
        title="Offline security scan",
        category="security",
        cost="moderate",
        truth_level="standard",
        parallel_safe=True,
        required_tools=("python",),
        command=(
            "python",
            "-m",
            "sdetkit",
            "security",
            "scan",
            "--fail-on",
            "none",
            "--format",
            "sarif",
        ),
        evidence_outputs=(".sdetkit/out/security.sarif",),
        notes="Generated and non-owned paths are excluded to reduce noise.",
    ),
    CheckDefinition(
        id="maintenance_full",
        title="Maintenance full report",
        category="dependency",
        cost="moderate",
        truth_level="standard",
        parallel_safe=True,
        required_tools=("python",),
        command=(
            "python",
            "-m",
            "sdetkit",
            "maintenance",
            "--mode",
            "full",
            "--format",
            "json",
        ),
        evidence_outputs=(".sdetkit/out/maintenance.json",),
    ),
    CheckDefinition(
        id="evidence_pack",
        title="Evidence pack",
        category="artifacts",
        cost="moderate",
        truth_level="merge",
        dependencies=("tests_full", "security_scan", "maintenance_full"),
        parallel_safe=True,
        required_tools=("python",),
        command=("python", "-m", "sdetkit", "evidence", "pack"),
        evidence_outputs=(".sdetkit/out/evidence.zip",),
    ),
)

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
        check_ids=("repo_layout", "format_check", "lint", "typing", "tests_smoke", "coverage"),
        notes="Balanced default for regular repo validation and daily automation.",
    ),
    CheckProfile(
        name="strict",
        description="Merge/release truth profile.",
        default_truth_level="merge",
        merge_truth=True,
        check_ids=(
            "repo_layout",
            "format_check",
            "lint",
            "typing",
            "tests_full",
            "security_scan",
            "maintenance_full",
            "evidence_pack",
        ),
        notes="Full verification lane used for merge and release decisions.",
    ),
    CheckProfile(
        name="adaptive",
        description="Planner-selected profile based on repo/input context.",
        default_truth_level="adaptive",
        merge_truth=False,
        check_ids=("repo_layout", "format_check", "lint", "typing", "tests_smoke", "security_scan"),
        planner_selected=True,
        notes="Phase-2/3 foundation: planner and scheduler decide the final targeted set.",
    ),
)


class CheckRegistry:
    def __init__(
        self,
        checks: tuple[CheckDefinition, ...] = DEFAULT_CHECKS,
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
