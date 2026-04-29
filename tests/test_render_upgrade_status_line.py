from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_render_upgrade_status_line(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "first-proof"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "first-proof-summary.json").write_text(json.dumps({"decision": "SHIP"}), encoding="utf-8")
    (artifact_dir / "health-score.json").write_text(json.dumps({"score": 88}), encoding="utf-8")
    (artifact_dir / "execution-contract.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
    onboarding = tmp_path / "onboarding-next.json"
    onboarding.write_text(json.dumps({"decision": "ADVANCE"}), encoding="utf-8")

    out = artifact_dir / "upgrade-status-line.txt"
    subprocess.run([
        sys.executable,
        "scripts/render_upgrade_status_line.py",
        "--artifact-dir", str(artifact_dir),
        "--onboarding", str(onboarding),
        "--out", str(out),
    ], check=True)

    line = out.read_text(encoding="utf-8")
    assert "decision=SHIP" in line
    assert "health=88" in line
    assert "contract_ok=True" in line
