from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .base import CheckContext, RegistrySnapshot
from .cache import CheckCache
from .planner import CheckPlan, PlannedCheck
from .results import CheckRecord, FinalVerdict, build_final_verdict


@dataclass(frozen=True)
class CheckRunReport:
    plan: CheckPlan
    records: tuple[CheckRecord, ...]
    verdict: FinalVerdict

    def as_dict(self) -> dict[str, Any]:
        payload = self.verdict.as_dict()
        payload["plan"] = {
            "profile": self.plan.profile,
            "requested_profile": self.plan.requested_profile,
            "selected_checks": [
                {
                    "id": item.id,
                    "title": item.title,
                    "blocking": item.blocking,
                    "dependencies": list(item.dependencies),
                    "command": item.command,
                    "category": item.category,
                    "truth_level": item.truth_level,
                    "parallel_safe": item.parallel_safe,
                    "target_mode": item.target_mode,
                    "targeting_reason": item.targeting_reason,
                    "changed_evidence": list(item.changed_evidence),
                    "selected_targets": list(item.selected_targets),
                }
                for item in self.plan.selected_checks
            ],
            "skipped_checks": [
                {
                    "id": item.id,
                    "title": item.title,
                    "reason": item.reason,
                    "blocking": item.blocking,
                }
                for item in self.plan.skipped_checks
            ],
            "notes": list(self.plan.notes),
            "planner_selected": self.plan.planner_selected,
            "changed_files": list(self.plan.changed_files),
            "changed_areas": list(self.plan.changed_areas),
            "adaptive_reason": self.plan.adaptive_reason,
        }
        return payload


