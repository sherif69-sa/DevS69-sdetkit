from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "business_execution_continue.py"
_SPEC = importlib.util.spec_from_file_location("business_execution_continue_script", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
continue_script = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(continue_script)


def test_build_continue_payload_prefers_checkpoint_when_due() -> None:
    followup = {
        "checkpoint_status": "due",
        "keep_moving": True,
        "recommended_command": "python scripts/business_execution_progress.py --done \"Task A\"",
        "checkpoint_command": "make business-execution-followup",
    }
    payload = continue_script.build_continue_payload(followup)
    assert payload["selected_command"] == "make business-execution-followup"
    assert payload["should_run_now"] is True


def test_main_writes_continue_artifacts(tmp_path: Path) -> None:
    followup = tmp_path / "followup.json"
    out_json = tmp_path / "continue.json"
    out_md = tmp_path / "continue.md"
    followup.write_text(
        json.dumps(
            {
                "checkpoint_status": "on-track",
                "keep_moving": True,
                "recommended_command": "python scripts/business_execution_progress.py --done \"Task A\"",
                "checkpoint_command": "make business-execution-followup",
            }
        ),
        encoding="utf-8",
    )
    rc = continue_script.main(
        [
            "--followup",
            str(followup),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )
    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["should_run_now"] is True
    assert out_md.exists()
