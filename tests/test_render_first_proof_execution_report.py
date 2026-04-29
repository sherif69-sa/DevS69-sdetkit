from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_render_first_proof_execution_report(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "first-proof"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "first-proof-summary.json").write_text(json.dumps({"decision": "SHIP"}), encoding="utf-8")
    (artifact_dir / "health-score.json").write_text(json.dumps({"score": 95, "decision": "GREEN"}), encoding="utf-8")
    (artifact_dir / "ops-bundle-contract-trend.json").write_text(json.dumps({"recent_pass_rate": 1.0}), encoding="utf-8")

    onboarding = tmp_path / "onboarding-next.json"
    onboarding.write_text(json.dumps({"decision": "ADVANCE", "tasks": ["make ops-now-lite"]}), encoding="utf-8")

    out_json = artifact_dir / "execution-report.json"
    out_md = artifact_dir / "execution-report.md"

    subprocess.run([
        sys.executable,
        "scripts/render_first_proof_execution_report.py",
        "--artifact-dir", str(artifact_dir),
        "--onboarding", str(onboarding),
        "--out-json", str(out_json),
        "--out-md", str(out_md),
        "--format", "json",
    ], check=True)

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["decision"] == "SHIP"
    assert payload["health_score"] == 95
    assert payload["onboarding_decision"] == "ADVANCE"
