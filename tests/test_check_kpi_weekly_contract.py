from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_check_kpi_weekly_contract_on_sample_payload(tmp_path: Path) -> None:
    schema = Path("docs/kpi-schema.v1.json")
    payload = Path("docs/artifacts/kpi-weekly-from-portfolio-2026-04-17.json")
    out = tmp_path / "kpi-contract-check.json"

    cmd = [
        sys.executable,
        "scripts/check_kpi_weekly_contract.py",
        "--schema",
        str(schema),
        "--payload",
        str(payload),
        "--out",
        str(out),
    ]
    subprocess.run(cmd, check=True)

    report = json.loads(out.read_text())
    assert report["ok"] is True
    assert report["schema_version"] == "1.0.0"
    assert report["week_ending"] == "2026-04-17"
    assert report["required_kpi_count"] == 6
