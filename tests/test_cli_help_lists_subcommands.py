from __future__ import annotations

import subprocess
import sys


def test_help_lists_doctor_patch_cassette_get_repo_dev_and_report() -> None:
    r = subprocess.run(
        [sys.executable, "-m", "sdetkit", "--help"],
        text=True,
        capture_output=True,
    )
    assert r.returncode == 0
    out = r.stdout
    assert "kv" in out
    assert "apiget" in out
    assert "doctor" in out
    assert "patch" in out
    assert "cassette-get" in out
    assert "repo" in out
    assert "dev" in out

    assert "report" in out
