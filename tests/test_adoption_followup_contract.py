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


def test_adoption_followup_contract_checks_history_rollup(tmp_path: Path) -> None:
    followup = tmp_path / "adoption-followup.json"
    rollup = tmp_path / "adoption-rollup.json"
    followup.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.adoption_followup.v1",
                "fit": "low",
                "decision": "NO-DATA",
                "next_command": "cmd-a",
                "recommendations": [{"priority": "P0", "title": "A", "action": "cmd-a"}],
            }
        ),
        encoding="utf-8",
    )
    rollup.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.adoption_followup_history.v1",
                "total_runs": 1,
                "decision_counts": {"NO-DATA": 1},
                "fit_counts": {"low": 1},
                "p0_recommendation_runs": 1,
                "p0_recommendation_rate": 1.0,
                "max_consecutive_no_ship": 0,
                "escalation_recommended": False,
                "escalation_reason": "none",
                "thresholds": {
                    "escalation_consecutive_no_ship": 2,
                    "escalation_min_runs": 3,
                    "escalation_min_p0_rate": 0.5,
                },
            }
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--followup",
            str(followup),
            "--history-rollup",
            str(rollup),
            "--format",
            "json",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
