from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from sdetkit import cli
from sdetkit import replayable_benchmark_harness as harness


def test_compute_percentiles_empty() -> None:
    pcts = harness.compute_percentiles([])
    assert pcts["p50_seconds"] == 0.0
    assert pcts["mean_seconds"] == 0.0


def test_compute_percentiles_samples() -> None:
    samples = [0.1, 0.2, 0.3, 0.4, 0.5]
    pcts = harness.compute_percentiles(samples)
    assert pcts["min_seconds"] == 0.1
    assert pcts["max_seconds"] == 0.5
    assert pcts["p50_seconds"] == 0.3
    assert pcts["mean_seconds"] == 0.3
    assert pcts["stddev_seconds"] > 0


def test_profile_performance_basic(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_sample.py").write_text("def test_ok(): assert True\n", encoding="utf-8")

    with patch.object(harness, "_run_perf_iteration", return_value=(0.05, 0, "pass")):
        report = harness.profile_performance(tmp_path, target="tests/test_sample.py", iterations=3)

    assert report["schema_version"] == harness.PERF_SCHEMA_VERSION
    assert report["verdict"] == "PASS"
    assert report["iterations"] == 3
    assert len(report["metrics"]["samples"]) == 3
    assert report["metrics"]["p50_seconds"] == 0.05
    assert report["comparison"] is None


def test_profile_performance_with_baseline_pass(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_sample.py").write_text("def test_ok(): assert True\n", encoding="utf-8")

    baseline_file = tmp_path / "baseline.json"
    baseline_file.write_text(
        json.dumps({"metrics": {"p50_seconds": 0.05}}),
        encoding="utf-8",
    )

    with patch.object(harness, "_run_perf_iteration", return_value=(0.052, 0, "pass")):
        report = harness.profile_performance(
            tmp_path,
            target="tests/test_sample.py",
            iterations=3,
            baseline_path=baseline_file,
            max_regression_percent=15.0,
        )

    assert report["verdict"] == "PASS"
    assert report["comparison"] is not None
    assert report["comparison"]["regressed"] is False
    assert report["comparison"]["percent_change"] <= 15.0


def test_profile_performance_with_baseline_regression(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_sample.py").write_text("def test_ok(): assert True\n", encoding="utf-8")

    baseline_file = tmp_path / "baseline.json"
    baseline_file.write_text(
        json.dumps({"metrics": {"p50_seconds": 0.04}}),
        encoding="utf-8",
    )

    # 0.04 -> 0.08 is +100% regression
    with patch.object(harness, "_run_perf_iteration", return_value=(0.08, 0, "slow")):
        report = harness.profile_performance(
            tmp_path,
            target="tests/test_sample.py",
            iterations=3,
            baseline_path=baseline_file,
            max_regression_percent=15.0,
        )

    assert report["verdict"] == "REGRESSION"
    assert report["comparison"] is not None
    assert report["comparison"]["regressed"] is True
    assert report["comparison"]["percent_change"] > 15.0


def test_render_perf_markdown() -> None:
    report = {
        "verdict": "PASS",
        "target": "tests/test_api.py",
        "iterations": 3,
        "metrics": {
            "min_seconds": 0.04,
            "p50_seconds": 0.05,
            "p90_seconds": 0.06,
            "p99_seconds": 0.07,
            "max_seconds": 0.08,
            "mean_seconds": 0.055,
            "stddev_seconds": 0.01,
        },
        "comparison": {
            "baseline_p50_seconds": 0.048,
            "current_p50_seconds": 0.05,
            "delta_seconds": 0.002,
            "percent_change": 4.17,
            "threshold_percent": 15.0,
            "regressed": False,
        },
        "diagnostics": ["Slight timing jitter observed."],
    }
    md = harness.render_perf_markdown(report)
    assert "# SDETKit Performance & Latency Radar" in md
    assert "**Verdict:** `PASS`" in md
    assert "| **P50 (Median)** | `0.0500s` |" in md
    assert "### Baseline Comparison" in md
    assert "| `0.0480s` | `0.0500s` | `+0.0020s` | **+4.17%** | `+15.0%` | **PASS** |" in md
    assert "Slight timing jitter observed." in md


def test_perf_cli_main(tmp_path: Path) -> None:
    out_json = tmp_path / "perf.json"
    out_md = tmp_path / "summary.md"
    save_b = tmp_path / "golden.json"

    with patch.object(harness, "_run_perf_iteration", return_value=(0.02, 0, "ok")):
        code = harness.perf_main(
            [
                "--root",
                str(tmp_path),
                "--iterations",
                "2",
                "--format",
                "json",
                "--out",
                str(out_json),
                "--summary-out",
                str(out_md),
                "--save-baseline",
                str(save_b),
                "tests/test_mock.py",
            ]
        )

    assert code == 0
    assert out_json.is_file()
    assert out_md.is_file()
    assert save_b.is_file()

    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["schema_version"] == harness.PERF_SCHEMA_VERSION
    assert data["verdict"] == "PASS"


def test_perf_cli_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, list[str]]] = []

    def _fake_run(module_name: str, args: list[str]) -> int:
        calls.append((module_name, list(args)))
        return 0

    monkeypatch.setattr(cli, "_run_module_main", _fake_run)

    rc = cli.main(["perf", "tests/test_perf.py"])
    assert rc == 0
    assert calls == [("sdetkit.replayable_benchmark_harness", ["perf", "tests/test_perf.py"])]

    calls.clear()
    rc_verify = cli.main(["verify", "perf", "--iterations", "5"])
    assert rc_verify == 0
    assert calls == [("sdetkit.replayable_benchmark_harness", ["--iterations", "5"])]
