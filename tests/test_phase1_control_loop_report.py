from __future__ import annotations

import json
from pathlib import Path

from scripts import phase1_control_loop_report as report


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_build_control_loop_report_partial() -> None:
    payload = report.build_control_loop_report(
        plan={"current_phase": {"id": 1}},
        baseline_summary={},
        dashboard={},
        weekly_pack={},
    )
    assert payload["completion_percent"] == 20.0
    assert payload["passed_stages"] == 1


def test_main_writes_outputs(tmp_path: Path) -> None:
    plan = tmp_path / "plan.json"
    baseline = tmp_path / "baseline.json"
    dashboard = tmp_path / "dashboard.json"
    weekly = tmp_path / "weekly.json"
    out_json = tmp_path / "out" / "loop.json"
    out_md = tmp_path / "out" / "loop.md"

    _write(plan, {"current_phase": {"id": 1}})
    _write(baseline, {"checks": []})
    _write(dashboard, {"ready_to_close": False, "next_step": "make phase1-next"})
    _write(weekly, {"artifact_inventory": {}})

    rc = report.main(
        [
            "--plan",
            str(plan),
            "--baseline-summary",
            str(baseline),
            "--dashboard",
            str(dashboard),
            "--weekly-pack",
            str(weekly),
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
