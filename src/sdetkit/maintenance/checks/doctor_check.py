from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

from sdetkit import doctor

from ...bools import coerce_bool
from ..types import CheckAction, CheckResult, MaintenanceContext

CHECK_NAME = "doctor_check"


def run(ctx: MaintenanceContext) -> CheckResult:
    args = ["--format", "json", "--pyproject", "--dev"]
    if ctx.mode == "full":
        args = ["--format", "json", "--all"]
    buff = io.StringIO()
    code = 0
    with redirect_stdout(buff):
        code = doctor.main(args)
    stdout = buff.getvalue().strip()
    if not stdout:
        return CheckResult(
            ok=False,
            summary="doctor returned no JSON output",
            details={"exit_code": code, "stdout": ""},
            actions=[
                CheckAction(id="doctor-run", title="Run doctor", applied=False, notes="No output")
            ],
        )
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return CheckResult(
            ok=False,
            summary="doctor output was not valid JSON",
            details={"exit_code": code, "stdout": stdout, "error": str(exc)},
            actions=[
                CheckAction(
                    id="doctor-parse",
                    title="Parse doctor output",
                    applied=False,
                    notes="Inspect doctor command output",
                )
            ],
        )
    quality = parsed.get("quality", {}) if isinstance(parsed, dict) else {}
    hints = parsed.get("hints", []) if isinstance(parsed, dict) else []
    quality_failed = int(quality.get("failed_checks", 0)) if isinstance(quality, dict) else 0
    hint_count = len(hints) if isinstance(hints, list) else 0
    summary = f"doctor score {parsed.get('score', 0)}%"
    if quality_failed or hint_count:
        summary += f" ({quality_failed} failed, {hint_count} hint(s))"

    actions = [
        CheckAction(
            id="doctor-run",
            title="Run doctor checks",
            applied=False,
            notes="Use `sdetkit doctor --all` for detailed review",
        )
    ]
    next_actions = parsed.get("next_actions", []) if isinstance(parsed, dict) else []
    if isinstance(next_actions, list):
        for item in next_actions[:3]:
            if not isinstance(item, dict):
                continue
            check_id = str(item.get("id", "")).strip() or "doctor-follow-up"
            fixes = item.get("fix", [])
            first_fix = ""
            if isinstance(fixes, list) and fixes:
                first_fix = str(fixes[0]).strip()
            title = first_fix or str(item.get("summary", "")).strip() or "Inspect doctor finding"
            if title:
                actions.append(
                    CheckAction(
                        id=f"doctor-{check_id}",
                        title=title,
                        applied=False,
                        notes=str(item.get("severity", "medium")),
                    )
                )

    return CheckResult(
        ok=coerce_bool(parsed.get("ok", False), default=False),
        summary=summary,
        details={
            "doctor": parsed,
            "exit_code": code,
            "quality": quality if isinstance(quality, dict) else {},
            "hint_samples": hints[:5] if isinstance(hints, list) else [],
            "priority_queue": parsed.get("checks", {})
            .get("upgrade_audit", {})
            .get("meta", {})
            .get("priority_queue", []),
            "risk_summary": parsed.get("checks", {})
            .get("upgrade_audit", {})
            .get("meta", {})
            .get("risk_summary", []),
            "validation_summary": parsed.get("checks", {})
            .get("upgrade_audit", {})
            .get("meta", {})
            .get("validation_summary", []),
            "hotspots": parsed.get("checks", {})
            .get("upgrade_audit", {})
            .get("meta", {})
            .get("hotspots", []),
        },
        actions=actions,
    )


CHECK_MODES = {"quick", "full"}

__all__ = ["run", "CHECK_NAME", "CHECK_MODES"]
