from __future__ import annotations

from ..types import CheckAction, CheckResult, MaintenanceContext
from ..utils import run_cmd

CHECK_NAME = "deps_check"


def run(ctx: MaintenanceContext) -> CheckResult:
    pip_check = run_cmd([ctx.python_exe, "-m", "pip", "check"], cwd=ctx.repo_root)
    outdated = run_cmd(
        [ctx.python_exe, "-m", "pip", "list", "--outdated", "--format=json"], cwd=ctx.repo_root
    )
    outdated_info: dict[str, object]
    if outdated.returncode == 0:
        outdated_info = {"ok": True, "data": outdated.stdout}
    else:
        outdated_info = {
            "ok": False,
            "error": outdated.stderr or outdated.stdout,
            "note": "outdated package listing is informational",
        }
    ok = pip_check.returncode == 0
    return CheckResult(
        ok=ok,
        summary="pip dependency graph is consistent"
        if ok
        else "pip check found dependency conflicts",
        details={
            "pip_check": {
                "returncode": pip_check.returncode,
                "stdout": pip_check.stdout,
                "stderr": pip_check.stderr,
            },
            "outdated": outdated_info,
        },
        actions=[
            CheckAction(
                id="pip-check",
                title="Run pip check",
                applied=False,
                notes="Resolve dependency conflicts" if not ok else "",
            )
        ],
    )


CHECK_MODES = {"quick", "full"}
