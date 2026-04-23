from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_impact_step_scorecards_contains_step2_and_step3(tmp_path: Path) -> None:
    build = tmp_path / "build"
    build.mkdir(parents=True, exist_ok=True)
    _write_json(
        build / "impact-workflow-run.json",
        {
            "steps": [
                {"step": "step_1", "completion_pct": 100, "phase_readiness": {}},
                {"step": "step_2", "completion_pct": 95, "phase_readiness": {}},
                {"step": "step_3", "completion_pct": 90, "phase_readiness": {}},
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
                "governance_head": {"score": 93},
                "observability_head": {"score": 91},
            }
        },
    )
    _write_json(build / "impact-criteria-report.json", {"completion_pct": 100})

    out = build / "impact-step-scorecards.json"
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/impact_step_scorecards.py",
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
    assert payload["schema_version"] == "sdetkit.impact-step-scorecards.v1"
    assert payload["scorecards"]["step_2"]["achieved_pct"] > 90
    assert payload["scorecards"]["step_3"]["achieved_pct"] > 85
