from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .base import CheckContext, RegistrySnapshot
from .planner import CheckPlan
from .results import CheckRecord, FinalVerdict, build_final_verdict


@dataclass(frozen=True)
class CheckRunReport:
    plan: CheckPlan
    records: tuple[CheckRecord, ...]
    verdict: FinalVerdict

    def as_dict(self) -> dict[str, Any]:
        payload = self.verdict.as_dict()
        payload["plan"] = {
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
    ) -> CheckRunReport:
        ctx = CheckContext(
            repo_root=repo_root,
            out_dir=out_dir,
            env=env,
            python_executable=python_executable,
        )
        records: list[CheckRecord] = []
        completed: dict[str, CheckRecord] = {
            skipped.id: CheckRecord(
                id=skipped.id,
                title=skipped.title,
                status="skipped",
                blocking=skipped.blocking,
                reason=skipped.reason,
            )
            for skipped in plan.skipped_checks
        }
        records.extend(completed.values())

        for item in plan.selected_checks:
            blocked_by = [
                dep
                for dep in item.dependencies
                if dep in completed and completed[dep].status in {"failed", "skipped"}
            ]
            if blocked_by:
                record = CheckRecord(
                    id=item.id,
                    title=item.title,
                    status="skipped",
                    blocking=item.blocking,
                    reason=f"dependency not satisfied: {', '.join(blocked_by)}",
                    command=item.command,
                )
            else:
                definition = self._snapshot.check(item.id)
                if definition.run is None:
                    record = CheckRecord(
                        id=item.id,
                        title=item.title,
                        status="skipped",
                        blocking=item.blocking,
                        reason="check has no execution wiring yet",
                        command=item.command,
                    )
                else:
                    record = definition.run(ctx)
            completed[item.id] = record
            records.append(record)

        verdict = build_final_verdict(
            profile=plan.profile,
            checks=records,
            profile_notes="; ".join(plan.notes),
            metadata={
                "source": "sdetkit.checks.runner",
                "checks_recorded": len(records),
                "requested_profile": plan.requested_profile,
                "selected_checks": list(plan.selected_ids),
            },
        )
        return CheckRunReport(plan=plan, records=tuple(records), verdict=verdict)
