from __future__ import annotations

import json
import subprocess
import sys


def test_optimizer_quality_boost_is_operator_actionable() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "kits",
            "optimize",
            "repo optimization control loop",
            "--format",
            "json",
            "--limit",
            "10",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    boost = next(item for item in payload["next_boosts"] if item["id"] == "quality-boost")

    assert boost["title"] == "Strengthen first-proof quality evidence"
    assert "first-proof health" in boost["summary"]
    assert boost["commands"] == [
        "make first-proof-health-score",
        "make first-proof-dashboard",
        "make first-proof-readiness-threshold",
    ]
