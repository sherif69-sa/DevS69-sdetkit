from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .base import CheckDefinition, CheckProfileName, PlannerHint, RegistrySnapshot


@dataclass(frozen=True)
class PlannedCheck:
    id: str
    title: str
    blocking: bool
    dependencies: tuple[str, ...]
    command: str
    category: str
    truth_level: str
    parallel_safe: bool


@dataclass(frozen=True)
class SkippedCheck:
    id: str
    title: str
    reason: str
    blocking: bool


@dataclass(frozen=True)
class CheckPlan:
    profile: CheckProfileName
    requested_profile: CheckProfileName
    selected_checks: tuple[PlannedCheck, ...]
    skipped_checks: tuple[SkippedCheck, ...]
    notes: tuple[str, ...] = ()
    planner_selected: bool = False

    @property
    def selected_ids(self) -> tuple[str, ...]:
        return tuple(item.id for item in self.selected_checks)


class CheckPlanner:
    def __init__(self, snapshot: RegistrySnapshot) -> None:
        self._snapshot = snapshot

    def plan(
        self,
        profile: CheckProfileName,
        *,
        repo_root: Path | None = None,
        hint: PlannerHint | None = None,
    ) -> CheckPlan:
        requested = profile
        resolved = self._resolve_profile(profile, repo_root=repo_root, hint=hint)
        profile_def = self._snapshot.profile(resolved)
        requested_ids = list(profile_def.check_ids)
        selected_defs = self._resolve_dependencies(requested_ids)
        selected_ids = {item.id for item in selected_defs}

        notes = [profile_def.notes]
        if resolved != requested:
            notes.append(f"adaptive resolved to `{resolved}` based on current repo/machine context")
        if hint is not None:
            notes.extend(hint.reasons)

        skipped: list[SkippedCheck] = []
        for check_id, check in self._snapshot.checks.items():
            if check_id in selected_ids:
                continue
            if check_id in requested_ids:
                continue
            reason = self._skip_reason_for_unselected(check, resolved)
            skipped.append(
                SkippedCheck(
                    id=check.id,
                    title=check.title,
                    reason=reason,
                    blocking=not check.advisory_only,
                )
            )

        for check in selected_defs:
            prereq_reason = self._prereq_skip_reason(check, repo_root)
            if prereq_reason:
                skipped.append(
                    SkippedCheck(
                        id=check.id,
                        title=check.title,
                        reason=prereq_reason,
                        blocking=not check.advisory_only,
                    )
                )

        skipped_ids = {item.id for item in skipped}
        selected = tuple(
            PlannedCheck(
                id=check.id,
                title=check.title,
                blocking=not check.advisory_only,
                dependencies=check.dependencies,
                command=" ".join(check.command),
                category=check.category,
                truth_level=check.truth_level,
                parallel_safe=check.parallel_safe,
            )
            for check in selected_defs
            if check.id not in skipped_ids
        )

        return CheckPlan(
            profile=resolved,
            requested_profile=requested,
            selected_checks=selected,
            skipped_checks=tuple(sorted(skipped, key=lambda item: item.id)),
            notes=tuple(note for note in notes if note),
            planner_selected=profile_def.planner_selected or resolved != requested,
        )

    def _resolve_profile(
        self,
        profile: CheckProfileName,
        *,
        repo_root: Path | None,
        hint: PlannerHint | None,
    ) -> CheckProfileName:
        if profile != "adaptive":
            return profile

        changed_paths = {Path(item).as_posix() for item in (hint.changed_paths if hint else ())}
        ci_like = False
        if hint is not None and any(reason.lower().startswith("ci") for reason in hint.reasons):
            ci_like = True
        if changed_paths and all(path.startswith(("docs/", "examples/")) for path in changed_paths):
            return "quick"
        if ci_like:
            return "strict"
        if repo_root is not None and (repo_root / "tests").exists():
            return "standard"
        return "quick"

    def _resolve_dependencies(self, requested_ids: list[str]) -> tuple[CheckDefinition, ...]:
        ordered: list[CheckDefinition] = []
        seen: set[str] = set()

        def visit(check_id: str) -> None:
            if check_id in seen:
                return
            seen.add(check_id)
            check = self._snapshot.check(check_id)
            for dep in check.dependencies:
                visit(dep)
            ordered.append(check)

        for check_id in requested_ids:
            visit(check_id)
        return tuple(ordered)

    def _prereq_skip_reason(self, check: CheckDefinition, repo_root: Path | None) -> str | None:
        missing_tools = [tool for tool in check.required_tools if shutil.which(tool) is None]
        if missing_tools:
            return f"missing required tool(s): {', '.join(sorted(missing_tools))}"
        if repo_root is not None:
            missing_paths = [
                path for path in check.required_paths if not (repo_root / path).exists()
            ]
            if missing_paths:
                return f"missing required path(s): {', '.join(sorted(missing_paths))}"
        return None

    def _skip_reason_for_unselected(self, check: CheckDefinition, profile: CheckProfileName) -> str:
        if check.id == "tests_full" and profile != "strict":
            return f"{profile} profile favors faster validation; run strict for merge truth"
        if check.id == "tests_smoke" and profile == "strict":
            return "strict profile uses full tests instead of smoke gate"
        return f"not selected in {profile} profile"
