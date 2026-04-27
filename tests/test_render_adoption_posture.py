from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/render_adoption_posture.py").resolve()


def test_render_adoption_posture_escalate(tmp_path: Path) -> None:
    followup = tmp_path / "followup.json"
    rollup = tmp_path / "rollup.json"
    followup.write_text(
        json.dumps({"fit": "high", "decision": "NO-SHIP", "next_command": "cmd-a"}),
        encoding="utf-8",
    )
    rollup.write_text(
        json.dumps({"total_runs": 5, "escalation_recommended": True, "escalation_reason": "consecutive_no_ship"}),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--followup", str(followup), "--rollup", str(rollup), "--format", "json"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["posture_level"] == "escalate"
    assert payload["escalation_recommended"] is True


def test_render_adoption_posture_stable_markdown(tmp_path: Path) -> None:
    followup = tmp_path / "followup.json"
    rollup = tmp_path / "rollup.json"
    followup.write_text(
        json.dumps({"fit": "medium", "decision": "SHIP", "next_command": "cmd-b"}),
        encoding="utf-8",
    )
    rollup.write_text(
        json.dumps({"total_runs": 2, "escalation_recommended": False, "escalation_reason": "none"}),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--followup", str(followup), "--rollup", str(rollup), "--format", "md"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0
    assert "- Posture level: `stable`" in proc.stdout
