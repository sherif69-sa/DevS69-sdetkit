from __future__ import annotations

from ..types import CheckAction, CheckResult, MaintenanceContext
from ..utils import run_cmd

CHECK_NAME = "tests_check"


def run(ctx: MaintenanceContext) -> CheckResult:
    cmd = [ctx.python_exe, "-m", "pytest", "-q"]
    result = run_cmd(cmd, cwd=ctx.repo_root)
    rerun = None
    if result.returncode != 0:
        rerun = run_cmd(cmd, cwd=ctx.repo_root)

    final = rerun if rerun is not None else result
    ok = final.returncode == 0

    details: dict[str, object] = {
        "returncode": final.returncode,
        "stdout": final.stdout,
        "stderr": final.stderr,
    }
    if rerun is not None:
        details["first_attempt"] = {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        details["retries"] = 1

    return CheckResult(
        ok=ok,
        summary="pytest passed"
        if rerun is None
        else ("pytest passed after retry" if ok else "pytest reported failures"),
        details=details,
        actions=[
            CheckAction(
                id="run-tests",
                title="Run pytest -q",
                applied=False,
                notes="Investigate failed tests before merge"
                if not ok
                else (
                    "Initial pytest run failed but retry passed; review flaky tests."
                    if rerun is not None
                    else ""
                ),
            )
        ],
    )


CHECK_MODES = {"full"}
