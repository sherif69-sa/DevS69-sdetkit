from __future__ import annotations

import json
from pathlib import Path

from scripts import phase1_retire_plan_into_flow as retire


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_retire_plan_success(tmp_path: Path) -> None:
    status = tmp_path / "status.json"
    plan = tmp_path / "plan.json"
    archive = tmp_path / "archive"
    manifest = tmp_path / "flow.json"

    _write(status, {"ok": True, "hard_blockers": []})
    _write(
        plan,
        {
            "plan_id": "x",
            "current_phase": {"id": 1, "name": "P1"},
            "phase_sequence": [
                {"id": 1, "name": "P1", "objective": "a"},
                {"id": 2, "name": "P2", "objective": "b"},
            ],
        },
    )

    out = retire.retire_phase1_plan(status, plan, archive, manifest)
    assert out["ok"] is True
    assert manifest.exists()


def test_retire_plan_fails_when_status_not_done(tmp_path: Path) -> None:
    status = tmp_path / "status.json"
    plan = tmp_path / "plan.json"
    archive = tmp_path / "archive"
    manifest = tmp_path / "flow.json"

    _write(status, {"ok": False, "hard_blockers": ["x"]})
    _write(plan, {"phase_sequence": [{"id": 1}, {"id": 2}]})

    out = retire.retire_phase1_plan(status, plan, archive, manifest)
    assert out["ok"] is False
    assert not manifest.exists()
