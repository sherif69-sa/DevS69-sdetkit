from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/build_first_proof_weekly_trend.py").resolve()


def test_weekly_trend_builder_outputs_files(tmp_path: Path) -> None:
    db = tmp_path / "db.jsonl"
    adaptive = tmp_path / "adaptive.json"
    out_json = tmp_path / "weekly-trend.json"
    out_md = tmp_path / "weekly-trend.md"

    rows = [
        {"captured_at": "2026-04-20T10:00:00+00:00", "decision": "SHIP", "failed_steps": []},
        {
            "captured_at": "2026-04-21T10:00:00+00:00",
            "decision": "NO-SHIP",
            "failed_steps": ["gate-fast"],
        },
    ]
    db.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    adaptive.write_text(json.dumps({"summary": {"confidence_score": 77}}), encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--db",
            str(db),
            "--adaptive-postcheck",
            str(adaptive),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--format",
            "json",
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert out_json.exists()
    assert out_md.exists()

    trend = json.loads(out_json.read_text(encoding="utf-8"))
    assert trend["summary"]["total_runs"] == 2
    assert trend["summary"]["adaptive_confidence"] == 77
