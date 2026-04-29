from __future__ import annotations

import shutil

from ..types import CheckAction, CheckResult, MaintenanceContext
from ..utils import run_cmd

CHECK_NAME = "clean_tree_check"
_IGNORED_PREFIXES = (
    ".sdetkit/",
    "docs/artifacts/enterprise-assessment-pack/",
    "sdet_check.json",
)


def _entry_path(entry: str) -> str:
    text = entry[3:].strip() if len(entry) > 3 else entry.strip()
    if " -> " in text:
        return text.split(" -> ", 1)[1].strip()
    return text


def _is_ignored_entry(entry: str) -> bool:
    path = _entry_path(entry)
    return any(path.startswith(prefix) for prefix in _IGNORED_PREFIXES)


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
    entries = [line for line in result.stdout.splitlines() if line.strip()]
    ignored_entries = [line for line in entries if _is_ignored_entry(line)]
    dirty = [line for line in entries if line not in ignored_entries]
    return CheckResult(
        ok=not dirty,
        summary="working tree is clean" if not dirty else "uncommitted changes detected",
        details={
            "entries": dirty,
            "count": len(dirty),
            "ignored_entries": ignored_entries,
            "ignored_count": len(ignored_entries),
        },
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

__all__ = ["run", "CHECK_NAME", "CHECK_MODES"]
