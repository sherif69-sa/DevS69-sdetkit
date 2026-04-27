from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_ops_next_prints_prioritized_actions(tmp_path: Path) -> None:
    followup = tmp_path / "followup.json"
    followup.write_text(
        json.dumps(
            {
                "decision": "NO-SHIP",
                "next_command": "make ops-daily",
                "recommendations": [
                    {"priority": "P2", "title": "Later fix", "action": "do later"},
                    {"priority": "P0", "title": "Now fix", "action": "do now"},
                    {"priority": "P1", "title": "Soon fix", "action": "do soon"},
                ],
            }
        ),
        encoding="utf-8",
    )

    cmd = [
        sys.executable,
        "scripts/ops_next.py",
        "--followup",
        str(followup),
        "--limit",
        "2",
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)

    out = result.stdout
    assert "OPS_DECISION=NO-SHIP" in out
    assert "OPS_NEXT_COMMAND=make ops-daily" in out
    assert "1. [P0] Now fix" in out
    assert "2. [P1] Soon fix" in out


def test_ops_next_json_output(tmp_path: Path) -> None:
    followup = tmp_path / "followup.json"
    followup.write_text(
        json.dumps(
            {
                "decision": "SHIP",
                "next_command": "make ops-premerge",
                "recommendations": [
                    {"priority": "P3", "title": "Proceed", "action": "merge"},
                ],
            }
        ),
        encoding="utf-8",
    )

    cmd = [
        sys.executable,
        "scripts/ops_next.py",
        "--followup",
        str(followup),
        "--format",
        "json",
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["decision"] == "SHIP"
    assert payload["next_command"] == "make ops-premerge"
    assert payload["recommendations"][0]["priority"] == "P3"
