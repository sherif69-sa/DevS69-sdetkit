from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_impact_trend_alert_flags_regression(tmp_path: Path) -> None:
    db = tmp_path / "impact-intelligence.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE impact_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, overall_score REAL)"
        )
        conn.execute(
            "CREATE TABLE impact_head_scores (run_id INTEGER, head TEXT, score REAL, rationale TEXT)"
        )
        conn.execute("INSERT INTO impact_runs (overall_score) VALUES (90)")
        conn.execute("INSERT INTO impact_runs (overall_score) VALUES (80)")
        conn.execute("INSERT INTO impact_runs (overall_score) VALUES (70)")

    out = tmp_path / "impact-trend-alert.json"
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/impact_trend_alert.py",
            "--db-path",
            str(db),
            "--out",
            str(out),
            "--format",
            "json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 1
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "sdetkit.impact-trend-alert.v2"
    assert payload["streak"] == "regressing"
    assert payload["ok"] is False


def test_impact_trend_alert_flags_head_regression(tmp_path: Path) -> None:
    db = tmp_path / "impact-intelligence.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE impact_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, overall_score REAL)"
        )
        conn.execute(
            "CREATE TABLE impact_head_scores (run_id INTEGER, head TEXT, score REAL, rationale TEXT)"
        )
        conn.execute("INSERT INTO impact_runs (overall_score) VALUES (80)")
        conn.execute("INSERT INTO impact_runs (overall_score) VALUES (80)")
        conn.execute(
            "INSERT INTO impact_head_scores (run_id, head, score, rationale) VALUES (1, 'security_head', 90, 'x')"
        )
        conn.execute(
            "INSERT INTO impact_head_scores (run_id, head, score, rationale) VALUES (2, 'security_head', 70, 'x')"
        )

    out = tmp_path / "impact-trend-alert.json"
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/impact_trend_alert.py",
            "--db-path",
            str(db),
            "--out",
            str(out),
            "--format",
            "json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 1
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["streak"] == "insufficient-data"
    assert payload["head_alerts"][0]["head"] == "security_head"
