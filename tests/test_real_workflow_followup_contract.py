from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_followup_contract_check_passes_for_valid_payload(tmp_path: Path) -> None:
    followup = tmp_path / "followup.json"
    history_rollup = tmp_path / "followup-history-rollup.json"
    out = tmp_path / "followup-contract-check.json"

    followup.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.real-workflow-followup.v1",
                "generated_at": "2026-04-27T00:00:00+00:00",
                "decision": "NO-SHIP",
                "threshold_breach": False,
                "recommendations": [
                    {
                        "priority": "P1",
                        "title": "Resolve first failing step",
                        "action": "Fix gate-fast blockers",
                    }
                ],
                "next_command": "make ops-daily",
            }
        ),
        encoding="utf-8",
    )
    history_rollup.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.real-workflow-followup-history-rollup.v1",
                "generated_at": "2026-04-27T00:00:00+00:00",
                "summary": {
                    "total_runs": 1,
                    "ship_runs": 0,
                    "no_ship_runs": 1,
                    "threshold_breach_runs": 0,
                    "ship_rate": 0.0,
                    "top_recurring_recommendations": [
                        {"title": "Resolve first failing step", "count": 1}
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    cmd = [
        sys.executable,
        "scripts/check_real_workflow_followup_contract.py",
        "--followup",
        str(followup),
        "--history-rollup",
        str(history_rollup),
        "--out",
        str(out),
        "--format",
        "json",
    ]
    subprocess.run(cmd, check=True)

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["errors"] == []


def test_followup_contract_check_fails_for_invalid_payload(tmp_path: Path) -> None:
    followup = tmp_path / "followup.json"
    history_rollup = tmp_path / "followup-history-rollup.json"
    out = tmp_path / "followup-contract-check.json"

    followup.write_text(
        json.dumps(
            {
                "schema_version": "broken",
                "generated_at": "2026-04-27T00:00:00+00:00",
                "decision": "MAYBE",
                "threshold_breach": "no",
                "recommendations": [{"priority": "P9", "title": "", "action": ""}],
                "next_command": "make unknown",
            }
        ),
        encoding="utf-8",
    )
    history_rollup.write_text(
        json.dumps(
            {
                "schema_version": "broken",
                "generated_at": "2026-04-27T00:00:00+00:00",
                "summary": {"total_runs": "x"},
            }
        ),
        encoding="utf-8",
    )

    cmd = [
        sys.executable,
        "scripts/check_real_workflow_followup_contract.py",
        "--followup",
        str(followup),
        "--history-rollup",
        str(history_rollup),
        "--out",
        str(out),
    ]
    result = subprocess.run(cmd, check=False)
    assert result.returncode == 1

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert payload["errors"]
