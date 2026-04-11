from __future__ import annotations

import json
import subprocess
import sys

from sdetkit.review_engine import triage_error_log


def test_triage_error_log_maps_common_failures_to_recommendations() -> None:
    sample = """
I001 [*] Import block is un-sorted or un-formatted
F401 [*] imported but unused
"""
    payload = triage_error_log(sample)
    ids = {row["id"] for row in payload["matched_rules"]}
    assert "ruff-import-order" in ids
    assert "ruff-unused-import" in ids
    assert payload["summary"]["ok"] is False


def test_review_error_assistant_json_mode_reads_stdin() -> None:
    sample = "gate: problems found\nERROR: *.whl is not a valid wheel filename.\n"
    proc = subprocess.run(
        [sys.executable, "scripts/review_error_assistant.py", "--format", "json"],
        input=sample,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 2
    payload = json.loads(proc.stdout)
    ids = {row["id"] for row in payload["matched_rules"]}
    assert "gate-problems-found" in ids
    assert "wheel-not-found" in ids
