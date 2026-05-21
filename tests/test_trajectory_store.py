from __future__ import annotations

import json
from pathlib import Path

from sdetkit.trajectory_store import build_trajectory_records, main, write_trajectory_records


def _diagnostic_vector() -> dict:
    return {
        "diagnoses": [
            {
                "diagnosis_id": "formatting-autopilot",
                "failure_surface": "formatting",
                "actual_failure": "ruff format..............................Failed",
                "first_failure_line": "ruff format..............................Failed",
                "safe_fix_candidate": True,
                "review_first": False,
                "recommended_next_action": "run_pre_commit",
                "affected_files": ["src/sdetkit/example.py"],
                "likely_owner_files": ["src/sdetkit/example.py"],
                "proof_commands": ["python -m pre_commit run -a"],
                "history_context": "recurring",
                "confidence": "high",
                "failure_vector": {
                    "failure_class": "formatter_only",
                    "risk_surface": "formatting",
                    "environment": "github_actions",
                    "exit_code": 1,
                    "first_failing_line": "ruff format..............................Failed",
                },
            },
            {
                "diagnosis_id": "unknown-fast-ci",
                "failure_surface": "unknown",
                "actual_failure": "Process completed with exit code 1",
                "first_failure_line": "Process completed with exit code 1",
                "safe_fix_candidate": False,
                "review_first": True,
                "proof_commands": ["collect failed check logs and rerun focused proof"],
                "failure_vector": {
                    "failure_class": "unknown",
                    "risk_surface": "unknown",
                    "environment": "github_actions",
                    "exit_code": 1,
                },
            },
        ]
    }


def _remediation_plan() -> dict:
    return {
        "plans": [
            {
                "diagnosis_id": "formatting-autopilot",
                "failure_surface": "formatting",
                "classification": "formatting_only",
                "safe_to_auto_fix": True,
                "allowed_strategy": "run_pre_commit",
                "blocked_reason": "",
                "affected_files": ["src/sdetkit/example.py"],
                "commands_to_run": ["python -m pre_commit run -a"],
                "proof_commands": ["python -m pre_commit run -a"],
                "history_context": "recurring",
            },
            {
                "diagnosis_id": "unknown-fast-ci",
                "failure_surface": "unknown",
                "classification": "unknown",
                "safe_to_auto_fix": False,
                "allowed_strategy": "collect_logs_and_classify",
                "blocked_reason": "unknown failures require fresh logs and classification",
                "affected_files": [],
                "commands_to_run": [],
                "proof_commands": ["collect failed check logs and rerun focused proof"],
                "history_context": "unknown",
            },
        ]
    }


def test_trajectory_records_capture_safe_candidate_and_review_first_decisions() -> None:
    records = build_trajectory_records(
        diagnostic_vector=_diagnostic_vector(),
        remediation_plan=_remediation_plan(),
        repo="sherif69-sa/DevS69-sdetkit",
        branch="feature/trajectory-store-records",
        commit_sha="abc123",
        pr_number=1386,
    )

    assert len(records) == 2
    formatting = records[0]
    unknown = records[1]
    assert formatting["schema_version"] == "sdetkit.trajectory.v1"
    assert formatting["decision"]["auto_fix_allowed"] is True
    assert formatting["decision"]["review_first"] is False
    assert formatting["command"] == "python -m pre_commit run -a"
    assert formatting["diagnosis"]["failure_class"] == "formatter_only"
    assert formatting["fix"]["patch_files"] == ["src/sdetkit/example.py"]
    assert formatting["final_result"] == "safe_fix_candidate"
    assert unknown["decision"]["auto_fix_allowed"] is False
    assert unknown["decision"]["review_first"] is True
    assert unknown["response"]["response_type"] == "unknown_review_required"
    assert unknown["final_result"] == "review_required"


def test_trajectory_store_writes_deterministic_jsonl(tmp_path: Path) -> None:
    records = build_trajectory_records(
        diagnostic_vector=_diagnostic_vector(),
        remediation_plan=_remediation_plan(),
        repo="sherif69-sa/DevS69-sdetkit",
        branch="feature/trajectory-store-records",
        commit_sha="abc123",
    )
    out = tmp_path / "trajectory.jsonl"

    summary = write_trajectory_records(records, out)
    first = out.read_text(encoding="utf-8")
    write_trajectory_records(records, out)
    second = out.read_text(encoding="utf-8")

    assert first == second
    assert summary["record_count"] == 2
    assert summary["auto_fix_allowed_count"] == 1
    assert summary["review_first_count"] == 1
    lines = [json.loads(line) for line in first.splitlines()]
    assert lines[0]["trajectory_id"].startswith("sherif69-sa-devs69-sdetkit")


def test_trajectory_store_cli_writes_jsonl(tmp_path: Path, capsys) -> None:
    diagnostic_path = tmp_path / "diagnostic-vector.json"
    plan_path = tmp_path / "remediation-plan.json"
    out = tmp_path / "trajectory.jsonl"
    diagnostic_path.write_text(json.dumps(_diagnostic_vector()), encoding="utf-8")
    plan_path.write_text(json.dumps(_remediation_plan()), encoding="utf-8")

    rc = main(
        [
            "--diagnostic-vector",
            str(diagnostic_path),
            "--remediation-plan",
            str(plan_path),
            "--out",
            str(out),
            "--repo",
            "sherif69-sa/DevS69-sdetkit",
            "--branch",
            "feature/trajectory-store-records",
            "--commit-sha",
            "abc123",
            "--format",
            "json",
        ]
    )

    assert rc == 0
    stdout = json.loads(capsys.readouterr().out)
    assert stdout["summary"]["record_count"] == 2
    assert stdout["summary"]["trajectory_jsonl"] == out.as_posix()
    assert len(out.read_text(encoding="utf-8").splitlines()) == 2
