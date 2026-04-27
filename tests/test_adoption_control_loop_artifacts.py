from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/check_adoption_control_loop_artifacts.py").resolve()


def test_adoption_control_loop_artifacts_ok(tmp_path: Path) -> None:
    for name in (
        "sdetkit-fit-recommendation.json",
        "gate-decision-summary.json",
        "gate-decision-summary.md",
        "adoption-followup.json",
        "adoption-followup.md",
        "adoption-followup-history-rollup.json",
    ):
        (tmp_path / name).write_text("{}", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--artifact-dir", str(tmp_path), "--format", "json"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["missing"] == []


def test_adoption_control_loop_artifacts_missing_files(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--artifact-dir", str(tmp_path), "--format", "json"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert "adoption-followup.json" in payload["missing"]
