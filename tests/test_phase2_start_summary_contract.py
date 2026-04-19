from __future__ import annotations

import json
from pathlib import Path

from scripts import check_phase2_start_summary_contract as contract


def test_contract_passes_valid_summary(tmp_path: Path) -> None:
    summary = tmp_path / "phase2-start-summary.json"
    summary.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.phase2_start_workflow.v1",
                "generated_at": "2026-04-19T00:00:00Z",
                "ok": True,
                "failed_steps": [],
                "next_actions": [],
                "steps": [
                    {"command": "python -m sdetkit phase2-kickoff --strict"},
                    {"command": "python scripts/check_phase2_kickoff_contract.py"},
                    {"command": "python scripts/check_operator_essentials_contract.py --format json"},
                ],
            }
        ),
        encoding="utf-8",
    )
    rc = contract.main(["--summary", str(summary), "--format", "json"])
    assert rc == 0


def test_contract_fails_missing_required_step(tmp_path: Path) -> None:
    summary = tmp_path / "phase2-start-summary.json"
    summary.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.phase2_start_workflow.v1",
                "generated_at": "2026-04-19T00:00:00Z",
                "ok": True,
                "failed_steps": [],
                "next_actions": [],
                "steps": [
                    {"command": "python -m sdetkit phase2-kickoff --strict"},
                    {"command": "python scripts/check_phase2_kickoff_contract.py"},
                ],
            }
        ),
        encoding="utf-8",
    )
    rc = contract.main(["--summary", str(summary), "--format", "json"])
    assert rc == 1
