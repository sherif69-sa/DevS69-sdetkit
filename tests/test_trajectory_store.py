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


def _pr_quality_action_report() -> dict:
    return {
        "status": "safe_fix_available",
        "primary_blocker": {
            "check": "autopilot",
            "title": "Formatter drift blocked pre-commit",
            "surface": "quality",
            "code": "PRE_COMMIT_FORMAT_DRIFT",
            "impact": "pre-commit changed a deterministic formatting file.",
            "formatter_changed_files": ["tools/maintenance_autopilot.py"],
            "safe_to_auto_fix": True,
            "safe_remediation": {
                "safe_to_auto_fix": True,
                "strategy": "run_pre_commit",
                "reason": "Failure is limited to deterministic formatting or whitespace hooks.",
            },
        },
        "automation": {
            "attempted": False,
            "allowed": True,
            "reason": "diagnosis is approved for narrow mechanical safe-fix planning",
        },
        "recommended_actions": ["Run pre-commit on the affected files."],
        "proof_commands": ["python -m pre_commit run -a"],
    }


def _pr_quality_check_intelligence() -> dict:
    return {
        "checks_seen": 3,
        "failed_checks": [
            {
                "name": "autopilot",
                "safe_to_auto_fix": True,
                "surface": "quality",
                "code": "PRE_COMMIT_FORMAT_DRIFT",
                "title": "Formatter drift blocked pre-commit",
                "first_failure_line": "RuntimeError: command failed (1): python -m pre_commit run -a",
                "formatter_changed_files": ["tools/maintenance_autopilot.py"],
                "safe_remediation": {
                    "safe_to_auto_fix": True,
                    "strategy": "run_pre_commit",
                    "reason": "Failure is limited to deterministic formatting or whitespace hooks.",
                },
                "diagnosis": {
                    "code": "PRE_COMMIT_FORMAT_DRIFT",
                    "title": "Formatter drift blocked pre-commit",
                    "risk_surface": "quality",
                    "diagnosis": "pre-commit formatting drift was detected.",
                    "proof_commands": ["python -m pre_commit run -a"],
                },
            }
        ],
        "queued_checks": [],
        "startup_failures": [],
    }


def test_pr_quality_trajectory_records_capture_safe_formatter_decision() -> None:
    from sdetkit.trajectory_store import build_pr_quality_trajectory_records

    records = build_pr_quality_trajectory_records(
        action_report=_pr_quality_action_report(),
        check_intelligence=_pr_quality_check_intelligence(),
        repo="sherif69-sa/DevS69-sdetkit",
        branch="feature/pr-quality-build-trajectory-artifact",
        commit_sha="abc123",
        pr_number=1388,
    )

    assert len(records) == 1
    record = records[0]
    assert record["environment"]["source"] == "pr_quality"
    assert record["diagnosis"]["failure_class"] == "pre_commit_format_drift"
    assert record["diagnosis"]["risk_surface"] == "quality"
    assert record["decision"]["auto_fix_allowed"] is True
    assert record["decision"]["review_first"] is False
    assert record["action"] == "run_pre_commit"
    assert record["fix"]["patch_files"] == ["tools/maintenance_autopilot.py"]
    assert record["proof"]["commands"] == ["python -m pre_commit run -a"]
    assert record["final_result"] == "safe_fix_candidate"


