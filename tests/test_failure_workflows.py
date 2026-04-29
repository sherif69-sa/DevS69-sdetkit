from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)


def test_build_failure_action_plan_generates_expected_fields(tmp_path: Path) -> None:
    input_path = tmp_path / "failures.json"
    output_path = tmp_path / "plan.json"
    input_path.write_text(
        json.dumps(
            {
                "failures": [
                    {
                        "id": "ISSUE-10",
                        "priority": "P2",
                        "test_id": "tests/test_api.py::test_timeout",
                        "category": "reliability",
                        "security_impact": "low",
                        "fix_recommendation": "Tune timeout",
                    },
                    {
                        "id": "ISSUE-01",
                        "priority": "P1",
                        "test_id": "tests/test_payment.py::test_capture",
                        "category": "network-stability",
                        "security_impact": "medium",
                        "fix_recommendation": "Add idempotency",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    proc = _run(
        [
            sys.executable,
            "scripts/build_failure_action_plan.py",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        cwd=Path.cwd(),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["total_actions"] == 2
    assert payload["actions"][0]["issue_id"] == "ISSUE-01"
    assert "reproduce_command" in payload["actions"][0]
    assert "verify_command" in payload["actions"][0]


def test_failure_autofix_workflow_generates_report(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    report_path = tmp_path / "report.json"
    plan_path.write_text(
        json.dumps(
            {
                "actions": [
                    {
                        "issue_id": "ISSUE-01",
                        "priority": "P1",
                        "owner": "qa",
                        "category": "reliability",
                        "security_impact": "medium",
                        "test_id": "tests/test_api.py::test_timeout",
                        "reproduce_command": f"{sys.executable} -c \"print(\'ok\')\"",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    proc = _run(
        [
            sys.executable,
            "scripts/failure_autofix_workflow.py",
            "--plan",
            str(plan_path),
            "--report",
            str(report_path),
            "--max-actions",
            "1",
        ],
        cwd=Path.cwd(),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["executed_actions"] == 1
    assert report["results"][0]["status"] == "passed"
    assert report["results"][0]["issue_id"] == "ISSUE-01"
    assert report["results"][0]["auto_fix_suggestions"]
