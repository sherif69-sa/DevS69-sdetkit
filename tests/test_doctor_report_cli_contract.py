from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _run_sdetkit(repo_root: Path, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")
    return subprocess.run(
        [sys.executable, "-m", "sdetkit", *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_sdetkit_doctor_report_contract_json_is_review_first(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]

    proc = _run_sdetkit(
        repo_root,
        tmp_path,
        "doctor",
        "--report-contract",
        "--format",
        "json",
        "--no-workspace",
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["schema_version"] == "sdetkit.doctor_report.v1"
    assert payload["status"] == "green"
    assert payload["safety_decision"]["review_first"] is True
    assert payload["safety_decision"]["automation_allowed"] is False
    assert payload["safety_decision"]["patch_application_allowed"] is False
    assert payload["safety_decision"]["merge_authorized"] is False
    assert payload["proof_commands"] == ["python -m sdetkit doctor --all --format json"]


def test_sdetkit_doctor_report_contract_markdown_respects_out_path(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    out_path = tmp_path / "doctor-report.md"

    proc = _run_sdetkit(
        repo_root,
        tmp_path,
        "doctor",
        "--report-contract",
        "--format",
        "md",
        "--ci",
        "--out",
        str(out_path),
        "--no-workspace",
    )

    assert proc.returncode == 2
    assert proc.stderr == ""
    assert proc.stdout.startswith("# SDETKit Doctor Report")
    assert "## Safety Decision" in proc.stdout
    assert "automation_allowed: `false`" in proc.stdout
    assert "patch_application_allowed: `false`" in proc.stdout
    assert "merge_authorized: `false`" in proc.stdout
    assert out_path.read_text(encoding="utf-8") == proc.stdout
