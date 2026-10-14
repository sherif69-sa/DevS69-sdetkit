from __future__ import annotations

import json
from pathlib import Path

from sdetkit.diagnostic_job import build_diagnostic_job, run_diagnostic_worker
from sdetkit.diagnostic_worker_trajectory import (
    build_worker_trajectory_records,
    render_markdown,
    write_artifacts,
)


def _job() -> dict:
    return build_diagnostic_job(
        repo="sherif69-sa/DevS69-sdetkit",
        base_sha="base123",
        head_sha="head123",
        event_name="pull_request",
        pr_number=1904,
        input_artifacts={"diagnostic_execution_plan": "diagnostic-execution-plan.json"},
        generated_at="2026-06-28T00:00:00Z",
    )


def _check_intelligence() -> dict:
    return {
        "failed_checks": [
            {
                "name": "PR Quality local quality gate",
                "surface": "formatting",
                "command": "python -m pre_commit run -a",
                "scope": "pr_owned_only",
                "diagnosis": {
                    "title": "Pre-commit formatting drift",
                    "surface": "formatting",
                },
                "first_failure": {
                    "line": "ruff format..............................Failed",
                    "line_number": 30,
                    "tool": "ruff",
                    "kind": "format_drift",
                },
                "safe_to_auto_fix": True,
                "affected_files": ["src/sdetkit/example.py"],
            }
        ]
    }


def _execution_plan() -> dict:
    return {
        "schema_version": "sdetkit.diagnostic_execution_plan.v1",
        "plan_status": "generated",
        "repo_root": ".",
        "repo_identity": {
            "name": "DevS69-sdetkit",
            "git_detected": True,
            "remote_url": "https://github.com/sherif69-sa/DevS69-sdetkit.git",
        },
        "source_artifacts": {
            "adoption_surface": "sdetkit.adoption_surface.v1",
            "adoption_proof_recommendations": ("sdetkit.adoption_proof_recommendations.v1"),
            "adoption_repo_topology": "sdetkit.adoption_repo_topology.v1",
        },
        "summary": {
            "command_count": 1,
            "required_count": 1,
            "recommended_count": 0,
            "review_command_count": 0,
            "review_first_item_count": 0,
        },
        "commands": [
            {
                "step": 1,
                "command_id": "command-example",
                "display_command": "python -m pytest -q",
                "argv": ["python", "-m", "pytest", "-q"],
                "environment": {},
                "cwd": ".",
                "surface": "python",
                "purpose": "test",
                "operator_level": "required",
                "review_required": False,
                "review_reasons": [],
                "evidence": [
                    {
                        "source": "adoption_surface",
                        "schema_version": "sdetkit.adoption_surface.v1",
                        "paths": ["pyproject.toml"],
                    }
                ],
                "execution_allowed": False,
            }
        ],
        "review_first_items": [],
        "policies": {
            "execution_default": "deny",
            "explicit_execution_authorization_required": True,
            "workspace_mode": "isolated_copy_required",
            "source_target_used_as_command_cwd": False,
            "network_default": "deny",
            "automatic_dependency_install_allowed": False,
            "source_target_mutation_allowed": False,
        },
        "rules": {
            "plan_only": True,
            "read_only": True,
            "no_command_execution": True,
            "no_dependency_install": True,
            "no_target_repo_mutation": True,
            "no_patch_application": True,
        },
        "execution_allowed": False,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "authority_boundary": {
            "execution_allowed": False,
            "automation_allowed": False,
            "patch_application_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }


def test_trajectory_retains_execution_plan_provenance_without_execution(
    tmp_path: Path,
) -> None:
    job = _job()
    result = run_diagnostic_worker(
        job,
        check_intelligence=_check_intelligence(),
        diagnostic_execution_plan=_execution_plan(),
        out_dir=tmp_path / "worker",
    )
    vector = json.loads(
        (tmp_path / "worker" / "vector" / "diagnostic-vector.json").read_text(encoding="utf-8")
    )

    records = build_worker_trajectory_records(
        job=job,
        worker_result=result,
        diagnostic_vector=vector,
    )

    assert len(records) == 1
    handoff = records[0]["worker_evidence"]["execution_plan_handoff"]
    assert handoff["status"] == "observed"
    assert handoff["plan_schema_version"] == "sdetkit.diagnostic_execution_plan.v1"
    assert handoff["summary"]["command_count"] == 1
    assert handoff["command_evidence"][0]["command_id"] == "command-example"
    assert handoff["command_evidence"][0]["execution_allowed"] is False
    assert handoff["execution_allowed"] is False
    assert handoff["reporting_only"] is True
    assert all(value is False for value in handoff["decision_boundary"].values())
    assert records[0]["proof"]["commands"] == []

    payload = write_artifacts(
        records,
        worker_result=result,
        out_dir=tmp_path / "trajectory",
    )
    summary = payload["summary"]
    assert summary["execution_plan_handoff_count"] == 1
    assert summary["planned_command_count"] == 1
    assert summary["execution_plan_review_first_item_count"] == 0

    markdown = render_markdown(summary)
    assert "Execution-plan handoffs retained: `1`" in markdown
    assert "Planned commands retained as evidence: `1`" in markdown
    assert "Proof commands executed: `false`" in markdown


def test_trajectory_reports_zero_when_execution_plan_is_not_provided(
    tmp_path: Path,
) -> None:
    job = _job()
    result = run_diagnostic_worker(
        job,
        check_intelligence=_check_intelligence(),
        out_dir=tmp_path / "worker",
    )
    vector = json.loads(
        (tmp_path / "worker" / "vector" / "diagnostic-vector.json").read_text(encoding="utf-8")
    )
    records = build_worker_trajectory_records(
        job=job,
        worker_result=result,
        diagnostic_vector=vector,
    )

    handoff = records[0]["worker_evidence"]["execution_plan_handoff"]
    assert handoff["status"] == "not_provided"
    assert handoff["command_evidence"] == []
    assert handoff["execution_allowed"] is False

    payload = write_artifacts(
        records,
        worker_result=result,
        out_dir=tmp_path / "trajectory",
    )
    summary = payload["summary"]
    assert summary["execution_plan_handoff_count"] == 0
    assert summary["planned_command_count"] == 0
    assert summary["execution_plan_review_first_item_count"] == 0
