from __future__ import annotations

import json

from sdetkit.doctor_report import (
    SCHEMA_VERSION,
    build_doctor_report_contract,
    render_doctor_report_markdown,
    write_doctor_report_contract,
)


def test_doctor_report_contract_prioritizes_blocking_findings() -> None:
    payload = {
        "ok": False,
        "score": 64,
        "quality": {
            "selected_checks": 4,
            "actionable_checks": 3,
            "passed_checks": 1,
            "failed_checks": 2,
            "skipped_checks": 1,
            "evidence_count": 2,
        },
        "next_actions": [
            {
                "id": "pre_commit",
                "severity": "medium",
                "summary": "pre-commit is missing or configuration is invalid",
                "fix": ["Install pre-commit and run pre-commit validate-config."],
            },
            {
                "id": "ci_workflows",
                "severity": "high",
                "summary": "missing workflow groups: quality",
                "fix": ["Add quality workflow"],
            },
        ],
    }

    report = build_doctor_report_contract(payload)

    assert report["schema_version"] == SCHEMA_VERSION
    assert report["status"] == "blocked"
    assert report["confidence"] == "high"
    assert report["primary_finding"] == {
        "title": "missing workflow groups: quality",
        "severity": "high",
        "check_id": "ci_workflows",
        "roadmap_lane": "ci_reliability",
        "next_action": "Add quality workflow",
        "proof_command": "python -m sdetkit doctor --ci --format json",
    }
    assert report["summary"] == {
        "score": 64,
        "ok": False,
        "selected_checks": 4,
        "actionable_checks": 3,
        "passed_checks": 1,
        "failed_checks": 2,
        "skipped_checks": 1,
        "finding_count": 2,
        "failure_vector_count": 0,
    }
    assert report["failure_vector_evidence"]["available"] is False
    assert report["safety_decision"]["review_first"] is True
    assert report["safety_decision"]["automation_allowed"] is False
    assert report["safety_decision"]["patch_application_allowed"] is False
    assert report["safety_decision"]["merge_authorized"] is False
    assert report["safety_decision"]["semantic_equivalence_claim"] is False
    assert report["roadmap_alignment"]["lanes"] == [
        "ci_reliability",
        "developer_workflow",
    ]
    assert report["proof_commands"] == [
        "python -m pre_commit run -a",
        "python -m sdetkit doctor --ci --format json",
    ]


def test_doctor_report_markdown_is_professional_and_review_first() -> None:
    payload = {
        "ok": False,
        "score": 80,
        "quality": {"selected_checks": 1, "actionable_checks": 1, "evidence_count": 1},
        "next_actions": [
            {
                "id": "release_meta",
                "severity": "high",
                "summary": "release metadata missing or inconsistent",
                "fix": ["Run release readiness proof."],
            }
        ],
    }

    markdown = render_doctor_report_markdown(build_doctor_report_contract(payload))

    assert markdown.startswith("# SDETKit Doctor Report")
    assert "## Primary Finding" in markdown
    assert "## Failure Vector Evidence" in markdown
    assert "## Safety Decision" in markdown
    assert "automation_allowed: `false`" in markdown
    assert "patch_application_allowed: `false`" in markdown
    assert "merge_authorized: `false`" in markdown
    assert "release metadata missing or inconsistent" in markdown
    assert "placeholder" not in markdown.lower()
    assert "ascii" not in markdown.lower()


def test_green_doctor_report_keeps_next_action_roadmap_aligned() -> None:
    report = build_doctor_report_contract(
        {
            "ok": True,
            "score": 100,
            "quality": {
                "selected_checks": 2,
                "actionable_checks": 2,
                "passed_checks": 2,
                "failed_checks": 0,
                "skipped_checks": 0,
            },
            "next_actions": [],
        }
    )

    assert report["status"] == "green"
    assert report["confidence"] == "medium"
    assert report["summary"]["failure_vector_count"] == 0
    assert report["primary_finding"]["roadmap_lane"] == "green_main"
    assert (
        report["primary_finding"]["proof_command"] == "python -m sdetkit doctor --all --format json"
    )
    assert report["proof_commands"] == ["python -m sdetkit doctor --all --format json"]


def test_doctor_report_includes_failure_vector_evidence() -> None:
    failure_vector_bundle = {
        "schema_version": "sdetkit.failure_vector.bundle.v1",
        "vector_schema_version": "sdetkit.failure_vector.v1",
        "environment": "ci",
        "failure_vector_count": 2,
        "summary": {
            "by_failure_class": {"format": 1, "test": 1},
            "by_risk": {"low": 1, "medium": 1},
            "safe_fix_candidate_count": 1,
            "review_first_count": 1,
        },
        "failure_vectors": [
            {
                "check": "ruff_format",
                "failure_class": "format",
                "failure_type": "format",
                "risk": "low",
                "headline_signal": "ruff format would reformat one file",
                "local_repro_command": "python -m ruff format --check src/sdetkit/cli/__init__.py",
                "safe_fix_candidate": True,
                "safe_fix_allowed": False,
            },
            {
                "check": "pytest",
                "failure_class": "test",
                "failure_type": "test",
                "risk": "medium",
                "headline_signal": "FAILED tests/test_example.py::test_contract",
                "local_repro_command": "python -m pytest tests/test_example.py::test_contract",
                "safe_fix_candidate": False,
                "safe_fix_allowed": False,
            },
        ],
    }

    report = build_doctor_report_contract(
        {"ok": True, "score": 100, "quality": {"selected_checks": 1}, "next_actions": []},
        failure_vector_bundle=failure_vector_bundle,
    )

    assert report["status"] == "review_required"
    assert report["confidence"] == "high"
    assert report["summary"]["failure_vector_count"] == 2
    assert report["failure_vector_evidence"] == {
        "available": True,
        "schema_version": "sdetkit.failure_vector.bundle.v1",
        "vector_schema_version": "sdetkit.failure_vector.v1",
        "failure_vector_count": 2,
        "by_failure_class": {"format": 1, "test": 1},
        "by_risk": {"low": 1, "medium": 1},
        "safe_fix_candidate_count": 1,
        "safe_fix_allowed_count": 0,
        "review_first_count": 1,
        "top_failure": {
            "check": "pytest",
            "failure_type": "test",
            "risk": "medium",
            "headline_signal": "FAILED tests/test_example.py::test_contract",
            "local_repro_command": "python -m pytest tests/test_example.py::test_contract",
        },
    }
    assert "failure_diagnosis" in report["roadmap_alignment"]["lanes"]

    markdown = render_doctor_report_markdown(report)
    assert "## Failure Vector Evidence" in markdown
    assert "failure_vector_count: `2`" in markdown
    assert "top_failure_type: `test`" in markdown
    assert "top_failure_signal: `FAILED tests/test_example.py::test_contract`" in markdown


def test_doctor_report_contract_writes_deterministic_json(tmp_path) -> None:
    report = build_doctor_report_contract(
        {
            "ok": False,
            "score": 50,
            "quality": {"selected_checks": 1, "actionable_checks": 1},
            "next_actions": [
                {
                    "id": "deps",
                    "severity": "high",
                    "summary": "pip dependency issues detected",
                    "fix": ["Run pip check locally and resolve dependency conflicts."],
                }
            ],
        }
    )
    out = tmp_path / "doctor-report.json"

    write_doctor_report_contract(report, out)
    parsed = json.loads(out.read_text(encoding="utf-8"))

    assert parsed == report
    assert out.read_text(encoding="utf-8").endswith("\n")
