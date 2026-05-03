from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_build_powerfuel_shadow_log_ranks_overlap_candidates(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps(
            {
                "trigger_counts": {"push": 3, "pull_request": 2, "schedule": 1},
                "workflow_trigger_map": {
                    "ci.yml": ["push", "pull_request"],
                    "nightly.yml": ["schedule"],
                    "lint.yml": ["push"],
                },
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "shadow.json"

    subprocess.run(
        [
            sys.executable,
            "scripts/build_powerfuel_shadow_log.py",
            "--baseline",
            str(baseline),
            "--generated-at",
            "2026-05-03T00:00:00Z",
            "--out",
            str(out),
        ],
        check=True,
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "shadow-log-started"
    assert payload["generated_at"] == "2026-05-03T00:00:00Z"
    assert payload["summary"]["candidate_count"] == 3
    assert payload["retirement_candidates"][0]["workflow"] == "ci.yml"
    assert payload["retirement_candidates"][0]["retirement_priority_score"] == 3
