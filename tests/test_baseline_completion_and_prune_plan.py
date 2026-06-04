from __future__ import annotations

import json
from pathlib import Path

from scripts import baseline_completion_and_prune_plan as workflow


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_prunes_baseline_and_advances(tmp_path: Path) -> None:
    status = tmp_path / "baseline-status.json"
    plan = tmp_path / "plan.json"
    archive = tmp_path / "archive"

    _write(status, {"ok": True, "hard_blockers": []})
    _write(
        plan,
        {
            "plan_id": "x",
            "current_phase": {"id": 1, "name": "P1"},
            "phase_sequence": [
                {"id": 1, "name": "P1", "objective": "a"},
                {"id": 2, "name": "P2", "objective": "b", "window": "Weeks 3-6"},
            ],
        },
    )

    result = workflow.baseline(status, plan, archive)
    assert result["ok"] is True

    updated = json.loads(plan.read_text(encoding="utf-8"))
    ids = [row["id"] for row in updated["phase_sequence"]]
    assert 1 not in ids
    assert updated["current_phase"]["id"] == 2
    assert updated["completed_phases"][0]["id"] == 1

    archived = list(archive.glob("baseline-completion-report-plan-snapshot-*.json"))
    assert archived


def test_fails_when_status_incomplete(tmp_path: Path) -> None:
    status = tmp_path / "baseline-status.json"
    plan = tmp_path / "plan.json"
    archive = tmp_path / "archive"

    _write(status, {"ok": False, "hard_blockers": ["required_check_ok::doctor"]})
    _write(plan, {"phase_sequence": [{"id": 1}, {"id": 2}]})

    result = workflow.baseline(status, plan, archive)
    assert result["ok"] is False
    assert "incomplete" in result["reason"]
