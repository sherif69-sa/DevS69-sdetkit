from __future__ import annotations

import subprocess
import sys


def test_start_session_plan_mode_runs_contract_and_pr_plan() -> None:
    proc = subprocess.run(
        [sys.executable, "scripts/start_session.py", "--size", "small"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert "scripts/check_workflow_contract.py" in proc.stdout
    assert "scripts/pr_clean.py --size small" in proc.stdout
    assert "Startup flow is clean." in proc.stdout
