from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_impact_policy_validate_passes_for_repo_policy(tmp_path: Path) -> None:
    policy = {
        "schema_version": "sdetkit.impact-policy.v1",
        "head_regression_drop_threshold": 5.0,
        "fail_on_overall_regression": True,
        "fail_on_head_regression": True,
        "min_step_scores": {"step_1": 85, "step_2": 85, "step_3": 85},
        "min_overall_program_score": 85,
        "branch_overrides": {"main": {"min_overall_program_score": 90}},
    }
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "scripts/impact_policy_validate.py", "--policy", str(path), "--format", "json"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0


def test_impact_policy_validate_fails_for_bad_thresholds(tmp_path: Path) -> None:
    policy = {
        "schema_version": "sdetkit.impact-policy.v1",
        "head_regression_drop_threshold": 0,
        "fail_on_overall_regression": True,
        "fail_on_head_regression": True,
        "min_step_scores": {"step_1": 120, "step_2": 85, "step_3": 85},
        "min_overall_program_score": -1,
        "branch_overrides": {},
    }
    path = tmp_path / "bad-policy.json"
    path.write_text(json.dumps(policy), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "scripts/impact_policy_validate.py", "--policy", str(path)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 1
