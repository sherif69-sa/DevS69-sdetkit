from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_workflow_contract_script_runs_without_external_pythonpath() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)

    proc = subprocess.run(
        [sys.executable, "scripts/check_workflow_contract.py"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert "workflow-contract check passed" in proc.stdout
