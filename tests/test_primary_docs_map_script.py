from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_primary_docs_map_guard_reports_ok_for_repo() -> None:
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, "scripts/check_primary_docs_map.py", "--format", "json"],
        cwd=root,
        text=True,
        capture_output=True,
        env={"PYTHONPATH": str(root / "src")},
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["overall_ok"] is True
    assert payload["schema_version"] == "1"
