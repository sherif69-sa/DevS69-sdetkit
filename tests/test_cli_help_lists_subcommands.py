from __future__ import annotations

import subprocess
import sys


def test_help_lists_doctor_patch_cassette_get_repo_dev_report_maintenance_agent_proof_docs_qa_and_weekly_review() -> None:
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
    assert "maintenance" in out
    assert "agent" in out
    assert "proof" in out
    assert "docs-qa" in out
    assert "weekly-review" in out
