from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_build_powerfuel_retirement_plan_creates_batch(tmp_path: Path) -> None:
    shadow = tmp_path / "shadow.json"
    out = tmp_path / "plan.json"
    shadow.write_text(
        json.dumps(
            {
                "retirement_candidates": [
                    {"workflow": "a.yml", "retirement_priority_score": 10},
                    {"workflow": "b.yml", "retirement_priority_score": 9},
                ]
            }
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "scripts/build_powerfuel_retirement_plan.py",
            "--shadow-log",
            str(shadow),
            "--batch-size",
            "1",
            "--generated-at",
            "2026-05-03T00:00:00Z",
            "--out",
            str(out),
        ],
        check=True,
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "retirement-plan-created"
    assert payload["generated_at"] == "2026-05-03T00:00:00Z"
    assert len(payload["batch"]) == 1
    assert payload["batch"][0]["workflow"] == "a.yml"
    assert payload["batch"][0]["status"] == "pending-shadow-parity"
