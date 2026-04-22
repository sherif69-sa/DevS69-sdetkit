from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import kpi_report


def test_kpi_report_helpers_cover_invalid_inputs(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    assert kpi_report._read_json(missing) is None

    bad = tmp_path / "bad.json"
    bad.write_text("{not-json", encoding="utf-8")
    assert kpi_report._read_json(bad) is None

    arr = tmp_path / "arr.json"
    arr.write_text("[1,2,3]", encoding="utf-8")
    assert kpi_report._read_json(arr) is None

    assert kpi_report._safe_float(None) is None
    assert kpi_report._safe_float("x") is None
    assert kpi_report._safe_float("2.5") == 2.5
    assert kpi_report._compute_delta(5.0, None) is None
    assert kpi_report._compute_delta(5.1234, 3.0) == 2.123


def test_kpi_report_main_writes_json_and_markdown(tmp_path: Path) -> None:
    current = tmp_path / "current.json"
    previous = tmp_path / "previous.json"
    out_json = tmp_path / "out" / "report.json"
    out_md = tmp_path / "out" / "report.md"

    current.write_text(
        json.dumps(
            {
                "time_to_first_success_minutes": 8,
                "lint_debt_count": 4,
                "type_debt_count": 2,
                "ci_cycle_minutes": 12.5,
                "release_gate_pass_rate": 0.5,
            }
        ),
        encoding="utf-8",
    )
    previous.write_text(
        json.dumps({"metrics": {"lint_debt_count": 10, "release_gate_pass_rate": 0.1}}),
        encoding="utf-8",
    )

    rc = kpi_report.main(
        [
            "--current",
            str(current),
            "--previous",
            str(previous),
            "--week",
            "2026-04-18",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )
    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["week"] == "2026-04-18"
    assert payload["trends"]["lint_debt_count"]["delta"] == -6.0
    assert "Release gate pass rate" in out_md.read_text(encoding="utf-8")


def test_kpi_report_main_rejects_invalid_current(tmp_path: Path) -> None:
    invalid = tmp_path / "missing.json"
    with pytest.raises(SystemExit, match="Invalid current KPI input"):
        kpi_report.main(["--current", str(invalid)])
