from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REQUIRED_PAYLOADS = {
    "first-proof-summary.json": {"decision": "SHIP", "ok": True},
    "health-score.json": {"score": 100, "decision": "GREEN"},
    "ops-bundle-contract.json": {"ok": True, "artifacts": []},
    "ops-bundle-contract-trend.json": {"recent_pass_rate": 1.0, "recent_runs": 1},
    "execution-report.json": {"decision": "SHIP", "health_score": 100, "next_tasks": []},
}


def test_execution_contract_passes(tmp_path: Path) -> None:
    for name, payload in REQUIRED_PAYLOADS.items():
        (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")

    out = tmp_path / "execution-contract.json"
    subprocess.run([
        sys.executable,
        "scripts/check_first_proof_execution_contract.py",
        "--artifact-dir", str(tmp_path),
        "--out", str(out),
        "--format", "json",
    ], check=True)

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True


def test_execution_contract_fails_on_missing(tmp_path: Path) -> None:
    (tmp_path / "first-proof-summary.json").write_text(json.dumps({"decision": "NO-SHIP", "ok": False}), encoding="utf-8")
    out = tmp_path / "execution-contract.json"
    proc = subprocess.run([
        sys.executable,
        "scripts/check_first_proof_execution_contract.py",
        "--artifact-dir", str(tmp_path),
        "--out", str(out),
    ], check=False)
    assert proc.returncode == 1
