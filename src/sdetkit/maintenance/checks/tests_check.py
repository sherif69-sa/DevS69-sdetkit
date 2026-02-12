from __future__ import annotations

from ..types import CheckAction, CheckResult, MaintenanceContext
from ..utils import run_cmd

CHECK_NAME = "tests_check"


def run(ctx: MaintenanceContext) -> CheckResult:
    result = run_cmd([ctx.python_exe, "-m", "pytest", "-q"], cwd=ctx.repo_root)
    ok = result.returncode == 0
    return CheckResult(
        ok=ok,
        summary="pytest passed" if ok else "pytest reported failures",
        details={
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        },
        actions=[
            CheckAction(
                id="run-tests",
                title="Run pytest -q",
                applied=False,
                notes="Investigate failed tests before merge" if not ok else "",
            )
        ],
    )


CHECK_MODES = {"full"}
