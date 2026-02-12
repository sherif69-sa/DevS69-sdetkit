from __future__ import annotations

import shutil

from ..types import CheckAction, CheckResult, MaintenanceContext
from ..utils import run_cmd

CHECK_NAME = "lint_check"


def run(ctx: MaintenanceContext) -> CheckResult:
    if shutil.which("ruff") is None:
        return CheckResult(
            ok=False,
            summary="ruff is not available",
            details={"missing_tool": "ruff"},
            actions=[
                CheckAction(id="install-ruff", title="Install ruff", notes="pip install ruff")
            ],
        )

    actions = [CheckAction(id="ruff-check", title="Run ruff check", applied=False, notes="")]
    if ctx.fix:
        fix_run = run_cmd([ctx.python_exe, "-m", "ruff", "check", "--fix", "."], cwd=ctx.repo_root)
        actions.append(
            CheckAction(
                id="ruff-fix",
                title="Apply `ruff check --fix`",
                applied=fix_run.returncode == 0,
                notes=(fix_run.stdout + fix_run.stderr).strip(),
            )
        )
        format_run = run_cmd([ctx.python_exe, "-m", "ruff", "format", "."], cwd=ctx.repo_root)
        actions.append(
            CheckAction(
                id="ruff-format",
                title="Apply `ruff format`",
                applied=format_run.returncode == 0,
                notes=(format_run.stdout + format_run.stderr).strip(),
            )
        )
        if shutil.which("pre-commit") is not None:
            hygiene_run = run_cmd(
                [
                    ctx.python_exe,
                    "-m",
                    "pre_commit",
                    "run",
                    "trailing-whitespace",
                    "end-of-file-fixer",
                    "-a",
                ],
                cwd=ctx.repo_root,
            )
            actions.append(
                CheckAction(
                    id="precommit-hygiene",
                    title="Apply trailing whitespace / EOF fixes",
                    applied=hygiene_run.returncode == 0,
                    notes=(hygiene_run.stdout + hygiene_run.stderr).strip(),
                )
            )

    check_run = run_cmd([ctx.python_exe, "-m", "ruff", "check", "."], cwd=ctx.repo_root)
    format_check_run = run_cmd(
        [ctx.python_exe, "-m", "ruff", "format", "--check", "."], cwd=ctx.repo_root
    )
    ok = check_run.returncode == 0 and format_check_run.returncode == 0
    details = {
        "ruff_check": {
            "returncode": check_run.returncode,
            "stdout": check_run.stdout,
            "stderr": check_run.stderr,
        },
        "ruff_format": {
            "returncode": format_check_run.returncode,
            "stdout": format_check_run.stdout,
            "stderr": format_check_run.stderr,
        },
    }
    summary = "ruff lint and format checks passed" if ok else "ruff found lint or format issues"
    return CheckResult(ok=ok, summary=summary, details=details, actions=actions)


CHECK_MODES = {"quick", "full"}
