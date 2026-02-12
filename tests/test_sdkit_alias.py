from __future__ import annotations

import subprocess
import sys


def test_sdkit_module_runs_help() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "sdkit", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "usage:" in proc.stdout.lower()
