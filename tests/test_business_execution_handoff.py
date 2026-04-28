from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "business_execution_handoff.py"
_SPEC = importlib.util.spec_from_file_location("business_execution_handoff_script", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
handoff_script = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(handoff_script)


def test_build_handoff_includes_key_fields() -> None:
    payload = handoff_script.build_handoff(
        week1={"status": "go", "start_date": "2026-04-28"},
        progress={
            "gate_decision": {"status": "conditional-pass"},
            "task_summary": {"completion_percent": 50},
        },
        rollup={"history_records": 3, "gate_counts": {"pass": 1, "conditional-pass": 1, "fail": 1}},
        next_payload={"next_tasks": ["A"], "recommended_command": "cmd"},
    )
    assert payload["week1_status"] == "go"
    assert payload["history_records"] == 3
    assert payload["next_tasks"] == ["A"]


def test_main_writes_handoff_artifacts(tmp_path: Path) -> None:
    (tmp_path / "week1.json").write_text(
        json.dumps({"status": "go", "start_date": "2026-04-28"}), encoding="utf-8"
    )
    (tmp_path / "progress.json").write_text(
        json.dumps(
            {"gate_decision": {"status": "pass"}, "task_summary": {"completion_percent": 100}}
        ),
        encoding="utf-8",
    )
    (tmp_path / "rollup.json").write_text(
        json.dumps(
            {"history_records": 1, "gate_counts": {"pass": 1, "conditional-pass": 0, "fail": 0}}
        ),
        encoding="utf-8",
    )
    (tmp_path / "next.json").write_text(
        json.dumps({"next_tasks": [], "recommended_command": None}),
        encoding="utf-8",
    )
    out_json = tmp_path / "handoff.json"
    out_md = tmp_path / "handoff.md"
    rc = handoff_script.main(
        [
            "--week1",
            str(tmp_path / "week1.json"),
            "--progress",
            str(tmp_path / "progress.json"),
            "--rollup",
            str(tmp_path / "rollup.json"),
            "--next",
            str(tmp_path / "next.json"),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )
    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["progress_gate"] == "pass"
    assert "Business Execution Handoff Summary" in out_md.read_text(encoding="utf-8")
