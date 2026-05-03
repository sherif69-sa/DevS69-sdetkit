from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_build_powerfuel_baseline_generates_expected_shape(tmp_path: Path) -> None:
    workflows = tmp_path / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text(
        """
on:
  push:
  pull_request:
  workflow_dispatch:
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (workflows / "nightly.yml").write_text(
        """
on:
  workflow_dispatch:
  schedule:
""".strip()
        + "\n",
        encoding="utf-8",
    )

    first_proof = tmp_path / "first-proof-summary.json"
    first_proof.write_text(
        json.dumps({"decision": "SHIP", "duration_seconds": 1200}), encoding="utf-8"
    )
    out = tmp_path / "baseline.json"

    subprocess.run(
        [
            sys.executable,
            "scripts/build_powerfuel_baseline.py",
            "--workflows-dir",
            str(workflows),
            "--first-proof-summary",
            str(first_proof),
            "--generated-at",
            "2026-05-03T00:00:00Z",
            "--out",
            str(out),
        ],
        check=True,
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["generated_at"] == "2026-05-03T00:00:00Z"
    assert payload["kpis"]["workflow_count"] == 2
    assert payload["kpis"]["duplicate_trigger_paths"] == 1
    assert payload["kpis"]["first_proof_success_rate"] == 1.0
    assert payload["kpis"]["time_to_first_proof_median_minutes"] == 20.0
    assert payload["trigger_counts"]["workflow_dispatch"] == 2

