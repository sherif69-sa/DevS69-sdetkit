from __future__ import annotations

import json
import subprocess
import sys


def test_optimizer_dependency_radar_opportunity_is_operator_actionable() -> None:
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

    opportunity = next(
        item for item in payload["innovation_opportunities"] if item["id"] == "dependency-radar"
    )

    assert opportunity["title"] == "Review validation-linked dependency upgrade candidates"
    assert "validation evidence" in opportunity["summary"]
    assert opportunity["commands"] == [
        "python -m sdetkit kits radar --repo-usage-tier hot-path --format json",
        "python -m sdetkit intelligence upgrade-audit --format json --used-in-repo-only --top 10",
        "python -m sdetkit agent templates run dependency-radar-worker",
    ]
    assert opportunity["acceptance_criteria"] == [
        "dependency radar payload is generated",
        "upgrade audit lists validation-linked candidates or confirms none are actionable",
        "selected upgrade candidate links back to the monthly enhancement intake",
    ]
