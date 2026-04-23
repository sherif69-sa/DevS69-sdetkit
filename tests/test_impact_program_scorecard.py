from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_impact_program_scorecard_builds_all_step_scores(tmp_path: Path) -> None:
    build = tmp_path / "build"
    build.mkdir(parents=True, exist_ok=True)
    _write_json(
        build / "impact-workflow-run.json",
        {
            "steps": [
                {"step": "step_1", "completion_pct": 100},
                {"step": "step_2", "completion_pct": 90},
                {"step": "step_3", "completion_pct": 80},
            ]
        },
    )
    _write_json(
        build / "impact-adaptive-review.json",
        {
            "heads": {
                "security_head": {"score": 95},
                "reliability_head": {"score": 90},
                "velocity_head": {"score": 92},
                "governance_head": {"score": 88},
                "observability_head": {"score": 85},
            }
        },
    )
    _write_json(build / "impact-criteria-report.json", {"completion_pct": 100})

    out = build / "impact-program-scorecard.json"
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/impact_program_scorecard.py",
            "--build-dir",
            str(build),
            "--out",
            str(out),
            "--format",
            "json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "sdetkit.impact-program-scorecard.v1"
    assert payload["step_scores"]["step_1"] > payload["step_scores"]["step_3"]
    assert payload["overall_score"] > 80
