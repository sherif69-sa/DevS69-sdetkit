from __future__ import annotations

import shutil

from ..types import CheckAction, CheckResult, MaintenanceContext
from ..utils import run_cmd

CHECK_NAME = "clean_tree_check"


def run(ctx: MaintenanceContext) -> CheckResult:
    if shutil.which("git") is None:
        return CheckResult(
            ok=False,
            summary="git is not available",
            details={"missing_tool": "git"},
            actions=[
                CheckAction(
                    id="install-git",
                    title="Install git",
                    applied=False,
                    notes="clean tree check requires git",
                )
            ],
        )
    result = run_cmd(["git", "status", "--porcelain"], cwd=ctx.repo_root)
    if result.returncode != 0:
        return CheckResult(
            ok=False,
            summary="git status failed",
            details={
                "stderr": result.stderr,
                "stdout": result.stdout,
                "returncode": result.returncode,
            },
            actions=[
                CheckAction(id="repair-git", title="Fix git state", notes="Retry after fixing repo")
            ],
        )
    dirty = [line for line in result.stdout.splitlines() if line.strip()]
    return CheckResult(
        ok=not dirty,
        summary="working tree is clean" if not dirty else "uncommitted changes detected",
        details={"entries": dirty, "count": len(dirty)},
        actions=[
            CheckAction(
                id="commit-or-stash",
                title="Commit or stash changes",
                applied=False,
                notes="clean tree is recommended for release and CI",
            )
        ],
    )


CHECK_MODES = {"quick", "full"}