def test_pr_quality_trajectory_cli_writes_artifact(tmp_path: Path, capsys) -> None:
    action_path = tmp_path / "action-report.json"
    intelligence_path = tmp_path / "check-intelligence.json"
    out = tmp_path / "trajectory.jsonl"
    action_path.write_text(json.dumps(_pr_quality_action_report()), encoding="utf-8")
    intelligence_path.write_text(
        json.dumps(_pr_quality_check_intelligence()),
        encoding="utf-8",
    )

    rc = main(
        [
            "--pr-quality-action-report",
            str(action_path),
            "--check-intelligence",
            str(intelligence_path),
            "--out",
            str(out),
            "--repo",
            "sherif69-sa/DevS69-sdetkit",
            "--branch",
            "feature/pr-quality-build-trajectory-artifact",
            "--commit-sha",
            "abc123",
            "--pr-number",
            "1388",
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["summary"]["record_count"] == 1
    assert printed["summary"]["auto_fix_allowed_count"] == 1
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["action"] == "run_pre_commit"


def _green_pr_quality_action_report() -> dict:
    return {
        "status": "green",
        "primary_blocker": {},
        "automation": {
            "attempted": False,
            "allowed": False,
            "reason": "no remediation needed",
        },
        "recommended_actions": [],
        "proof_commands": [],
    }


def _green_pr_quality_check_intelligence() -> dict:
    return {
        "checks_seen": 44,
        "failed_checks": [],
        "queued_checks": [],
        "startup_failures": [],
    }


def _evidence_review_narrative() -> dict:
    return {
        "quality": {"ok": True, "coverage_percent": "96.69%"},
        "primary_signal": {
            "kind": "review_signal",
            "surface": "pr_quality",
            "title": "PR Quality evidence changed",
        },
        "graph": {
            "node_count": 2,
            "review_first_count": 1,
            "critical_count": 0,
            "top_blocker": {
                "title": "PR Quality evidence changed",
                "surface": "pr_quality",
                "action": "review",
                "review_first": True,
            },
        },
        "next_proof": [
            "python -m pytest -q tests/test_pr_quality_evidence_narrative.py -o addopts=",
            "python -m pre_commit run -a",
        ],
    }


def _evidence_proof_narrative() -> dict:
    return {
        "quality": {"ok": True, "coverage_percent": "96.69%"},
        "primary_signal": {
            "kind": "review_signal",
            "surface": "pr_quality",
            "title": "PR Quality proof changed",
        },
        "graph": {
            "node_count": 2,
            "review_first_count": 0,
            "critical_count": 0,
            "top_blocker": {
                "title": "PR Quality proof changed",
                "surface": "pr_quality",
                "action": "rerun_proof",
                "review_first": False,
            },
        },
        "next_proof": ["python -m pre_commit run -a"],
    }


def test_pr_quality_trajectory_records_capture_green_evidence_review_signal() -> None:
    from sdetkit.trajectory_store import build_pr_quality_trajectory_records

    records = build_pr_quality_trajectory_records(
        action_report=_green_pr_quality_action_report(),
        check_intelligence=_green_pr_quality_check_intelligence(),
        evidence_narrative=_evidence_review_narrative(),
        repo="sherif69-sa/DevS69-sdetkit",
        branch="feature/trajectory-evidence-review-records",
        commit_sha="abc123",
        pr_number=1389,
    )

    assert len(records) == 1
    record = records[0]
    assert record["environment"]["source"] == "pr_quality"
    assert record["diagnosis"]["failure_class"] == "evidence_review_signal"
    assert record["diagnosis"]["risk_surface"] == "pr_quality"
    assert record["decision"]["review_first"] is True
    assert record["decision"]["auto_fix_allowed"] is False
    assert record["action"] == "review"
    assert record["final_result"] == "evidence_review_required"


def test_pr_quality_trajectory_records_capture_green_evidence_proof_signal() -> None:
    from sdetkit.trajectory_store import build_pr_quality_trajectory_records

    records = build_pr_quality_trajectory_records(
        action_report=_green_pr_quality_action_report(),
        check_intelligence=_green_pr_quality_check_intelligence(),
        evidence_narrative=_evidence_proof_narrative(),
        repo="sherif69-sa/DevS69-sdetkit",
        branch="feature/trajectory-evidence-review-records",
        commit_sha="abc123",
        pr_number=1389,
    )

    assert len(records) == 1
    record = records[0]
    assert record["diagnosis"]["failure_class"] == "evidence_proof_signal"
    assert record["decision"]["review_first"] is False
    assert record["decision"]["auto_fix_allowed"] is False
    assert record["action"] == "rerun_proof"
    assert record["response"]["response_type"] == "evidence_proof_signal"
    assert record["final_result"] == "proof_signal"


def test_pr_quality_trajectory_cli_writes_green_evidence_review_record(
    tmp_path: Path,
    capsys,
) -> None:
    action_path = tmp_path / "action-report.json"
    intelligence_path = tmp_path / "check-intelligence.json"
    narrative_path = tmp_path / "pr-evidence-narrative.json"
    out = tmp_path / "trajectory.jsonl"

    action_path.write_text(json.dumps(_green_pr_quality_action_report()), encoding="utf-8")
    intelligence_path.write_text(
        json.dumps(_green_pr_quality_check_intelligence()),
        encoding="utf-8",
    )
    narrative_path.write_text(json.dumps(_evidence_review_narrative()), encoding="utf-8")

    rc = main(
        [
            "--pr-quality-action-report",
            str(action_path),
            "--check-intelligence",
            str(intelligence_path),
            "--evidence-narrative",
            str(narrative_path),
            "--out",
            str(out),
            "--repo",
            "sherif69-sa/DevS69-sdetkit",
            "--branch",
            "feature/trajectory-evidence-review-records",
            "--commit-sha",
            "abc123",
            "--pr-number",
            "1389",
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["summary"]["record_count"] == 1
    assert printed["summary"]["review_first_count"] == 1
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["action"] == "review"
    assert payload["final_result"] == "evidence_review_required"


def test_pr_quality_comment_can_show_green_evidence_review_trajectory_summary() -> None:
    from sdetkit import pr_quality_action_report as report
    from sdetkit.trajectory_store import build_pr_quality_trajectory_records

    records = build_pr_quality_trajectory_records(
        action_report=_green_pr_quality_action_report(),
        check_intelligence=_green_pr_quality_check_intelligence(),
        evidence_narrative=_evidence_review_narrative(),
        repo="sherif69-sa/DevS69-sdetkit",
        branch="feature/trajectory-evidence-review-records",
        commit_sha="abc123",
        pr_number=1389,
    )

    body = report.render_comment_body(
        action_report=_green_pr_quality_action_report(),
        check_intelligence=_green_pr_quality_check_intelligence(),
        evidence_narrative=_evidence_review_narrative(),
        trajectory_records=records,
    )

    assert "SDETKit Review Result: Green with evidence review" in body
    assert "## Evidence review signal" in body
    assert "<summary><strong>Trajectory summary</strong></summary>" in body
    assert "Records: `1`" in body
    assert "Review-first decisions: `1`" in body
    assert "`evidence_review_required`=1" in body
    assert "`pr-quality-evidence-signal-evidence-review-signal`: action=`review`" in body


def test_pr_quality_trajectory_records_carry_failure_bundle_safety_evidence() -> None:
    from sdetkit.trajectory_store import build_pr_quality_trajectory_records

    records = build_pr_quality_trajectory_records(
        action_report={
            "status": "safe_fix_available",
            "automation": {
                "allowed": True,
                "reason": "safe fix planning is allowed, but not applied",
            },
            "proof_commands": ["python -m pre_commit run -a"],
        },
        check_intelligence={
            "checks_seen": 1,
            "failed_checks": [
                {
                    "name": "ruff",
                    "safe_to_auto_fix": True,
                    "review_first": False,
                    "diagnosis": {
                        "code": "RUFF_FIXABLE_LINT",
                        "title": "Ruff fixable lint can be mechanically remediated",
                    },
                }
            ],
        },
        failure_bundle={
            "out_dir": "build/pr-quality/failure-bundle",
            "report_path": "build/pr-quality/failure-bundle/failure-bundle.md",
            "safety_summary": {
                "review_first": False,
                "safe_fix_allowed": True,
                "reporting_only": True,
                "automation_allowed": False,
                "patch_application_allowed": False,
                "merge_authorized": False,
                "semantic_equivalence_proven": False,
            },
        },
        repo="sherif69-sa/DevS69-sdetkit",
        branch="feat/trajectory-safetygate-summary-evidence",
        commit_sha="abc123",
        pr_number=1607,
    )

    assert len(records) == 1
    safety_gate = records[0]["safety_gate"]
    assert safety_gate == {
        "source": "failure_bundle.safety_summary",
        "review_first": False,
        "safe_fix_allowed": True,
        "reporting_only": True,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "report_path": "build/pr-quality/failure-bundle/failure-bundle.md",
    }


def test_pr_quality_trajectory_cli_accepts_failure_bundle_artifact(tmp_path: Path, capsys) -> None:
    action_report = tmp_path / "action-report.json"
    action_report.write_text(
        json.dumps(
            {
                "status": "safe_fix_available",
                "automation": {
                    "allowed": True,
                    "reason": "safe fix planning is allowed, but not applied",
                },
                "proof_commands": ["python -m pre_commit run -a"],
            }
        ),
        encoding="utf-8",
    )
    check_intelligence = tmp_path / "check-intelligence.json"
    check_intelligence.write_text(
        json.dumps(
            {
                "checks_seen": 1,
                "failed_checks": [
                    {
                        "name": "ruff",
                        "safe_to_auto_fix": True,
                        "review_first": False,
                        "diagnosis": {"code": "RUFF_FIXABLE_LINT"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    failure_bundle = tmp_path / "failure-bundle.json"
    failure_bundle.write_text(
        json.dumps(
            {
                "manifest": {
                    "review_first": False,
                    "safe_fix_allowed": True,
                }
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "trajectory.jsonl"

    rc = main(
        [
            "--pr-quality-action-report",
            str(action_report),
            "--check-intelligence",
            str(check_intelligence),
            "--failure-bundle",
            str(failure_bundle),
            "--out",
            str(out),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["summary"]["record_count"] == 1
    record = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert record["safety_gate"]["source"] == "failure_bundle.safety_summary"
    assert record["safety_gate"]["safe_fix_allowed"] is True
    assert record["safety_gate"]["review_first"] is False
    assert record["safety_gate"]["automation_allowed"] is False
    assert record["safety_gate"]["merge_authorized"] is False
