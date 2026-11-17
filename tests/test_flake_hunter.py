"""Tests for `sdetkit.flake_hunter` and `sdetkit verify flake` CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import flake_hunter, mcp_server


@pytest.fixture(autouse=True)
def _clean_pytest_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)


def test_compute_stats_handles_empty_and_populated() -> None:
    empty = flake_hunter._compute_stats([])
    assert empty == {"min": 0.0, "max": 0.0, "mean": 0.0, "stddev": 0.0}

    single = flake_hunter._compute_stats([1.5])
    assert single == {"min": 1.5, "max": 1.5, "mean": 1.5, "stddev": 0.0}

    multi = flake_hunter._compute_stats([1.0, 2.0, 3.0])
    assert multi["min"] == 1.0
    assert multi["max"] == 3.0
    assert multi["mean"] == 2.0
    assert multi["stddev"] > 0.0


def test_classify_cause_detects_patterns() -> None:
    assert flake_hunter._classify_cause("Connection timed out after 5000ms") == "TIMING_RACE"
    assert flake_hunter._classify_cause("asyncio.exceptions.TimeoutError") == "TIMING_RACE"
    assert flake_hunter._classify_cause("FileExistsError: already exists") == "STATE_POLLUTION"
    assert flake_hunter._classify_cause("AssertionError: 1 != 2") == "UNKNOWN"


def test_extract_failures_from_pytest_output() -> None:
    stdout = (
        "FAILED tests/test_api.py::test_connection - AssertionError\n"
        "ERROR tests/test_db.py::test_init - OperationalError\n"
    )
    found = flake_hunter._extract_failures(stdout, "")
    assert found == [
        "tests/test_api.py::test_connection",
        "tests/test_db.py::test_init",
    ]


def test_render_markdown_verdicts() -> None:
    det_md = flake_hunter.render_markdown(
        {
            "verdict": "deterministic",
            "target": "tests/test_calc.py",
            "runs_completed": 5,
            "passed_runs": 5,
            "failed_runs": 0,
            "flake_rate": 0.0,
            "duration_stats": {"min": 0.1, "max": 0.2, "mean": 0.15, "stddev": 0.03},
        }
    )
    assert "DETERMINISTIC PASS" in det_md
    assert "0.0%" in det_md

    flaky_md = flake_hunter.render_markdown(
        {
            "verdict": "flaky",
            "target": "tests/test_calc.py",
            "runs_completed": 5,
            "passed_runs": 3,
            "failed_runs": 2,
            "flake_rate": 40.0,
            "duration_stats": {"min": 0.1, "max": 0.5, "mean": 0.25, "stddev": 0.1},
            "flaky_tests": ["tests/test_calc.py::test_race"],
            "failures": [
                {
                    "run": 2,
                    "cause": "TIMING_RACE",
                    "error_snippet": "Timed out waiting for response",
                }
            ],
        }
    )
    assert "FLAKY (PROVEN NON-DETERMINISTIC)" in flaky_md
    assert "40.0%" in flaky_md
    assert "tests/test_calc.py::test_race" in flaky_md
    assert "TIMING_RACE" in flaky_md


def test_hunt_flakes_deterministic(tmp_path: Path) -> None:
    test_file = tmp_path / "test_ok.py"
    test_file.write_text("def test_pure(): assert 2 + 2 == 4\n", encoding="utf-8")

    result = flake_hunter.hunt_flakes(
        root=tmp_path,
        target=test_file,
        runs=3,
        shuffle=True,
    )
    assert result["ok"] is True
    assert result["verdict"] == "deterministic"
    assert result["runs_completed"] == 3
    assert result["passed_runs"] == 3
    assert result["failed_runs"] == 0
    assert result["flake_rate"] == 0.0


def test_hunt_flakes_proven_flaky(tmp_path: Path) -> None:
    # A test that toggles state in a temporary counter file to simulate a flaky test
    counter_file = tmp_path / "counter.txt"
    test_code = (
        "from pathlib import Path\n"
        f"p = Path({repr(str(counter_file))})\n"
        "def test_flaky():\n"
        "    count = int(p.read_text()) if p.is_file() else 0\n"
        "    p.write_text(str(count + 1))\n"
        "    # Fails on even iterations, passes on odd iterations\n"
        "    assert count % 2 == 0\n"
    )
    test_file = tmp_path / "test_flaky.py"
    test_file.write_text(test_code, encoding="utf-8")

    result = flake_hunter.hunt_flakes(
        root=tmp_path,
        target=test_file,
        runs=4,
        shuffle=False,
    )
    assert result["ok"] is False
    assert result["verdict"] == "flaky"
    assert result["passed_runs"] > 0
    assert result["failed_runs"] > 0
    assert 0.0 < result["flake_rate"] < 100.0
    assert len(result["flaky_tests"]) > 0


def test_hunt_flakes_consistently_broken(tmp_path: Path) -> None:
    test_file = tmp_path / "test_broken.py"
    test_file.write_text("def test_fail(): assert False\n", encoding="utf-8")

    result = flake_hunter.hunt_flakes(
        root=tmp_path,
        target=test_file,
        runs=3,
    )
    assert result["ok"] is False
    assert result["verdict"] == "broken"
    assert result["passed_runs"] == 0
    assert result["failed_runs"] == 3
    assert result["flake_rate"] == 100.0


def test_cli_main_with_json_and_out(tmp_path: Path) -> None:
    test_file = tmp_path / "test_sample.py"
    test_file.write_text("def test_ok(): pass\n", encoding="utf-8")
    out_file = tmp_path / "flake_report.json"

    rc = flake_hunter.main(
        [
            str(test_file),
            "--repo-root",
            str(tmp_path),
            "--runs",
            "2",
            "--format",
            "json",
            "--out",
            str(out_file),
        ]
    )
    assert rc == 0
    assert out_file.is_file()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["verdict"] == "deterministic"
    assert data["runs_completed"] == 2


def test_mcp_hunt_flakes_tool(tmp_path: Path) -> None:
    test_file = tmp_path / "test_simple.py"
    test_file.write_text("def test_add(): assert 1 + 1 == 2\n", encoding="utf-8")

    tool_res = mcp_server.hunt_flakes_tool(
        {"repo_root": str(tmp_path), "target": str(test_file), "runs": 2},
        cwd=tmp_path,
        timeout=30,
    )
    assert tool_res["error"] is False
    assert tool_res["structured"]["verdict"] == "deterministic"
    assert "DETERMINISTIC PASS" in tool_res["text"]


def test_mcp_hunt_flakes_tool_invalid_runs(tmp_path: Path) -> None:
    with pytest.raises(mcp_server.ToolError, match="runs must be an integer between 2 and 100"):
        mcp_server.hunt_flakes_tool(
            {"repo_root": str(tmp_path), "runs": 1},
            cwd=tmp_path,
            timeout=30,
        )
