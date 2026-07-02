from __future__ import annotations

from sdetkit.pr_quality_live_dashboard import build_live_evidence_snapshot
from sdetkit.pr_quality_review_experience import render_pr_quality_review_experience


def _model(primary_failure: dict[str, object]) -> dict[str, object]:
    return {
        "decision": {
            "review_state": "blocked",
            "failed_checks": 1,
            "required_queued_checks": 0,
            "required_startup_failures": 0,
            "missing_required_contexts": 0,
        },
        "primary_failure": primary_failure,
        "authority_boundary": {
            "boundary_mode": "reporting_only",
            "patch_automation": False,
            "security_dismissal": False,
            "merge_authorization": False,
            "semantic_equivalence_claim": False,
        },
        "ghas_blocker_details": {"collected": True},
        "artifact_index": [],
    }


def _snapshot(model: dict[str, object]) -> None:
    model["live_evidence"] = build_live_evidence_snapshot(
        pr_number=1972,
        head_sha="a" * 40,
        base_sha="b" * 40,
        review_model=model,
        check_intelligence={"current_head_sha": "a" * 40},
        runtime_proof_artifacts={},
        artifact_manifest={},
        environment={
            "GITHUB_SERVER_URL": "https://github.com",
            "GITHUB_REPOSITORY": "sherif69-sa/DevS69-sdetkit",
            "GITHUB_RUN_ID": "28574132738",
            "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_WORKFLOW": "PR Quality Comment",
            "GITHUB_JOB": "quality",
        },
        generated_at="2026-07-02T08:00:00+00:00",
    )


def test_live_evidence_enriches_budget_expected_and_observed() -> None:
    model = _model(
        {
            "available": True,
            "check_name": "Workflow contracts",
            "expected": "",
            "observed": "",
            "message": "",
            "test_node": "",
            "families": [
                {
                    "failure_code": "PYTEST_ASSERTION_FAILURE",
                    "test_node": (
                        "tests/test_workflow_contracts.py::test_repository_workflow_contracts_pass"
                    ),
                    "message": (
                        "[{'code': 'budget_regression', "
                        "'metric': 'heavy_workflow_count', "
                        "'maximum': 8, 'actual': 9}]"
                    ),
                }
            ],
        }
    )

    _snapshot(model)

    failure = model["primary_failure"]
    assert failure["expected"] == "heavy_workflow_count <= 8"
    assert failure["observed"] == "heavy_workflow_count = 9"
    assert failure["test_node"].endswith("test_repository_workflow_contracts_pass")
    assert "budget_regression" in failure["message"]

    html = render_pr_quality_review_experience(model)
    assert "<dt>Expected</dt><dd><code>heavy_workflow_count &lt;= 8</code>" in html
    assert "<dt>Observed</dt><dd><code>heavy_workflow_count = 9</code>" in html
    assert "Not captured" not in html.split("<dt>Expected</dt>", 1)[1].split("</dl>", 1)[0]


def test_live_evidence_enriches_quality_truth_baseline_mismatch() -> None:
    model = _model(
        {
            "available": True,
            "check_name": "GitHub Actions Advanced Reference",
            "expected": "",
            "observed": "",
            "message": "",
            "test_node": "",
            "families": [
                {
                    "failure_code": "PYTEST_ASSERTION_FAILURE",
                    "test_node": (
                        "tests/test_quality_truth_baseline.py::"
                        "test_quality_truth_baseline_matches_current_repository_configuration"
                    ),
                    "message": (
                        "[{'check': 'source_module_count_matches', "
                        "'metric': 'source_module_count', "
                        "'expected': 495, 'actual': 496}]"
                    ),
                }
            ],
        }
    )

    _snapshot(model)

    failure = model["primary_failure"]
    assert failure["expected"] == "source_module_count = 495"
    assert failure["observed"] == "source_module_count = 496"
    assert failure["test_node"].endswith(
        "test_quality_truth_baseline_matches_current_repository_configuration"
    )


def test_live_evidence_preserves_explicit_expected_and_observed() -> None:
    model = _model(
        {
            "available": True,
            "check_name": "Focused contract",
            "expected": "expected payload",
            "observed": "observed payload",
            "message": "expected='other'; observed='other'",
            "families": [],
        }
    )

    _snapshot(model)

    failure = model["primary_failure"]
    assert failure["expected"] == "expected payload"
    assert failure["observed"] == "observed payload"


def test_live_evidence_uses_truthful_fallback_when_detail_is_absent() -> None:
    model = _model(
        {
            "available": True,
            "check_name": "Workflow contracts",
            "expected": "",
            "observed": "",
            "message": "",
            "families": [],
        }
    )

    _snapshot(model)

    failure = model["primary_failure"]
    assert failure["expected"] == "check completes successfully"
    assert failure["observed"] == "Workflow contracts reported failure without detailed output"
