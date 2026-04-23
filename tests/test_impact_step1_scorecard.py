from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_impact_step1_scorecard_builds_achievement_metric(tmp_path: Path) -> None:
    build = tmp_path / "build"
    build.mkdir(parents=True, exist_ok=True)
    _write_json(
        build / "impact-workflow-run.json",
        {
            "steps": [
                {
                    "step": "step_1",
                    "completion_pct": 100,
                    "phase_readiness": {
                        "phase_1_security_scan_ok": True,
                        "phase_2_release_gate_ok": True,
                        "phase_alignment_ok": True,
                    },
                }
            ]
        },
    )
    _write_json(
        build / "impact-adaptive-review.json",
        {
            "heads": {
                "security_head": {"score": 90},
                "reliability_head": {"score": 95},
            }
        },
    )
    _write_json(build / "impact-criteria-report.json", {"completion_pct": 100})

    out = build / "impact-step1-scorecard.json"
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/impact_step1_scorecard.py",
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
    assert payload["schema_version"] == "sdetkit.impact-step1-scorecard.v1"
    assert payload["achieved_pct"] > 95
    assert payload["status"] == "strong"
