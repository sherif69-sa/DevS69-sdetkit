from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/first_proof_learning_db.py").resolve()


def test_first_proof_learning_db_append_and_rollup(tmp_path: Path) -> None:
    summary = tmp_path / "summary.json"
    db = tmp_path / "db.jsonl"
    rollup = tmp_path / "rollup.json"

    summary.write_text(
        json.dumps(
            {
                "ok": False,
                "decision": "NO-SHIP",
                "selected_python": "/usr/bin/python3.11",
                "failed_steps": ["gate-fast"],
                "steps": [{"name": "gate-fast", "returncode": 2}],
            }
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--summary",
            str(summary),
            "--db",
            str(db),
            "--rollup-out",
            str(rollup),
            "--format",
            "json",
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 0
    result = json.loads(proc.stdout)
    assert result["ok"] is True
    assert db.exists()
    assert rollup.exists()

    rollup_payload = json.loads(rollup.read_text(encoding="utf-8"))
    assert rollup_payload["summary"]["total_runs"] == 1
    assert rollup_payload["summary"]["no_ship_runs"] == 1
    assert isinstance(rollup_payload["adaptive_reviewer"]["actions"], list)
