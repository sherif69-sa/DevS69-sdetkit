from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_build_powerfuel_consolidation_score_generates_payload(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    shadow = tmp_path / "shadow.json"
    out = tmp_path / "score.json"

    baseline.write_text(json.dumps({"kpis": {"workflow_count": 50, "duplicate_trigger_paths": 60}}), encoding="utf-8")
    shadow.write_text(json.dumps({"retirement_candidates": [{"retirement_priority_score": 80}]}), encoding="utf-8")

    subprocess.run([
        sys.executable,
        "scripts/build_powerfuel_consolidation_score.py",
        "--baseline",
        str(baseline),
        "--shadow",
        str(shadow),
        "--out",
        str(out),
    ], check=True)

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "consolidation-score-generated"
    assert payload["score"] >= 0
    assert payload["priority_lane"] in {"low", "medium", "high"}
