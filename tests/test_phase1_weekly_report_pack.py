from __future__ import annotations

import json
from pathlib import Path

from scripts import phase1_weekly_report_pack as pack


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_build_pack_payload(tmp_path: Path) -> None:
    status = tmp_path / "status.json"
    dashboard = tmp_path / "dashboard.json"
    _write(status, {"hard_blockers": ["a", "b"]})
    _write(dashboard, {"ready_to_close": False, "next_step": "make phase1-next"})

    inputs = {
        "status": status,
        "next_actions": tmp_path / "missing-next.json",
        "ops_snapshot": tmp_path / "missing-snapshot.json",
        "completion_dashboard": dashboard,
        "baseline_summary": tmp_path / "missing-summary.json",
    }
    payload = pack.build_pack_payload(inputs)
    assert payload["hard_blocker_count"] == 2
    assert payload["ready_to_close"] is False


def test_main_writes_outputs(tmp_path: Path) -> None:
    rc = pack.main(["--out-dir", str(tmp_path / "pack"), "--format", "json"])
    assert rc == 0
    assert (tmp_path / "pack" / "phase1-weekly-pack.json").exists()
    assert (tmp_path / "pack" / "phase1-weekly-pack.md").exists()
