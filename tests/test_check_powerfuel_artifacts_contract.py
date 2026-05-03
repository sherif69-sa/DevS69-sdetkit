from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_check_powerfuel_artifacts_contract_passes(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    shadow = tmp_path / "shadow.json"
    weekly = tmp_path / "weekly.json"
    retirement = tmp_path / "retirement.json"
    out = tmp_path / "contract.json"

    baseline.write_text(json.dumps({"date": "x", "status": "x", "generated_at": "x", "kpis": {}, "trigger_counts": {}, "workflow_trigger_map": {}}), encoding="utf-8")
    shadow.write_text(json.dumps({"date": "x", "status": "x", "generated_at": "x", "summary": {}, "retirement_candidates": []}), encoding="utf-8")
    weekly.write_text(json.dumps({"date": "x", "status": "x", "generated_at": "x", "scoreboard": {}, "next_retirement_batch": []}), encoding="utf-8")
    retirement.write_text(json.dumps({"date": "x", "status": "x", "generated_at": "x", "batch": []}), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "scripts/check_powerfuel_artifacts_contract.py",
            "--baseline",
            str(baseline),
            "--shadow",
            str(shadow),
            "--weekly",
            str(weekly),
            "--retirement",
            str(retirement),
            "--out",
            str(out),
        ],
        check=True,
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert payload["checks"]["baseline"]["pass"] is True
