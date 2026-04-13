from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    root = Path(__file__).resolve().parents[1]
    return subprocess.run(
        [sys.executable, "scripts/check_canonical_path_drift.py", *args],
        cwd=root,
        text=True,
        capture_output=True,
        env={"PYTHONPATH": str(root / "src")},
    )


def test_canonical_path_drift_guard_reports_ok_for_repo_state() -> None:
    proc = _run("--format", "json")
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["overall_ok"] is True
    assert payload["schema_version"] == "1"
    assert payload["checks"]["README"]["ok"] is True
