from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/check_first_proof_trend_threshold.py").resolve()


def test_trend_threshold_breach_detected(tmp_path: Path) -> None:
    trend = tmp_path / "weekly-trend.json"
    out = tmp_path / "threshold.json"
    trend.write_text(
        json.dumps(
            {
                "summary": {"total_runs": 7, "ship_rate_last_7": 0.3},
                "recent_runs": [
                    {"decision": "SHIP"},
                    {"decision": "NO-SHIP"},
                    {"decision": "NO-SHIP"},
                ],
            }
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--trend",
            str(trend),
            "--out",
            str(out),
            "--min-ship-rate",
            "0.5",
            "--min-total-runs",
            "3",
            "--format",
            "json",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["breach"] is True
    assert payload["action"] == "recover-first-proof-ship-rate"


def test_trend_threshold_fail_on_breach(tmp_path: Path) -> None:
    trend = tmp_path / "weekly-trend.json"
    out = tmp_path / "threshold.json"
    trend.write_text(
        json.dumps(
            {
                "summary": {"total_runs": 7, "ship_rate_last_7": 0.3},
                "recent_runs": [
                    {"decision": "NO-SHIP"},
                    {"decision": "NO-SHIP"},
                ],
            }
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--trend",
            str(trend),
            "--out",
            str(out),
            "--min-ship-rate",
            "0.5",
            "--min-total-runs",
            "3",
            "--fail-on-breach",
            "--format",
            "json",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 1


def test_trend_threshold_watches_when_not_consecutive(tmp_path: Path) -> None:
    trend = tmp_path / "weekly-trend.json"
    out = tmp_path / "threshold.json"
    trend.write_text(
        json.dumps(
            {
                "summary": {"total_runs": 7, "ship_rate_last_7": 0.3},
                "recent_runs": [
                    {"decision": "NO-SHIP"},
                    {"decision": "SHIP"},
                    {"decision": "NO-SHIP"},
                ],
            }
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--trend",
            str(trend),
            "--out",
            str(out),
            "--min-ship-rate",
            "0.5",
            "--min-total-runs",
            "3",
            "--min-consecutive-breaches",
            "2",
            "--format",
            "json",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["breach"] is False
    assert payload["action"] == "watch-consecutive-no-ship"


def test_trend_threshold_profile_overrides_fail_on_breach(tmp_path: Path) -> None:
    trend = tmp_path / "weekly-trend.json"
    out = tmp_path / "threshold.json"
    cfg = tmp_path / "profiles.json"
    trend.write_text(
        json.dumps(
            {
                "summary": {"total_runs": 6, "ship_rate_last_7": 0.2},
                "recent_runs": [{"decision": "NO-SHIP"}, {"decision": "NO-SHIP"}],
            }
        ),
        encoding="utf-8",
    )
    cfg.write_text(
        json.dumps(
            {
                "profiles": {
                    "main": {
                        "min_ship_rate": 0.6,
                        "min_total_runs": 5,
                        "min_consecutive_breaches": 2,
                        "fail_on_breach": True,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--trend",
            str(trend),
            "--out",
            str(out),
            "--branch",
            "main",
            "--profile-config",
            str(cfg),
            "--format",
            "json",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["fail_on_breach"] is True
