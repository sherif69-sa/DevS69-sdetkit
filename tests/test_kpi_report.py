from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_kpi_report_builds_outputs_and_trends(tmp_path: Path) -> None:
    current = tmp_path / "current.json"
    previous = tmp_path / "previous.json"
    out_json = tmp_path / "report.json"
    out_md = tmp_path / "report.md"

    _write(
        current,
        {
            "time_to_first_success_minutes": 7.5,
            "lint_debt_count": 9,
            "type_debt_count": 2,
            "ci_cycle_minutes": 14.0,
            "release_gate_pass_rate": 1.0,
        },
    )
    _write(
        previous,
        {
            "metrics": {
                "time_to_first_success_minutes": 10.0,
                "lint_debt_count": 11,
                "type_debt_count": 4,
                "ci_cycle_minutes": 16.0,
                "release_gate_pass_rate": 0.0,
            }
        },
    )

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "kpi-report",
            "--current",
            str(current),
            "--previous",
            str(previous),
            "--week",
            "2026-04-10",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["week"] == "2026-04-10"
    assert payload["metrics"]["lint_debt_count"] == 9.0
    assert payload["trends"]["lint_debt_count"]["delta"] == -2.0
    assert payload["trends"]["release_gate_pass_rate"]["delta"] == 1.0
    markdown = out_md.read_text(encoding="utf-8")
    assert "# Release Confidence KPI Pack" in markdown
    assert "Release gate pass rate" in markdown
