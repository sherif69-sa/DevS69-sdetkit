from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/build_first_proof_control_tower.py").resolve()


def test_control_tower_builds_outputs(tmp_path: Path) -> None:
    rollup = tmp_path / "rollup.json"
    adaptive = tmp_path / "adaptive.json"
    out_json = tmp_path / "control-tower.json"
    out_md = tmp_path / "control-tower.md"

    rollup.write_text(
        json.dumps(
            {
                "summary": {
                    "total_runs": 5,
                    "ship_rate": 0.6,
                    "top_failed_steps": [{"step": "gate-fast", "count": 2}],
                },
                "adaptive_reviewer": {"actions": ["Prioritize gate-fast fixes"]},
            }
        ),
        encoding="utf-8",
    )
    adaptive.write_text(
        json.dumps(
            {
                "summary": {
                    "ok": True,
                    "confidence_score": 88,
                    "failed_required": 0,
                    "failed_warn": 1,
                }
            }
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--first-proof-rollup",
            str(rollup),
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
