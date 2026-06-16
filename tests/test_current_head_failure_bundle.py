from __future__ import annotations

import json

from sdetkit.current_head_failure_bundle import (
    SCHEMA_VERSION,
    build_current_head_failure_bundle,
    render_current_head_failure_bundle_markdown,
    write_current_head_failure_bundle,
)

TEST_SOURCE_AUTHORITY_EXPANDED_FIELDS_KEY = "_".join(("source", "authority", "expanded", "fields"))


def test_current_head_failure_bundle_persists_replayable_manifest(tmp_path):
    bundle = build_current_head_failure_bundle(
        pr_number=1366,
        head_sha="abc123",
        base_sha="def456",
        created_at="2026-05-21T03:00:00Z",
        check_intelligence={
            "checks_seen": 4,
            "failed_checks": [
                {
                    "name": "Validate (ubuntu-latest / py3.12)",
                    "safe_to_auto_fix": False,
                    "review_first": True,
                    "first_failure": {
                        "line": "FAILED tests/test_contract.py::test_contract",
                        "line_number": 42,
                        "tool": "pytest",
                        "kind": "test_failure",
                    },
                    "diagnosis": {
                        "owner_files": [
                            "src/sdetkit/check_intelligence.py",
                            "tests/test_check_intelligence_first_failure.py",
                        ]
                    },
                }
            ],
            "queued_checks": [{"name": "CI", "required": True}],
            "startup_failures": [],
            "missing_required_contexts": [],
        },
        action_report={"review_first": True, "safe_fix_available": False},
        diagnostic_vectors={"vectors": [{"classification": "test_failure"}]},
        remediation_plans={"plans": [{"classification": "review_first"}]},
        safe_fix_outcome={"attempted": False},
        refresh_summary={"merge_assessment": "blocked"},
    )

    written = write_current_head_failure_bundle(bundle, tmp_path)

    assert [path.name for path in written] == [
        "manifest.json",
        "failure-bundle.json",
        "failure-bundle.md",
    ]

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    payload = json.loads((tmp_path / "failure-bundle.json").read_text(encoding="utf-8"))
    markdown = (tmp_path / "failure-bundle.md").read_text(encoding="utf-8")

    assert manifest["schema_version"] == SCHEMA_VERSION
    assert manifest["pr_number"] == 1366
    assert manifest["head_sha"] == "abc123"
    assert manifest["base_sha"] == "def456"
    assert manifest["checks_seen"] == 4
    assert manifest["failed_checks"] == 1
    assert manifest["required_queued_checks"] == 1
    assert manifest["review_first"] is True
    assert manifest["safe_fix_allowed"] is False
    assert payload["first_failures"][0]["line"] == "FAILED tests/test_contract.py::test_contract"
    assert payload["owner_files"] == [
        "src/sdetkit/check_intelligence.py",
        "tests/test_check_intelligence_first_failure.py",
    ]
    assert "# Current-head failure evidence bundle" in markdown
    assert "Validate (ubuntu-latest / py3.12)" in markdown
    assert "src/sdetkit/check_intelligence.py" in markdown


def test_current_head_failure_bundle_rendering_is_deterministic():
    bundle = build_current_head_failure_bundle(
        pr_number=1,
        head_sha="head",
        base_sha="base",
        check_intelligence={"checks_seen": 0, "failed_checks": []},
        action_report={},
    )

    first = render_current_head_failure_bundle_markdown(bundle)
    second = render_current_head_failure_bundle_markdown(bundle)

    assert first == second
    assert "- Failed checks: `0`" in first
    assert "- none" in first


