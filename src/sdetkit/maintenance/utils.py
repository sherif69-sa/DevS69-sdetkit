from __future__ import annotations

import subprocess
from pathlib import Path


def run_cmd(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)
