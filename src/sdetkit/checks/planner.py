from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .base import CheckDefinition, CheckProfileName, CheckTargetMode, PlannerHint, RegistrySnapshot


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
    target_mode: CheckTargetMode = "full"
    targeting_reason: str = ""
    changed_evidence: tuple[str, ...] = ()
    selected_targets: tuple[str, ...] = ()


@dataclass(frozen=True)
class SkippedCheck:
    id: str
    title: str
    reason: str
    blocking: bool
    category: str = "uncategorized"
    truth_level: str = "adaptive"


@dataclass(frozen=True)
class CheckPlan:
    profile: CheckProfileName
    requested_profile: CheckProfileName
    selected_checks: tuple[PlannedCheck, ...]
    skipped_checks: tuple[SkippedCheck, ...]
    notes: tuple[str, ...] = ()
    planner_selected: bool = False
    changed_files: tuple[str, ...] = ()
    changed_areas: tuple[str, ...] = ()
    adaptive_reason: str = ""

    @property
    def selected_ids(self) -> tuple[str, ...]:
        return tuple(item.id for item in self.selected_checks)


def discover_changed_files(repo_root: Path) -> tuple[str, ...]:
    git_dir = repo_root / ".git"
    if not git_dir.exists():
        return ()
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain", "--untracked-files=all"],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return ()
    changed: list[str] = []
    for raw in proc.stdout.splitlines():
        line = raw.rstrip()
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        path = path.strip()
        if path:
            changed.append(path)
    return tuple(sorted(dict.fromkeys(changed)))


def classify_changed_files(changed_paths: tuple[str, ...]) -> tuple[str, ...]:
    areas: set[str] = set()
    for raw in changed_paths:
        path = Path(raw)
        head = path.parts[0] if path.parts else "root"
        suffix = path.suffix.lower()
        if head == "tests":
            areas.add("tests")
        elif head == "src":
            areas.add("source")
        elif head in {"docs", "examples"}:
            areas.add("docs")
        elif head in {"scripts", ".github"}:
            areas.add("tooling")
        elif suffix in {".md", ".rst"}:
            areas.add("docs")
        elif suffix == ".py":
            areas.add("python")
        else:
            areas.add(head)
    return tuple(sorted(areas))


