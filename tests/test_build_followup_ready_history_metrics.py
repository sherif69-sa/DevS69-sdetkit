from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_build_followup_ready_history_metrics(tmp_path: Path) -> None:
    followup = tmp_path / "followup-ready.json"
    followup.write_text(json.dumps({"ok": False}), encoding="utf-8")
    hist = tmp_path / "history.jsonl"
    out = tmp_path / "metrics.json"

    subprocess.run(
        [
            sys.executable,
            "scripts/build_followup_ready_history_metrics.py",
            "--followup",
            str(followup),
            "--history",
            str(hist),
            "--out",
            str(out),
        ],
        check=True,
    )

    followup.write_text(json.dumps({"ok": True}), encoding="utf-8")
    subprocess.run(
        [
            sys.executable,
            "scripts/build_followup_ready_history_metrics.py",
            "--followup",
            str(followup),
            "--history",
            str(hist),
            "--out",
            str(out),
            "--format",
            "json",
        ],
        check=True,
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["history_runs"] == 2
    assert payload["closed_incidents"] >= 1
    assert payload["median_time_to_remediate_hours"] is not None
