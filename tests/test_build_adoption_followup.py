from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/build_adoption_followup.py").resolve()


def test_build_adoption_followup_with_missing_inputs(tmp_path: Path) -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--fit",
            str(tmp_path / "missing-fit.json"),
            "--summary",
            str(tmp_path / "missing-summary.json"),
            "--format",
            "json",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["fit"] == "unknown"
    assert payload["decision"] == "NO-DATA"
    assert any("fit recommendation" in row["title"].lower() for row in payload["recommendations"])


def test_build_adoption_followup_no_ship_adds_remediation(tmp_path: Path) -> None:
    fit = tmp_path / "fit.json"
    summary = tmp_path / "summary.json"
    fit.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.fit_recommendation.v1",
                "fit": "high",
                "score": 16,
                "next_steps": ["step-a"],
            }
        ),
        encoding="utf-8",
    )
    summary.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.gate_decision_summary.v1",
                "decision": "NO-SHIP",
                "validation_errors": [],
            }
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--fit",
            str(fit),
            "--summary",
            str(summary),
            "--format",
            "json",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["fit"] == "high"
    assert payload["decision"] == "NO-SHIP"
    assert any("remediate first failing release step" in row["title"].lower() for row in payload["recommendations"])
