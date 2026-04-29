from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_render_first_proof_dashboard(tmp_path: Path) -> None:
    root = tmp_path / "first-proof"
    root.mkdir(parents=True)
    (root / "first-proof-summary.json").write_text(
        json.dumps({"decision": "SHIP"}), encoding="utf-8"
    )
    (root / "health-score.json").write_text(
        json.dumps({"score": 90, "decision": "GREEN"}), encoding="utf-8"
    )
    (root / "ops-bundle-contract-trend.json").write_text(
        json.dumps({"recent_pass_rate": 1.0, "branch_recent_pass_rate": 1.0}), encoding="utf-8"
    )
    (root / "execution-contract.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
    (root / "followup-ready.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
    onboarding = tmp_path / "onboarding-next.json"
    onboarding.write_text(
        json.dumps({"decision": "ADVANCE", "tasks": ["make ops-now-lite"]}), encoding="utf-8"
    )

    out_json = root / "dashboard.json"
    out_md = root / "dashboard.md"
    subprocess.run(
        [
            sys.executable,
            "scripts/render_first_proof_dashboard.py",
            "--artifact-dir",
            str(root),
            "--onboarding",
            str(onboarding),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--format",
            "json",
        ],
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["decision"] == "SHIP"
    assert payload["health_score"] == 90
    assert payload["execution_contract_ok"] is True
