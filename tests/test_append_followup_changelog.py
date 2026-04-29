from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_append_followup_changelog(tmp_path: Path) -> None:
    dashboard = tmp_path / "dashboard.json"
    dashboard.write_text(json.dumps({"decision": "SHIP", "health_score": 92, "followup_ready": True}), encoding="utf-8")
    status = tmp_path / "status.txt"
    status.write_text("UPGRADE_STATUS decision=SHIP\n", encoding="utf-8")
    out = tmp_path / "changelog.jsonl"

    subprocess.run([
        sys.executable,
        "scripts/append_followup_changelog.py",
        "--dashboard", str(dashboard),
        "--status-line", str(status),
        "--out", str(out),
        "--format", "json",
    ], check=True)

    rows = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 1
    payload = json.loads(rows[0])
    assert payload["decision"] == "SHIP"
    assert payload["health_score"] == 92
