from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_build_kpi_weekly_snapshot_from_portfolio_sample(tmp_path: Path) -> None:
    portfolio = Path("docs/artifacts/portfolio-scorecard-sample-2026-04-17.json")
    out = tmp_path / "kpi-weekly.json"

    cmd = [
        sys.executable,
        "scripts/build_kpi_weekly_snapshot.py",
        "--portfolio-scorecard",
        str(portfolio),
        "--out",
        str(out),
        "--week-ending",
        "2026-04-17",
        "--program-status",
        "green",
        "--rollback-count",
        "0",
    ]
    subprocess.run(cmd, check=True)

    payload = json.loads(out.read_text())

    assert payload["schema_version"] == "1.0.0"
    assert payload["week_ending"] == "2026-04-17"
    assert payload["program_status"] == "green"

    kpis = payload["kpis"]
    assert kpis["first_time_success_onboarding_rate"]["value"] == 33.33
    assert kpis["first_time_success_onboarding_rate"]["sample_size"] == 3

    assert kpis["failed_release_gate_frequency"]["value"] == 33.33
    assert kpis["failed_release_gate_frequency"]["unit"] == "percent"

    assert kpis["rollback_rate"]["value"] == 0
    assert kpis["rollback_rate"]["unit"] == "count"

    assert kpis["median_release_decision_time"]["value"] is None
    assert kpis["mean_time_to_triage_first_failure"]["value"] is None
    assert kpis["docs_to_adoption_conversion"]["value"] is None
