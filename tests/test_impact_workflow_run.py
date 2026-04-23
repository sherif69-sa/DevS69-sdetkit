from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_impact_workflow_run_dry_run_all_steps(tmp_path: Path) -> None:
    out = tmp_path / "impact-run.json"
    follow_up = tmp_path / "follow-up.md"
    next_plan = tmp_path / "next-plan.json"
    adaptive_review = tmp_path / "adaptive-review.json"
    intelligence_db = tmp_path / "impact-intelligence.db"
    criteria_report = tmp_path / "criteria-report.json"
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/impact_workflow_run.py",
            "--step",
            "all",
            "--dry-run",
            "--format",
            "json",
            "--out",
            str(out),
            "--follow-up-out",
            str(follow_up),
            "--next-plan-out",
            str(next_plan),
            "--adaptive-review-out",
            str(adaptive_review),
            "--intelligence-db",
            str(intelligence_db),
            "--criteria-out",
            str(criteria_report),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["schema_version"] == "sdetkit.impact-workflow-run.v4"
    assert follow_up.is_file()
    assert next_plan.is_file()
    assert adaptive_review.is_file()
    review_payload = json.loads(adaptive_review.read_text(encoding="utf-8"))
    assert review_payload["schema_version"] == "sdetkit.impact-adaptive-review.v1"
    criteria_payload = json.loads(criteria_report.read_text(encoding="utf-8"))
    assert criteria_payload["schema_version"] == "sdetkit.impact-criteria-report.v1"
    assert criteria_payload["ok"] is True
    assert len(review_payload["heads"]) == 5

    with sqlite3.connect(intelligence_db) as conn:
        run_count = conn.execute("SELECT COUNT(*) FROM impact_runs").fetchone()[0]
        head_count = conn.execute("SELECT COUNT(*) FROM impact_head_scores").fetchone()[0]
    assert run_count == 1
    assert head_count == 5


def test_impact_workflow_run_step1_reports_accomplishment_and_phase_readiness(
    tmp_path: Path,
) -> None:
    out = tmp_path / "impact-step1.json"
    next_plan = tmp_path / "impact-step1-next-plan.json"
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/impact_workflow_run.py",
            "--step",
            "step_1",
            "--dry-run",
            "--format",
            "json",
            "--out",
            str(out),
            "--next-plan-out",
            str(next_plan),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    step1 = payload["steps"][0]
    readiness = step1["phase_readiness"]
    assert readiness["phase_1_security_scan_ok"] is True
    assert readiness["phase_2_release_gate_ok"] is True


def test_impact_workflow_run_boost_adds_boost_results(tmp_path: Path) -> None:
    out = tmp_path / "impact-boost.json"
    next_plan = tmp_path / "impact-next-plan.json"
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/impact_workflow_run.py",
            "--step",
            "step_1",
            "--dry-run",
            "--boost",
            "--format",
            "json",
            "--out",
            str(out),
            "--next-plan-out",
            str(next_plan),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["boost"]["enabled"] is True
    next_payload = json.loads(next_plan.read_text(encoding="utf-8"))
    assert next_payload["status"] == "ready"


def test_impact_workflow_run_rejects_unknown_step() -> None:
    proc = subprocess.run(
        [sys.executable, "scripts/impact_workflow_run.py", "--step", "step_99"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 2
    assert "unknown step" in proc.stderr
