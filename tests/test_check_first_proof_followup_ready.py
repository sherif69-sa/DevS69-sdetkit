from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_followup_ready_passes(tmp_path: Path) -> None:
    artifact = tmp_path / "first-proof"
    artifact.mkdir(parents=True)
    (artifact / "execution-contract.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
    (artifact / "execution-report.json").write_text("{}", encoding="utf-8")
    (artifact / "upgrade-status-line.txt").write_text("UPGRADE_STATUS ...\n", encoding="utf-8")
    onboarding = tmp_path / "onboarding-next.json"
    onboarding.write_text("{}", encoding="utf-8")

    out = artifact / "followup-ready.json"
    subprocess.run([
        sys.executable,
        "scripts/check_first_proof_followup_ready.py",
        "--artifact-dir", str(artifact),
        "--onboarding", str(onboarding),
        "--out", str(out),
        "--format", "json",
    ], check=True)

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True


def test_followup_ready_fails(tmp_path: Path) -> None:
    artifact = tmp_path / "first-proof"
    artifact.mkdir(parents=True)
    (artifact / "execution-contract.json").write_text(json.dumps({"ok": False}), encoding="utf-8")
    out = artifact / "followup-ready.json"
    proc = subprocess.run([
        sys.executable,
        "scripts/check_first_proof_followup_ready.py",
        "--artifact-dir", str(artifact),
        "--out", str(out),
    ], check=False)
    assert proc.returncode == 1
