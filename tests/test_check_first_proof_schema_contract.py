from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_schema_contract_passes(tmp_path: Path) -> None:
    for name in ["health-score.json", "ops-bundle-contract-trend.json", "execution-report.json"]:
        (tmp_path / name).write_text(json.dumps({"schema_version": "1.0.0"}), encoding="utf-8")
    out = tmp_path / "schema-contract.json"
    subprocess.run(
        [
            sys.executable,
            "scripts/check_first_proof_schema_contract.py",
            "--artifact-dir",
            str(tmp_path),
            "--out",
            str(out),
            "--format",
            "json",
        ],
        check=True,
    )


def test_schema_contract_fails(tmp_path: Path) -> None:
    (tmp_path / "health-score.json").write_text(
        json.dumps({"schema_version": "0.9.0"}), encoding="utf-8"
    )
    (tmp_path / "ops-bundle-contract-trend.json").write_text(
        json.dumps({"schema_version": "1.0.0"}), encoding="utf-8"
    )
    (tmp_path / "execution-report.json").write_text(
        json.dumps({"schema_version": "1.0.0"}), encoding="utf-8"
    )
    out = tmp_path / "schema-contract.json"
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/check_first_proof_schema_contract.py",
            "--artifact-dir",
            str(tmp_path),
            "--out",
            str(out),
        ],
        check=False,
    )
    assert proc.returncode == 1
