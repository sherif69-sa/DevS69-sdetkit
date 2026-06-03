from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED_SCRIPT = ROOT / "scripts" / "seed_quality_baseline_summary_fixture.py"


def test_seed_phase1_baseline_summary_fixture_writes_contract_shape(tmp_path: Path) -> None:
    summary = tmp_path / "build" / "phase1-baseline" / "phase1-baseline-summary.json"

    result = subprocess.run(
        [sys.executable, str(SEED_SCRIPT), "--summary", str(summary)],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout)["seeded"] is True

    payload = json.loads(summary.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "sdetkit.phase1_baseline.v1"
    assert payload["generated_at_utc"] == "2026-04-19T00:00:00Z"
    assert payload["out_dir"] == "build/phase1-baseline"
    assert payload["ok"] is False
    assert [row["id"] for row in payload["checks"]] == [
        "doctor",
        "enterprise_contracts",
        "primary_docs_map",
        "pytest",
        "ruff",
    ]

    second = subprocess.run(
        [sys.executable, str(SEED_SCRIPT), "--summary", str(summary)],
        capture_output=True,
        check=False,
        text=True,
    )

    assert second.returncode == 0
    assert json.loads(second.stdout)["seeded"] is False


def test_phase3_quality_contract_depends_on_local_fixture() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    target_line = next(
        line
        for line in makefile.splitlines()
        if line.startswith("platform-readiness-quality-contract:")
    )

    assert "quality-baseline-summary-fixture" in target_line
    assert "quality-baseline-summary-fixture:" in makefile
