#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], *, cwd: Path) -> int:
    proc = subprocess.run(cmd, cwd=cwd, check=False)
    return int(proc.returncode)


def main(argv: list[str] | None = None) -> int:
    _ = argv
    repo_root = Path(__file__).resolve().parents[1]

    checks: tuple[list[str], ...] = (
        [sys.executable, "scripts/sync_feature_registry_docs.py", "--check"],
        [sys.executable, "scripts/regenerate_real_repo_adoption_goldens.py", "--check"],
    )

    for cmd in checks:
        rc = _run(cmd, cwd=repo_root)
        if rc != 0:
            return rc

    diff_paths = [
        "docs/feature-registry.md",
        "artifacts/adoption/real-repo-golden",
    ]
    diff_cmd = ["git", "diff", "--exit-code", "--", *diff_paths]
    return _run(diff_cmd, cwd=repo_root)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
