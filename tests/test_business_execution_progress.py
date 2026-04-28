from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "business_execution_progress.py"
_SPEC = importlib.util.spec_from_file_location("business_execution_progress_script", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
progress_script = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(progress_script)


def test_build_progress_tracks_completion_and_gate() -> None:
    week1 = {
        "schema_version": "sdetkit.business-execution-start.v1",
        "status": "go",
        "week_1_execution_plan": {
            "day_1": ["A", "B"],
            "day_2_3": ["C"],
            "day_4_5": ["D"],
        },
    }
    payload = progress_script.build_progress(week1, {"A", "C"})
    assert payload["task_summary"]["completed"] == 2
    assert payload["task_summary"]["total"] == 4
    assert payload["gate_decision"]["status"] == "conditional-pass"


def test_main_writes_progress_artifacts(tmp_path: Path) -> None:
    week1 = tmp_path / "week1.json"
    week1.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.business-execution-start.v1",
                "status": "needs-owner-assignment",
                "week_1_execution_plan": {"day_1": ["A"]},
            }
        ),
        encoding="utf-8",
    )
    out_json = tmp_path / "progress.json"
    out_md = tmp_path / "progress.md"
    history = tmp_path / "history.jsonl"
    rollup = tmp_path / "rollup.json"
    rc = progress_script.main(
        [
            "--week1",
            str(week1),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--history",
            str(history),
            "--history-rollup-out",
            str(rollup),
        ]
    )
    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["gate_decision"]["status"] == "conditional-pass"
    assert "Status: needs-owner-assignment" in out_md.read_text(encoding="utf-8")
    assert history.exists()
    rollup_payload = json.loads(rollup.read_text(encoding="utf-8"))
    assert rollup_payload["history_records"] == 1


def test_main_strict_owner_gate_fails_when_owners_are_unassigned(tmp_path: Path) -> None:
    week1 = tmp_path / "week1.json"
    week1.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.business-execution-start.v1",
                "status": "needs-owner-assignment",
                "week_1_execution_plan": {"day_1": ["A"]},
            }
        ),
        encoding="utf-8",
    )
    out_json = tmp_path / "progress.json"
    out_md = tmp_path / "progress.md"
    history = tmp_path / "history.jsonl"
    rollup = tmp_path / "rollup.json"
    rc = progress_script.main(
        [
            "--week1",
            str(week1),
            "--owner-gate-mode",
            "strict",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--history",
            str(history),
            "--history-rollup-out",
            str(rollup),
        ]
    )
    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["gate_decision"]["status"] == "fail"
