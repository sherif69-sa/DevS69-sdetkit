from __future__ import annotations

from ..types import CheckAction, CheckResult, MaintenanceContext
from ..utils import run_cmd

CHECK_NAME = "deps_check"


def run(ctx: MaintenanceContext) -> CheckResult:
    pip_check = run_cmd([ctx.python_exe, "-m", "pip", "check"], cwd=ctx.repo_root)
    deterministic_mode = str(ctx.env.get("SDETKIT_DETERMINISTIC", "")).strip() == "1"
    outdated = (
        run_cmd(
            [ctx.python_exe, "-m", "pip", "list", "--outdated", "--format=json"], cwd=ctx.repo_root
        )
        if not deterministic_mode
        else None
    )
    outdated_info: dict[str, object]
    if deterministic_mode:
        outdated_info = {
            "ok": True,
            "data": "[]",
            "note": "skipped in deterministic mode",
        }
    elif outdated is not None and outdated.returncode == 0:
        outdated_info = {"ok": True, "data": outdated.stdout}
    else:
        outdated_info = {
            "ok": False,
            "error": (outdated.stderr or outdated.stdout) if outdated is not None else "",
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
