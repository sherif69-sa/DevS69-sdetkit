from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/run_adoption_validation_suite.py").resolve()


def test_run_adoption_validation_suite_pass(tmp_path: Path) -> None:
    out = tmp_path / "summary.json"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--command", f"{sys.executable} -c \"print('ok')\"", "--out", str(out)],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0
    assert "ADOPTION_VALIDATION=PASS" in proc.stdout
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["returncode"] == 0


def test_run_adoption_validation_suite_fail(tmp_path: Path) -> None:
    out = tmp_path / "summary.json"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--command", f"{sys.executable} -c \"import sys; sys.exit(3)\"", "--out", str(out)],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 1
    assert "ADOPTION_VALIDATION=FAIL" in proc.stdout
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert payload["returncode"] == 3
