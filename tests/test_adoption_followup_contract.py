from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/check_adoption_followup_contract.py").resolve()


def test_adoption_followup_contract_ok(tmp_path: Path) -> None:
    followup = tmp_path / "adoption-followup.json"
    followup.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.adoption_followup.v1",
                "fit": "high",
                "decision": "NO-SHIP",
                "next_command": "cmd-a",
                "recommendations": [
                    {"priority": "P0", "title": "A", "action": "cmd-a"},
                    {"priority": "P1", "title": "B", "action": "cmd-b"},
                ],
            }
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--followup", str(followup), "--format", "json"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["errors"] == []


def test_adoption_followup_contract_detects_priority_order_and_next_command(tmp_path: Path) -> None:
    followup = tmp_path / "adoption-followup.json"
    followup.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.adoption_followup.v1",
                "fit": "medium",
                "decision": "SHIP",
                "next_command": "wrong",
                "recommendations": [
                    {"priority": "P1", "title": "B", "action": "cmd-b"},
                    {"priority": "P0", "title": "A", "action": "cmd-a"},
                ],
            }
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--followup", str(followup), "--format", "json"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert any("sorted by priority" in row for row in payload["errors"])
    assert any("next_command must equal recommendations[0].action" in row for row in payload["errors"])