class CheckPlanner:
    def init_(self, snapshot: RegistrySnapshot) -> None:
        self._snapshot = snapshot

    def plan(
        self,
        profile: CheckProfileName,
        *,
        repo_root: Path | None = None,
        hint: PlannerHint | None = None,
    ) -> CheckPlan:
        requested = profile
        changed_files = self._resolve_changed_files(repo_root, hint)
        changed_areas = classify_changed_files(changed_files)
        resolved, adaptive_reason, adaptive_notes = self._resolve_profile(
            profile,
            repo_root=repo_root,
            hint=hint,
            changed_files=changed_files,
            changed_areas=changed_areas,
        )
        profile_def = self._snapshot.profile(resolved)
        requested_ids = list(profile_def.check_ids)
        selected_defs = self._resolve_dependencies(requested_ids)
        selected_ids = {item.id for item in selected_defs}

        notes = [profile_def.notes]
        notes.extend(adaptive_notes)
        if resolved != requested:
            notes.append(f"adaptive resolved to `{resolved}`: {adaptive_reason}")
        if changed_files:
            notes.append(f"changed files considered: {', '.join(changed_files)}")
        else:
            notes.append("changed files considered: none detected")
        if changed_areas:
            notes.append(f"changed areas: {', '.join(changed_areas)}")
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
                    category=check.category,
                    truth_level=check.truth_level,
                )
            )

        planned_items: list[PlannedCheck] = []
        for check in selected_defs:
            prereq_reason = self._prereq_skip_reason(check, repo_root)
            if prereq_reason:
                skipped.append(
                    SkippedCheck(
                        id=check.id,
                        title=check.title,
                        reason=prereq_reason,
                        blocking=not check.advisory_only,
                        category=check.category,
                        truth_level=check.truth_level,
                    )
                )
                continue
            target_mode, target_reason, selected_targets = self._targeting_for(
                check,
                profile=resolved,
                requested_profile=requested,
                repo_root=repo_root,
                hint=hint,
                changed_files=changed_files,
                changed_areas=changed_areas,
            )
            planned_items.append(
                PlannedCheck(
                    id=check.id,
                    title=check.title,
                    blocking=not check.advisory_only,
                    dependencies=check.dependencies,
                    command=" ".join(check.command),
                    category=check.category,
                    truth_level=check.truth_level,
                    parallel_safe=check.parallel_safe,
                    target_mode=target_mode,
                    targeting_reason=target_reason,
                    changed_evidence=changed_files,
                    selected_targets=selected_targets,
                )
            )
            if target_reason:
                notes.append(f"{check.id} -> {target_mode}: {target_reason}")

        return CheckPlan(
            profile=resolved,
            requested_profile=requested,
            selected_checks=tuple(planned_items),
            skipped_checks=tuple(sorted(skipped, key=lambda item: item.id)),
            notes=tuple(dict.fromkeys(note for note in notes if note)),
            planner_selected=profile_def.planner_selected or resolved != requested,
            changed_files=changed_files,
            changed_areas=changed_areas,
            adaptive_reason=adaptive_reason,
        )

    def _resolve_profile(
        self,
        profile: CheckProfileName,
        *,
        repo_root: Path | None,
        hint: PlannerHint | None,
        changed_files: tuple[str, ...],
        changed_areas: tuple[str, ...],
    ) -> tuple[CheckProfileName, str, tuple[str, ...]]:
        if profile != "adaptive":
            return profile, "requested explicitly", ()

        cpu_count = os.cpu_count() or 1
        ci_like = bool(os.environ.get("CI")) or (
            hint is not None and any(reason.lower().startswith("ci") for reason in hint.reasons)
        )
        has_tests = bool(repo_root is not None and (repo_root / "tests").exists())
        tool_ready = shutil.which("pytest") is not None and shutil.which("ruff") is not None
        docs_only = bool(changed_files) and all(
            path.startswith(("docs/", "examples/")) or Path(path).suffix.lower() in {".md", ".rst"}
            for path in changed_files
        )
        notes = (
            f"adaptive signals: cpu={cpu_count}, ci={ci_like}, has_tests={has_tests}, tool_ready={tool_ready}",
        )

        if ci_like:
            return "strict", "CI-like environment requests merge/release truth", notes
        if docs_only:
            return "quick", "docs/examples-only changes allow the honest smoke lane", notes
        if not has_tests or not tool_ready:
            return (
                "quick",
                "repo/tooling signals are incomplete, so adaptive stays conservative",
                notes,
            )
        if (
            changed_files
            and len(changed_files) <= 8
            and {"source", "tests", "python"} & set(changed_areas)
        ):
            return "standard", "small code change set keeps adaptive on standard validation", notes
        return "standard", "default local path keeps adaptive on standard validation", notes

    def _resolve_changed_files(
        self, repo_root: Path | None, hint: PlannerHint | None
    ) -> tuple[str, ...]:
        if hint is not None and hint.changed_paths:
            return tuple(dict.fromkeys(hint.changed_paths))
        if repo_root is None:
            return ()
        return discover_changed_files(repo_root)

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

    def _targeting_for(
        self,
        check: CheckDefinition,
        *,
        profile: CheckProfileName,
        requested_profile: CheckProfileName,
        repo_root: Path | None,
        hint: PlannerHint | None,
        changed_files: tuple[str, ...],
        changed_areas: tuple[str, ...],
    ) -> tuple[CheckTargetMode, str, tuple[str, ...]]:
        if check.category != "tests":
            return "full", "", ()
        if profile == "strict" or requested_profile == "strict":
            return "full", "strict mode preserves the full truth path", ()
        if hint is not None and not hint.targeted:
            return "smoke", "targeted execution disabled by planner hint", ()
        if not changed_files or len(changed_files) > 8:
            return "smoke", "no small changed-file set available, so smoke scope stays broad", ()
        if not ({"source", "tests", "python"} & set(changed_areas)):
            return "smoke", "changed files are outside the Python test surface", ()
        selected_targets = self._infer_test_targets(repo_root, changed_files)
        if not selected_targets:
            return "smoke", "no safe pytest targets were inferred from changed files", ()
        return (
            "targeted",
            f"small changed-file set maps to targeted pytest scope: {', '.join(selected_targets)}",
            selected_targets,
        )

    def _infer_test_targets(
        self, repo_root: Path | None, changed_files: tuple[str, ...]
    ) -> tuple[str, ...]:
        if repo_root is None:
            return ()
        targets: list[str] = []
        for rel in changed_files:
            path = Path(rel)
            if path.parts[:1] == ("tests",) and path.suffix == ".py":
                if (repo_root / rel).exists():
                    targets.append(rel)
                continue
            if path.parts[:2] == ("src", "sdetkit") and path.suffix == ".py":
                candidate = Path("tests") / f"test_{path.stem}.py"
                if (repo_root / candidate).exists():
                    targets.append(candidate.as_posix())
        return tuple(sorted(dict.fromkeys(targets)))
