from __future__ import annotations

import json
from pathlib import Path

from scripts import phase2_status_report


def _write_kickoff_pack(root: Path) -> None:
    (root / "evidence").mkdir(parents=True, exist_ok=True)
    (root / "phase2-kickoff-summary.json").write_text("{}", encoding="utf-8")
    (root / "phase2-kickoff-summary.md").write_text("# ok\n", encoding="utf-8")
    (root / "phase2-kickoff-delivery-board.md").write_text("# board\n", encoding="utf-8")
    (root / "phase2-kickoff-validation-commands.md").write_text("# commands\n", encoding="utf-8")
    (root / "evidence/phase2-kickoff-execution-summary.json").write_text("{}", encoding="utf-8")


def test_build_status_ok_when_summary_and_kickoff_artifacts_exist(tmp_path: Path) -> None:
    summary = tmp_path / "phase2-start-summary.json"
    summary.write_text(
        json.dumps({"schema_version": "sdetkit.phase2_start_workflow.v1", "ok": True}),
        encoding="utf-8",
    )
    kickoff = tmp_path / "kickoff-pack"
    _write_kickoff_pack(kickoff)

    payload = phase2_status_report.build_status(summary, kickoff)
    assert payload["ok"] is True
    assert payload["hard_blockers"] == []


def test_build_status_fails_when_summary_missing(tmp_path: Path) -> None:
    kickoff = tmp_path / "kickoff-pack"
    _write_kickoff_pack(kickoff)
    payload = phase2_status_report.build_status(tmp_path / "missing.json", kickoff)
    assert payload["ok"] is False
    assert any(str(item).startswith("missing_summary::") for item in payload["hard_blockers"])
