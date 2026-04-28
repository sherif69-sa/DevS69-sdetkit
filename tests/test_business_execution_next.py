from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "business_execution_next.py"
_SPEC = importlib.util.spec_from_file_location("business_execution_next_script", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
next_script = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(next_script)


def test_build_next_payload_selects_pending_tasks() -> None:
    progress = {
        "schema_version": "sdetkit.business-execution-progress.v1",
        "gate_decision": {"status": "conditional-pass"},
        "tasks": [
            {"task": "A", "done": True},
            {"task": "B", "done": False},
            {"task": "C", "done": False},
        ],
    }
    payload = next_script.build_next_payload(progress, limit=1)
    assert payload["pending_count"] == 2
    assert payload["next_tasks"] == ["B"]
    assert payload["recommended_command"] is not None


def test_main_writes_next_artifacts(tmp_path: Path) -> None:
    progress = tmp_path / "progress.json"
    progress.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.business-execution-progress.v1",
                "gate_decision": {"status": "fail"},
                "tasks": [{"task": "A", "done": False}],
            }
        ),
        encoding="utf-8",
    )
    out_json = tmp_path / "next.json"
    out_md = tmp_path / "next.md"
    rc = next_script.main(
        [
            "--progress",
            str(progress),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )
    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["pending_count"] == 1
    assert "Suggested next tasks" in out_md.read_text(encoding="utf-8")
