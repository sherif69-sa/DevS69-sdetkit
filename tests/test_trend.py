from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import cli, cockpit


def test_capture_telemetry_snapshot(tmp_path: Path) -> None:
    store = tmp_path / "trends.jsonl"
    snapshot = cockpit.capture_telemetry_snapshot(
        tmp_path,
        store_path=store,
        custom_metrics={"doctor_score_pct": 100.0, "quarantine_count": 1},
    )

    assert snapshot["doctor_score_pct"] == 100.0
    assert snapshot["quarantine_count"] == 1
    assert "timestamp" in snapshot
    assert "iso_timestamp" in snapshot
    assert store.is_file()

    lines = store.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["quarantine_count"] == 1


def test_compute_trend_report_improving(tmp_path: Path) -> None:
    store = tmp_path / "trends.jsonl"

    # Snapshot 1: Older, with 3 quarantined tests and lower mutation score
    cockpit.capture_telemetry_snapshot(
        tmp_path,
        store_path=store,
        custom_metrics={
            "timestamp": 1000.0,
            "doctor_score_pct": 85.0,
            "quarantine_count": 3,
            "mutation_score_pct": 80.0,
        },
    )

    # Snapshot 2: Latest, with 0 quarantined tests and higher mutation score
    cockpit.capture_telemetry_snapshot(
        tmp_path,
        store_path=store,
        custom_metrics={
            "timestamp": 2000.0,
            "doctor_score_pct": 100.0,
            "quarantine_count": 0,
            "mutation_score_pct": 90.0,
        },
    )

    report = cockpit.compute_trend_report(tmp_path, days=0, store_path=store)

    assert report["schema_version"] == "sdetkit.trend.v1"
    assert report["snapshots_evaluated"] == 2
    assert report["velocity_direction"] == "IMPROVING"
    assert report["deltas"]["doctor_health_delta"] == 15.0
    assert report["deltas"]["quarantine_delta"] == -3
    assert report["deltas"]["mutation_score_delta"] == 10.0
    assert report["reliability_velocity_index"] >= 90.0
    assert any("Flake reduction" in i for i in report["insights"])


def test_compute_trend_report_degrading(tmp_path: Path) -> None:
    store = tmp_path / "trends.jsonl"

    # Snapshot 1: Good baseline
    cockpit.capture_telemetry_snapshot(
        tmp_path,
        store_path=store,
        custom_metrics={
            "timestamp": 1000.0,
            "doctor_score_pct": 100.0,
            "quarantine_count": 0,
            "mutation_score_pct": 90.0,
        },
    )

    # Snapshot 2: Regressed
    cockpit.capture_telemetry_snapshot(
        tmp_path,
        store_path=store,
        custom_metrics={
            "timestamp": 2000.0,
            "doctor_score_pct": 70.0,
            "quarantine_count": 5,
            "mutation_score_pct": 75.0,
        },
    )

    report = cockpit.compute_trend_report(tmp_path, days=0, store_path=store)

    assert report["velocity_direction"] == "DEGRADING"
    assert report["deltas"]["doctor_health_delta"] == -30.0
    assert report["deltas"]["quarantine_delta"] == 5
    assert report["deltas"]["mutation_score_delta"] == -15.0


def test_render_trend_markdown(tmp_path: Path) -> None:
    store = tmp_path / "trends.jsonl"
    cockpit.capture_telemetry_snapshot(tmp_path, store_path=store)

    report = cockpit.compute_trend_report(tmp_path, days=30, store_path=store)
    md = cockpit.render_trend_markdown(report)

    assert "SDETKit Release Reliability & Drift Trend Radar" in md
    assert "Reliability Velocity Index (RVI)" in md
    assert "Reliability Metric Velocity Matrix" in md


def test_trend_main_formats(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store = tmp_path / "trends.jsonl"

    # 1. Format JSON with capture
    rc = cockpit.trend_main(
        ["--root", str(tmp_path), "--store", str(store), "--capture", "--format", "json"]
    )
    assert rc == 0
    out_json = capsys.readouterr().out
    data = json.loads(out_json)
    assert data["schema_version"] == "sdetkit.trend.v1"
    assert "reliability_velocity_index" in data

    # 2. Format MD
    rc = cockpit.trend_main(["--root", str(tmp_path), "--store", str(store), "--format", "md"])
    assert rc == 0
    out_md = capsys.readouterr().out
    assert "SDETKit Release Reliability & Drift Trend Radar" in out_md

    # 3. Out file
    out_file = tmp_path / "trend_report.json"
    rc = cockpit.trend_main(
        [
            "--root",
            str(tmp_path),
            "--store",
            str(store),
            "--format",
            "json",
            "--out",
            str(out_file),
        ]
    )
    assert rc == 0
    assert out_file.exists()


def test_cli_dispatch_trend(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, list[str]]] = []

    def _fake_run(module_name: str, args: list[str]) -> int:
        calls.append((module_name, list(args)))
        return 0

    monkeypatch.setattr(cli, "_run_module_main", _fake_run)

    rc = cli.main(["trend", "--days", "14"])
    assert rc == 0
    assert calls == [("sdetkit.cockpit", ["trend", "--days", "14"])]

    calls.clear()
    rc_verify = cli.main(["verify", "trend", "--days", "7"])
    assert rc_verify == 0
    assert calls == [("sdetkit.cockpit", ["--days", "7"])]
