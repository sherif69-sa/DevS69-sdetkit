from __future__ import annotations

import json
from pathlib import Path

from scripts import phase1_completion_dashboard as dash


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_build_dashboard_ready_true(tmp_path: Path) -> None:
    plan = tmp_path / "plan.json"
    status = tmp_path / "status.json"
    summary = tmp_path / "summary.json"
    snapshot = tmp_path / "snapshot.json"

    _write(
        plan,
        {
            "plan_id": "p",
            "current_phase": {"id": 1, "name": "P1"},
            "phase_sequence": [{"id": 1, "name": "P1", "now_actions": ["x"]}],
            "control_loop": ["Plan"],
            "phase_handoff_rule": "rule",
        },
    )
    _write(status, {"ok": True, "accomplished": ["a"], "not_yet": [], "hard_blockers": []})
    _write(
        summary,
        {
            "checks": [
                {"id": "doctor", "ok": True},
                {"id": "enterprise_contracts", "ok": True},
                {"id": "primary_docs_map", "ok": True},
            ]
        },
    )
    _write(
        snapshot, {"progress_percent": 100, "top_risk_item": None, "recommended_next_actions": []}
    )

    out = dash.build_dashboard(plan, status, summary, snapshot)
    assert out["ready_to_close"] is True
    assert out["next_step"] == "make phase1-closeout"


def test_main_writes_outputs(tmp_path: Path) -> None:
    plan = tmp_path / "plan.json"
    status = tmp_path / "status.json"
    summary = tmp_path / "summary.json"
    snapshot = tmp_path / "snapshot.json"
    out_json = tmp_path / "out" / "dashboard.json"
    out_md = tmp_path / "out" / "dashboard.md"

    _write(
        plan,
        {
            "plan_id": "p",
            "current_phase": {"id": 1, "name": "P1"},
            "phase_sequence": [{"id": 1, "name": "P1", "now_actions": ["x"]}],
            "control_loop": ["Plan"],
            "phase_handoff_rule": "rule",
        },
    )
    _write(status, {"ok": False, "accomplished": [], "not_yet": ["x"], "hard_blockers": ["x"]})
    _write(summary, {"checks": []})
    _write(snapshot, {"progress_percent": 0, "recommended_next_actions": ["x"]})

    rc = dash.main(
        [
            "--plan",
            str(plan),
            "--status",
            str(status),
            "--summary",
            str(summary),
            "--snapshot",
            str(snapshot),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--format",
            "json",
        ]
    )
    assert rc == 0
    assert out_json.exists()
    assert out_md.exists()
