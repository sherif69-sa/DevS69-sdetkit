from __future__ import annotations

import json
import subprocess
import sys


def test_pr_clean_small_plan_contains_mandatory_commands(tmp_path) -> None:
    report = tmp_path / "small-report.json"
    proc = subprocess.run(
        [sys.executable, "scripts/pr_clean.py", "--size", "small", "--report", str(report)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert "pr-clean profile: small" in proc.stdout
    assert "[lint] ruff check ." in proc.stdout
    assert "[format] ruff format --check ." in proc.stdout
    assert "[gate_fast] PYTHONPATH=src python -m sdetkit gate fast" in proc.stdout

    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["profile"] == "small"
    assert data["run"] is False
    assert data["ok"] is True


def test_pr_clean_large_plan_includes_release_quality_and_review(tmp_path) -> None:
    report = tmp_path / "large-report.json"
    proc = subprocess.run(
        [sys.executable, "scripts/pr_clean.py", "--size", "large", "--report", str(report)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert "[gate_release] PYTHONPATH=src python -m sdetkit gate release" in proc.stdout
    assert "[doctor] PYTHONPATH=src python -m sdetkit doctor" in proc.stdout
    assert "[coverage] bash quality.sh cov" in proc.stdout
    assert (
        "[review] PYTHONPATH=src python -m sdetkit review . --no-workspace --format operator-json"
        in proc.stdout
    )

    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["profile"] == "large"
    assert len(data["steps"]) == 8
