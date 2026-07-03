from __future__ import annotations

from sdetkit.pr_quality_live_dashboard import (
    build_live_evidence_snapshot,
    render_live_evidence_html,
    render_live_evidence_markdown,
    render_live_product_dashboard,
)


def _review_model() -> dict[str, object]:
    return {
        "decision": {
            "review_state": "blocked",
            "failed_checks": 1,
            "required_queued_checks": 0,
            "required_startup_failures": 0,
            "missing_required_contexts": 0,
        },
        "primary_failure": {
            "available": True,
            "check_name": "Quality truth baseline",
            "diagnostic_failure_code": "PYTEST_ASSERTION_FAILURE",
            "message": "source_module_count expected 497 but observed 498",
            "expected": "source_module_count = 497",
            "observed": "source_module_count = 498",
            "test_node": (
                "tests/test_quality_truth_baseline.py::"
                "test_quality_truth_baseline_matches_current_repository_configuration"
            ),
            "source_path": "docs/contracts/quality-truth-baseline.v1.json",
            "reproduction_command": (
                "python -m pytest -q "
                "tests/test_quality_truth_baseline.py::"
                "test_quality_truth_baseline_matches_current_repository_configuration "
                "-o addopts="
            ),
            "mapping_confidence": "high",
            "provenance_status": "confirmed",
            "step_evidence_status": "confirmed",
            "workflow_exact_head_verified": True,
            "reporting_only": True,
            "automation_allowed": False,
            "patch_application_allowed": False,
            "security_dismissal_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
        "authority_boundary": {
            "boundary_mode": "reporting_only",
            "patch_automation": False,
            "security_dismissal": False,
            "merge_authorization": False,
            "semantic_equivalence_claim": False,
        },
        "ghas_blocker_details": {"collected": True},
    }


def _snapshot(review_model: dict[str, object] | None = None) -> dict[str, object]:
    return build_live_evidence_snapshot(
        pr_number=1984,
        head_sha="a" * 40,
        base_sha="b" * 40,
        review_model=review_model or _review_model(),
        check_intelligence={"current_head_sha": "a" * 40},
        runtime_proof_artifacts={},
        artifact_manifest={},
        environment={
            "GITHUB_SERVER_URL": "https://github.com",
            "GITHUB_REPOSITORY": "sherif69-sa/DevS69-sdetkit",
            "GITHUB_RUN_ID": "28600000000",
            "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_WORKFLOW": "PR Quality Comment",
            "GITHUB_JOB": "quality",
        },
        generated_at="2026-07-03T08:00:00+00:00",
    )


def test_live_snapshot_exposes_complete_adaptive_diagnosis() -> None:
    snapshot = _snapshot()

    card = snapshot["adaptive_diagnosis"]
    assert card["diagnostic_completeness"] == "complete"
    assert card["confidence"] == "high"
    assert card["failure_class"] == "test"
    assert card["review_first"] is True
    assert card["checks"]["authority_boundary_preserved"] is True
    assert card["owner_files"] == [
        "docs/contracts/quality-truth-baseline.v1.json",
        "tests/test_quality_truth_baseline.py",
    ]
    assert card["reporting_only"] is True
    assert card["automation_allowed"] is False
    assert card["merge_authorized"] is False


def test_live_markdown_renders_contributor_adaptive_diagnosis() -> None:
    markdown = render_live_evidence_markdown(_snapshot())

    assert "## Adaptive Diagnosis" in markdown
    assert "| Completeness | `complete` |" in markdown
    assert "| Confidence | `high` |" in markdown
    assert "| Failure class | `test` |" in markdown
    assert "`authority_boundary_preserved`: `pass`" in markdown
    assert "docs/contracts/quality-truth-baseline.v1.json" in markdown
    assert "python -m pytest -q" in markdown
    assert "`automation_allowed=false`" in markdown
    assert "`merge_authorized=false`" in markdown


def test_live_html_renders_visible_adaptive_diagnosis() -> None:
    html = render_live_evidence_html(_snapshot())

    assert '<section id="adaptive-diagnosis"' in html
    assert "<h2>Adaptive Diagnosis</h2>" in html
    assert "Completeness" in html
    assert "Confidence" in html
    assert "Failure class" in html
    assert "Safeguards" in html
    assert "Owner files" in html
    assert "Focused proof" in html
    assert "Evidence gaps" in html
    assert "Next human action" in html
    assert "Authority boundary" in html
    assert "automation_allowed" in html
    assert ">false<" in html


def test_live_product_dashboard_includes_adaptive_diagnosis() -> None:
    html = render_live_product_dashboard(_snapshot())

    assert html.count('<section id="adaptive-diagnosis"') == 1
    assert "The first violated contract, evidence quality, and review-first action." in html


def test_live_html_escapes_adaptive_diagnosis_evidence() -> None:
    snapshot = _snapshot()
    snapshot["adaptive_diagnosis"]["next_human_action"] = "<script>alert('unsafe')</script>"

    html = render_live_evidence_html(snapshot)

    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


def test_live_views_preserve_existing_output_without_adaptive_card() -> None:
    review_model = {
        "decision": {
            "review_state": "ready",
            "failed_checks": 0,
            "required_queued_checks": 0,
            "required_startup_failures": 0,
            "missing_required_contexts": 0,
        },
        "authority_boundary": {
            "boundary_mode": "reporting_only",
            "patch_automation": False,
            "security_dismissal": False,
            "merge_authorization": False,
        },
        "ghas_blocker_details": {"collected": True},
    }
    snapshot = _snapshot(review_model)

    assert "adaptive_diagnosis" not in snapshot
    assert "## Adaptive Diagnosis" not in render_live_evidence_markdown(snapshot)
    assert '<section id="adaptive-diagnosis"' not in render_live_evidence_html(snapshot)
