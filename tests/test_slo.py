from __future__ import annotations

import json
from pathlib import Path

from sdetkit.cli import main as cli_main
from sdetkit.policy import (
    SLO_SCHEMA_VERSION,
    _calculate_p95,
    _collect_slo_inputs,
    evaluate_slo,
    render_slo_markdown,
    slo_main,
)


def test_calculate_p95_various_inputs() -> None:
    assert _calculate_p95([]) == 0.0
    assert _calculate_p95([42.5]) == 42.5
    durs = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    p95 = _calculate_p95(durs)
    assert 90.0 <= p95 <= 100.0


def test_evaluate_slo_all_met() -> None:
    data = {
        "total_runs": 100,
        "flaky_runs": 0,
        "total_gate_failures": 10,
        "false_positive_failures": 0,
        "run_durations": [15.0, 20.0, 25.0],
        "min_change_coverage_percent": 95.0,
        "max_mutation_survived_percent": 5.0,
    }
    report = evaluate_slo(data)
    assert report["schema_version"] == SLO_SCHEMA_VERSION
    assert report["verdict"] == "MET"
    assert report["summary"]["breached"] == 0
    assert report["summary"]["met"] == 5
    assert len(report["remediations"]) == 0
    flakiness_obj = report["objectives"]["flakiness_rate"]
    assert flakiness_obj["actual"] == 0.0
    assert flakiness_obj["status"] == "MET"
    assert flakiness_obj["budget_remaining_percent"] == 100.0


def test_evaluate_slo_warning_budget_depletion() -> None:
    # Target is 2.0%, actual is 1.8% -> remaining budget is 10.0% (<= 20% warning threshold)
    data = {
        "flakiness_rate": 1.8,
        "total_runs": 100,
        "flaky_runs": 1,
        "run_durations": [20.0],
    }
    report = evaluate_slo(data)
    assert report["verdict"] == "WARNING"
    assert report["objectives"]["flakiness_rate"]["status"] == "WARNING"
    assert report["objectives"]["flakiness_rate"]["budget_remaining_percent"] == 10.0
    assert len(report["remediations"]) > 0


def test_evaluate_slo_breached_threshold() -> None:
    # Target is 2.0%, actual is 3.5% -> BREACHED
    data = {
        "total_runs": 100,
        "flaky_runs": 5,
        "min_change_coverage_percent": 75.0,  # Floor target is 85% -> BREACHED
    }
    report = evaluate_slo(data)
    assert report["verdict"] == "BREACHED"
    assert report["objectives"]["flakiness_rate"]["status"] == "BREACHED"
    assert report["objectives"]["min_change_coverage_percent"]["status"] == "BREACHED"
    assert any("Flakiness rate elevated" in r for r in report["remediations"])
    assert any("Change coverage floor violated" in r for r in report["remediations"])


def test_evaluate_slo_custom_policy_override() -> None:
    data = {
        "total_runs": 50,
        "flaky_runs": 1,
    }
    custom_policy = {
        "flakiness_rate": {
            "target": 0.5,  # Stricter: <= 0.5%
        }
    }
    report = evaluate_slo(data, custom_policy)
    # 1/50 = 2.0% > 0.5% -> BREACHED
    assert report["objectives"]["flakiness_rate"]["target"] == 0.5
    assert report["objectives"]["flakiness_rate"]["status"] == "BREACHED"


def test_render_slo_markdown_formatting() -> None:
    data = {
        "total_runs": 20,
        "flaky_runs": 2,
    }
    report = evaluate_slo(data)
    md = render_slo_markdown(report)
    assert "# Continuous Reliability SLO Report:" in md
    assert "| Objective | Type | Target | Actual | Budget Remaining | Status |" in md
    assert "Pipeline Flakiness Rate" in md
    assert "Actionable Remediation Guidance" in md


def test_collect_slo_inputs_from_file_and_dir(tmp_path: Path) -> None:
    # Single file
    run_file = tmp_path / "run.json"
    run_file.write_text(json.dumps({"total_runs": 40, "flaky_runs": 2}), encoding="utf-8")
    collected = _collect_slo_inputs(tmp_path, run_file)
    assert collected["total_runs"] == 40
    assert collected["flaky_runs"] == 2

    # Directory of runs
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (runs_dir / "r1.json").write_text(
        json.dumps({"total_runs": 10, "verdict": "SHIP", "duration": 14.5}),
        encoding="utf-8",
    )
    (runs_dir / "r2.json").write_text(
        json.dumps({"total_runs": 10, "verdict": "NO_SHIP", "duration": 22.0}),
        encoding="utf-8",
    )
    collected_dir = _collect_slo_inputs(tmp_path, runs_dir)
    assert collected_dir["total_runs"] == 20
    assert collected_dir["flaky_runs"] == 1
    assert len(collected_dir["run_durations"]) == 2


def test_slo_main_json_and_file_outputs(tmp_path: Path, capsys) -> None:
    out_json = tmp_path / "report.json"
    sum_md = tmp_path / "summary.md"

    rc = slo_main(
        [
            "--repo-root",
            str(tmp_path),
            "--format",
            "json",
            "--out",
            str(out_json),
            "--summary-out",
            str(sum_md),
            "--fail-on",
            "none",
        ]
    )
    assert rc == 0
    assert out_json.is_file()
    assert sum_md.is_file()

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["schema_version"] == SLO_SCHEMA_VERSION
    assert "objectives" in payload


def test_slo_main_exit_codes(tmp_path: Path) -> None:
    run_file = tmp_path / "breached.json"
    run_file.write_text(
        json.dumps({"total_runs": 10, "flaky_runs": 5}),
        encoding="utf-8",
    )

    # With --fail-on breached -> exits 1
    rc_fail = slo_main(
        [
            "--runs",
            str(run_file),
            "--fail-on",
            "breached",
        ]
    )
    assert rc_fail == 1

    # With --fail-on none -> exits 0
    rc_pass = slo_main(
        [
            "--runs",
            str(run_file),
            "--fail-on",
            "none",
        ]
    )
    assert rc_pass == 0


def test_cli_dispatch_sdetkit_slo(tmp_path: Path, capsys) -> None:
    rc = cli_main(["slo", "--repo-root", str(tmp_path), "--format", "json", "--fail-on", "none"])
    assert rc == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["schema_version"] == SLO_SCHEMA_VERSION


def test_cli_dispatch_sdetkit_verify_slo(tmp_path: Path, capsys) -> None:
    rc = cli_main(
        ["verify", "slo", "--repo-root", str(tmp_path), "--format", "text", "--fail-on", "none"]
    )
    assert rc == 0
    captured = capsys.readouterr()
    assert "Reliability SLO Verdict:" in captured.out


def test_cli_dispatch_sdetkit_policy_slo(tmp_path: Path, capsys) -> None:
    rc = cli_main(
        ["policy", "slo", "--repo-root", str(tmp_path), "--format", "md", "--fail-on", "none"]
    )
    assert rc == 0
    captured = capsys.readouterr()
    assert "# Continuous Reliability SLO Report:" in captured.out
