from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_ops_bundle_contract_passes(tmp_path: Path) -> None:
    files = [tmp_path / "a.json", tmp_path / "b.json"]
    for f in files:
        f.write_text("{}\n", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"bundle": "first-proof-ops", "artifacts": [str(f) for f in files]}), encoding="utf-8")
    out = tmp_path / "contract.json"
    subprocess.run([
        sys.executable,
        "scripts/check_first_proof_ops_bundle_contract.py",
        "--manifest", str(manifest),
        "--out", str(out),
        "--format", "json",
    ], check=True)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True


def test_ops_bundle_contract_fails_on_missing(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"bundle": "first-proof-ops", "artifacts": [str(tmp_path / 'missing.json')]}), encoding="utf-8")
    out = tmp_path / "contract.json"
    proc = subprocess.run([
        sys.executable,
        "scripts/check_first_proof_ops_bundle_contract.py",
        "--manifest", str(manifest),
        "--out", str(out),
    ], check=False)
    assert proc.returncode == 1
