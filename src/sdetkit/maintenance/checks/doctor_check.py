from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

from sdetkit import doctor

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
    return CheckResult(
        ok=bool(parsed.get("ok", False)),
        summary=f"doctor score {parsed.get('score', 0)}%",
        details={"doctor": parsed, "exit_code": code},
        actions=[
            CheckAction(
                id="doctor-run",
                title="Run doctor checks",
                applied=False,
                notes="Use `sdetkit doctor --all` for detailed review",
            )
        ],
    )


CHECK_MODES = {"quick", "full"}
