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
    }
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
    assert report["primary_finding"]["roadmap_lane"] == "green_main"
    assert (
        report["primary_finding"]["proof_command"]
        == "python -m sdetkit doctor --all --format json"
    )
    assert report["proof_commands"] == ["python -m sdetkit doctor --all --format json"]


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