class CheckRunner:
    def __init__(self, snapshot: RegistrySnapshot) -> None:
        self._snapshot = snapshot

    def run(
        self,
        plan: CheckPlan,
        *,
        repo_root: Path,
        out_dir: Path,
        env: dict[str, str],
        python_executable: str,
        use_cache: bool = True,
        max_workers: int | None = None,
    ) -> CheckRunReport:
        base_ctx = CheckContext(
            repo_root=repo_root,
            out_dir=out_dir,
            env=env,
            python_executable=python_executable,
            profile=plan.profile,
            changed_paths=plan.changed_files,
        )
        cache = CheckCache(out_dir / "cache" / "checks", enabled=use_cache)
        completed: dict[str, CheckRecord] = {
            skipped.id: CheckRecord(
                id=skipped.id,
                title=skipped.title,
                status="skipped",
                blocking=skipped.blocking,
                reason=skipped.reason,
                metadata={
                    "category": skipped.category,
                    "truth_level": skipped.truth_level,
                    "target_mode": "full",
                    "cache": {"status": "not-applicable"},
                    "execution": {"status": "skipped"},
                },
            )
            for skipped in plan.skipped_checks
        }

        plan_items = list(plan.selected_checks)
        workers = self._select_workers(plan_items, max_workers=max_workers)
        execution_mode = "parallel" if workers > 1 else "sequential"
        pending_ids = {item.id for item in plan_items}
        futures: dict[Any, PlannedCheck] = {}

        with ThreadPoolExecutor(max_workers=workers) as executor:
            while pending_ids or futures:
                progressed = False
                for item in plan_items:
                    if item.id not in pending_ids:
                        continue
                    if item.id in completed or any(
                        existing.id == item.id for existing in futures.values()
                    ):
                        continue
                    if any(dep not in completed for dep in item.dependencies):
                        continue
                    blocked_by = [
                        dep
                        for dep in item.dependencies
                        if completed[dep].status in {"failed", "skipped"}
                    ]
                    if blocked_by:
                        completed[item.id] = CheckRecord(
                            id=item.id,
                            title=item.title,
                            status="skipped",
                            blocking=item.blocking,
                            reason=f"dependency not satisfied: {', '.join(blocked_by)}",
                            command=item.command,
                            metadata={
                                "category": item.category,
                                "truth_level": item.truth_level,
                                "target_mode": item.target_mode,
                                "target_reason": item.targeting_reason,
                                "changed_paths": list(item.changed_evidence),
                                "selected_targets": list(item.selected_targets),
                                "cache": {"status": "not-applicable"},
                                "execution": {"mode": execution_mode, "workers": workers},
                            },
                        )
                        pending_ids.remove(item.id)
                        progressed = True
                        continue
                    if not item.parallel_safe and futures:
                        continue
                    if item.parallel_safe and workers == 1 and futures:
                        continue
                    future = executor.submit(
                        self._execute_item,
                        item,
                        base_ctx,
                        cache,
                        execution_mode,
                        workers,
                    )
                    futures[future] = item
                    pending_ids.remove(item.id)
                    progressed = True
                    if not item.parallel_safe:
                        break
                    if len(futures) >= workers:
                        break

                if not futures:
                    if not progressed:
                        break
                    continue

                done, _ = wait(set(futures), return_when=FIRST_COMPLETED)
                for future in done:
                    item = futures.pop(future)
                    completed[item.id] = future.result()

        records = [completed[item.id] for item in plan_items if item.id in completed]
        records.extend(
            completed[item.id]
            for item in sorted(plan.skipped_checks, key=lambda skipped: skipped.id)
            if item.id in completed
        )
        ordered_records = tuple(
            sorted(records, key=lambda record: self._record_order(record.id, plan))
        )

        verdict = build_final_verdict(
            profile=plan.profile,
            checks=list(ordered_records),
            profile_notes="; ".join(plan.notes),
            metadata={
                "source": "sdetkit.checks.runner",
                "checks_recorded": len(ordered_records),
                "requested_profile": plan.requested_profile,
                "selected_checks": list(plan.selected_ids),
                "changed_files": list(plan.changed_files),
                "changed_areas": list(plan.changed_areas),
                "adaptive_reason": plan.adaptive_reason,
                "execution": {"mode": execution_mode, "workers": workers},
                "cache_enabled": use_cache,
            },
        )
        return CheckRunReport(plan=plan, records=ordered_records, verdict=verdict)

    def _select_workers(self, plan_items: list[PlannedCheck], *, max_workers: int | None) -> int:
        safe_count = sum(1 for item in plan_items if item.parallel_safe)
        if safe_count <= 1:
            return 1
        if max_workers is not None:
            return max(1, min(safe_count, max_workers))
        cpu_count = max(1, __import__("os").cpu_count() or 1)
        suggested = min(safe_count, max(1, min(4, cpu_count // 2 or 1)))
        return max(1, suggested)

    def _execute_item(
        self,
        item: PlannedCheck,
        base_ctx: CheckContext,
        cache: CheckCache,
        execution_mode: str,
        workers: int,
    ) -> CheckRecord:
        definition = self._snapshot.check(item.id)
        ctx = base_ctx.for_check(
            check_id=item.id,
            target_mode=item.target_mode,
            target_reason=item.targeting_reason,
            selected_targets=item.selected_targets,
        )
        cache_key = cache.key_for(
            repo_root=ctx.repo_root,
            check_id=item.id,
            profile=ctx.profile,
            target_mode=item.target_mode,
            command=item.command,
            changed_paths=item.changed_evidence,
            selected_targets=item.selected_targets,
        )
        if definition.cacheable:
            cached = cache.load(cache_key)
            if cached is not None:
                metadata = dict(cached.metadata)
                metadata.setdefault("category", item.category)
                metadata.setdefault("truth_level", item.truth_level)
                metadata.setdefault("target_mode", item.target_mode)
                metadata.setdefault("target_reason", item.targeting_reason)
                metadata.setdefault("changed_paths", list(item.changed_evidence))
                metadata.setdefault("selected_targets", list(item.selected_targets))
                metadata["execution"] = {"mode": execution_mode, "workers": workers}
                return CheckRecord(**{**cached.__dict__, "metadata": metadata})
        if definition.run is None:
            record = CheckRecord(
                id=item.id,
                title=item.title,
                status="skipped",
                blocking=item.blocking,
                reason="check has no execution wiring yet",
                command=item.command,
                metadata={
                    "category": item.category,
                    "truth_level": item.truth_level,
                    "target_mode": item.target_mode,
                    "target_reason": item.targeting_reason,
                    "changed_paths": list(item.changed_evidence),
                    "selected_targets": list(item.selected_targets),
                    "cache": {"status": "not-applicable"},
                    "execution": {"mode": execution_mode, "workers": workers},
                },
            )
        else:
            record = definition.run(ctx)
            metadata = dict(record.metadata)
            metadata.setdefault("category", item.category)
            metadata.setdefault("truth_level", item.truth_level)
            metadata.setdefault("target_mode", item.target_mode)
            metadata.setdefault("target_reason", item.targeting_reason)
            metadata.setdefault("changed_paths", list(item.changed_evidence))
            metadata.setdefault("selected_targets", list(item.selected_targets))
            metadata["execution"] = {"mode": execution_mode, "workers": workers}
            cache_meta = dict(metadata.get("cache", {}))
            cache_meta.setdefault("status", "fresh")
            cache_meta["key"] = cache_key
            metadata["cache"] = cache_meta
            record = CheckRecord(**{**record.__dict__, "metadata": metadata})
        if definition.cacheable and record.status != "skipped":
            cache.save(cache_key, record)
        return record

    def _record_order(self, check_id: str, plan: CheckPlan) -> int:
        selected = {item.id: index for index, item in enumerate(plan.selected_checks)}
        if check_id in selected:
            return selected[check_id]
        return len(selected) + sorted(item.id for item in plan.skipped_checks).index(check_id)