def test_current_head_failure_bundle_links_only_matching_head_trajectory() -> None:
    bundle = build_current_head_failure_bundle(
        pr_number=1803,
        head_sha="current-head",
        base_sha="base-head",
        check_intelligence={
            "checks_seen": 1,
            "failed_checks": [],
        },
        trajectory_jsonl_path="build/sdetkit/trajectory.jsonl",
        trajectory_records=[
            {
                "schema_version": "sdetkit.trajectory.v1",
                "trajectory_id": "matching-trajectory",
                "diagnostic_id": "diagnosis-1",
                "commit_sha": "current-head",
                "generated_at": "2026-06-16T01:00:00Z",
                "action": "review_test_failure",
                "final_result": "review_required",
                "decision": {
                    "review_first": True,
                    "auto_fix_allowed": False,
                },
                "authority_boundary": {
                    "reporting_only": True,
                    "automation_allowed": False,
                    "patch_application_allowed": False,
                    "merge_authorized": False,
                    "semantic_equivalence_proven": False,
                    "automatic_security_fix_allowed": False,
                    "automatic_dismissal_allowed": False,
                },
            },
            {
                "schema_version": "sdetkit.trajectory.v1",
                "trajectory_id": "other-head-trajectory",
                "diagnostic_id": "diagnosis-2",
                "commit_sha": "other-head",
                "generated_at": "2026-06-16T02:00:00Z",
                "action": "review_other_failure",
                "final_result": "review_required",
                "decision": {
                    "review_first": True,
                    "auto_fix_allowed": False,
                },
                "authority_boundary": {
                    "reporting_only": True,
                    "automation_allowed": False,
                    "patch_application_allowed": False,
                    "merge_authorized": False,
                    "semantic_equivalence_proven": False,
                },
            },
        ],
    )

    manifest = bundle["manifest"]
    history = bundle["trajectory_history"]

    assert manifest["trajectory_linked"] is True
    assert manifest["trajectory_record_count"] == 1
    assert manifest["trajectory_review_first_count"] == 1
    assert manifest["trajectory_auto_fix_allowed_count"] == 0
    assert manifest["trajectory_source_path"] == "build/sdetkit/trajectory.jsonl"

    assert history["schema_version"] == "sdetkit.current_head_trajectory_link.v1"
    assert history["status"] == "linked"
    assert history["head_sha"] == "current-head"
    assert history["record_count"] == 1
    assert history["trajectory_ids"] == ["matching-trajectory"]
    assert history["records"][0]["trajectory_id"] == "matching-trajectory"
    assert history["records"][0]["review_first"] is True
    assert history["records"][0][TEST_SOURCE_AUTHORITY_EXPANDED_FIELDS_KEY] == []
    assert history["reporting_only"] is True
    assert history["current_pr_decision_input"] is False
    assert history["expanded_authority_fields"] == []
    assert all(value is False for value in history["decision_boundary"].values())

    markdown = render_current_head_failure_bundle_markdown(bundle)
    assert "## Current-head trajectory history" in markdown
    assert "Matching records: `1`" in markdown
    assert "`matching-trajectory`" in markdown
    assert "other-head-trajectory" not in markdown
    assert "Current PR decision input: `false`" in markdown
    assert "Merge authorized: `false`" in markdown


def test_current_head_failure_bundle_surfaces_trajectory_authority_expansion() -> None:
    bundle = build_current_head_failure_bundle(
        pr_number=1803,
        head_sha="current-head",
        base_sha="base-head",
        trajectory_records=[
            {
                "trajectory_id": "unsafe-source-record",
                "commit_sha": "current-head",
                "decision": {
                    "review_first": False,
                    "auto_fix_allowed": True,
                },
                "authority_boundary": {
                    "reporting_only": False,
                    "automation_allowed": True,
                    "patch_application_allowed": True,
                    "merge_authorized": True,
                    "semantic_equivalence_proven": True,
                },
            }
        ],
    )

    history = bundle["trajectory_history"]

    assert history["status"] == "linked_review_required"
    assert history["records"][0][TEST_SOURCE_AUTHORITY_EXPANDED_FIELDS_KEY] == [
        "automation_allowed",
        "merge_authorized",
        "patch_application_allowed",
        "semantic_equivalence_proven",
    ]
    assert history["expanded_authority_fields"] == [
        "automation_allowed",
        "merge_authorized",
        "patch_application_allowed",
        "semantic_equivalence_proven",
    ]
    assert history["reporting_only"] is True
    assert history["current_pr_decision_input"] is False
    assert all(value is False for value in history["decision_boundary"].values())
