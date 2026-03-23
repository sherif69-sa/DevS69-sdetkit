from __future__ import annotations

import os
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from .results import CheckRecord

CheckCategory = Literal[
    "repo",
    "doctor",
    "lint",
    "format",
    "typing",
    "tests",
    "security",
    "dependency",
    "packaging",
    "docs",
    "release",
    "governance",
    "ci",
    "performance",
    "artifacts",
]
CheckCost = Literal["cheap", "moderate", "expensive"]
CheckTruthLevel = Literal["smoke", "standard", "merge", "adaptive"]
CheckProfileName = Literal["quick", "standard", "strict", "adaptive"]
CheckStatus = Literal["passed", "failed", "skipped"]
CheckRunner = Callable[["CheckContext"], "CheckRecord"]


@dataclass(frozen=True)
class CheckContext:
    repo_root: Path
    out_dir: Path
    env: Mapping[str, str] = field(default_factory=lambda: dict(os.environ))
    python_executable: str = sys.executable

    def resolve(self, *parts: str) -> Path:
        return self.repo_root.joinpath(*parts)

    def artifact_path(self, name: str) -> Path:
        return self.out_dir / name


@dataclass(frozen=True)
class CheckDefinition:
    id: str
    title: str
    category: CheckCategory
    cost: CheckCost
    truth_level: CheckTruthLevel
    dependencies: tuple[str, ...] = ()
    parallel_safe: bool = True
    required_tools: tuple[str, ...] = ()
    required_paths: tuple[str, ...] = ()
    advisory_only: bool = False
    profile_names: tuple[CheckProfileName, ...] = ("quick", "standard", "strict", "adaptive")
    command: tuple[str, ...] = ()
    evidence_outputs: tuple[str, ...] = ()
    run: CheckRunner | None = None
    notes: str = ""


@dataclass(frozen=True)
class CheckProfile:
    name: CheckProfileName
    description: str
    default_truth_level: CheckTruthLevel
    merge_truth: bool
    check_ids: tuple[str, ...]
    planner_selected: bool = False
    notes: str = ""


@dataclass(frozen=True)
class PlannerHint:
    profile: CheckProfileName
    reasons: tuple[str, ...] = ()
    changed_paths: tuple[str, ...] = ()
    targeted: bool = False
    cache_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class SchedulerPlan:
    profile: CheckProfileName
    selected_checks: tuple[str, ...]
    concurrency: int
    blocked_checks: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass
class RegistrySnapshot:
    profiles: dict[CheckProfileName, CheckProfile] = field(default_factory=dict)
    checks: dict[str, CheckDefinition] = field(default_factory=dict)

    def profile(self, name: CheckProfileName) -> CheckProfile:
        return self.profiles[name]

    def check(self, check_id: str) -> CheckDefinition:
        return self.checks[check_id]

    def checks_for_profile(self, profile: CheckProfileName) -> tuple[CheckDefinition, ...]:
        configured = self.profile(profile).check_ids
        return tuple(self.check(check_id) for check_id in configured)

    def categories(self) -> tuple[str, ...]:
        return tuple(sorted({check.category for check in self.checks.values()}))


def normalize_ids(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
