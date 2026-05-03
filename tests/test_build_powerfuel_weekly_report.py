from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_build_powerfuel_weekly_report_outputs_json_and_markdown(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    shadow = tmp_path / "shadow.json"
    out_json = tmp_path / "weekly.json"
    out_md = tmp_path / "weekly.md"
    score = tmp_path / "score.json"

    baseline.write_text(
        json.dumps(
            {
                "kpis": {
                    "workflow_count": 10,
                    "duplicate_trigger_paths": 4,
                    "first_proof_success_rate": 1.0,
                    "time_to_first_proof_median_minutes": 12.5,
                }
            }
        ),
        encoding="utf-8",
    )
    score.write_text(json.dumps({"score": 77}), encoding="utf-8")
    shadow.write_text(
        json.dumps(
            {
                "retirement_candidates": [
                    {
                        "workflow": "ci.yml",
                        "retirement_priority_score": 10,
                        "triggers": ["push", "pull_request"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "scripts/build_powerfuel_weekly_report.py",
            "--baseline",
            str(baseline),
            "--shadow-log",
            str(shadow),
            "--generated-at",
            "2026-05-03T00:00:00Z",
            "--consolidation-score",
            str(score),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["status"] == "weekly-report-published"
    assert payload["scoreboard"]["workflow_count"] == 10
    assert payload["next_retirement_batch"][0]["workflow"] == "ci.yml"
    assert payload["scoreboard"]["consolidation_readiness_score"] == 77
    assert "Powerfuel Weekly Report" in out_md.read_text(encoding="utf-8")
