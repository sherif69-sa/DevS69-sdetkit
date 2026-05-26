from __future__ import annotations

import json
from pathlib import Path

from sdetkit.pr_quality_candidate_visibility import (
    build_candidate_visibility,
    main,
    render_markdown,
)
from sdetkit.protected_verifier import (
    CHANGED_FILE_INVENTORY_MISMATCH,
    OUTSIDE_SCORED_SCOPE,
)


def _formatting_failure() -> dict:
    return {
        "failed_checks": [
            {
                "name": "PR Quality local quality gate",
                "surface": "quality",
                "diagnosis": {
                    "title": "Pre-commit formatting drift",
                    "code": "PRE_COMMIT_FORMAT_DRIFT",
                },
                "first_failure": {
                    "line": "ruff format..............................Failed",
                    "line_number": 30,
                    "tool": "ruff",
                    "kind": "format_drift",
                },
                "safe_to_auto_fix": True,
                "safe_remediation": {
                    "safe_to_auto_fix": True,
                    "strategy": "run_pre_commit",
                    "category": "formatting_only",
                    "affected_files": ["src/sdetkit/example.py"],
                },
            }
        ]
    }


def _pattern_insights() -> dict:
    return {
        "recurring_review_first_surfaces": [],
        "recurring_safe_fix_patterns": [
            {"failure_class": "formatting_only", "action": "run_pre_commit", "count": 2}
        ],
    }


def _verification_evidence(changed_files: list[str] | None = None) -> dict:
    return {
        "changed_files": changed_files or ["src/sdetkit/example.py"],
        "proof_results": [
            {"command": "python -m pre_commit run -a", "status": "passed", "exit_code": 0}
        ],
    }


def test_candidate_visibility_normalizes_only_its_read_only_view() -> None:
    intelligence = _formatting_failure()
    payload = build_candidate_visibility(
        check_intelligence=intelligence,
        evidence_graph={},
        pr_quality_action_report={},
        changed_files=["src/sdetkit/example.py"],
        pattern_insights=_pattern_insights(),
        verification_evidence=_verification_evidence(),
    )

    assert intelligence["failed_checks"][0]["surface"] == "quality"
    assert payload["diagnostic_vector"]["diagnoses"][0]["failure_surface"] == "formatting"


def test_candidate_visibility_exposes_matching_structural_proof_without_authority() -> None:
    payload = build_candidate_visibility(
        check_intelligence=_formatting_failure(),
        evidence_graph={},
        pr_quality_action_report={},
        changed_files=["src/sdetkit/example.py"],
        pattern_insights=_pattern_insights(),
        verification_evidence=_verification_evidence(),
    )

    score = payload["patch_score"]
    verification = payload["protected_verifier"]
    assert payload["status"] == "candidate_structurally_verified"
    assert payload["candidate_files"] == ["src/sdetkit/example.py"]
    assert payload["observed_pr_changed_files"] == ["src/sdetkit/example.py"]
    assert score["decision"]["status"] == "candidate_for_protected_verification"
    assert score["decision"]["automation_allowed"] is False
    assert verification["decision"]["status"] == "structurally_verified_candidate"
    assert verification["decision"]["automation_allowed"] is False
    assert verification["decision"]["merge_authorized"] is False
    assert payload["decision_boundary"]["automation_allowed"] is False
    assert payload["decision_boundary"]["merge_authorized"] is False

    markdown = render_markdown(payload)
    assert "Read-only remediation candidate verification" in markdown
    assert "Candidate scope: `src/sdetkit/example.py`" in markdown
    assert "PatchScorer decision: `candidate_for_protected_verification`" in markdown
    assert "ProtectedVerifier decision: `structurally_verified_candidate`" in markdown
    assert "Automation allowed: `false`" in markdown


def test_candidate_visibility_keeps_broader_pr_diff_review_first() -> None:
    observed = ["src/sdetkit/example.py", "src/sdetkit/feature.py"]
    payload = build_candidate_visibility(
        check_intelligence=_formatting_failure(),
        evidence_graph={},
        pr_quality_action_report={},
        changed_files=observed,
        pattern_insights=_pattern_insights(),
        verification_evidence=_verification_evidence(observed),
    )

    verification = payload["protected_verifier"]
    codes = {finding["code"] for finding in verification["findings"]}
    assert payload["status"] == "candidate_review_first_after_verification"
    assert payload["candidate_files"] == ["src/sdetkit/example.py"]
    assert payload["observed_pr_changed_files"] == observed
    assert payload["patch_score"]["decision"]["status"] == "candidate_for_protected_verification"
    assert verification["decision"]["status"] == "blocked_review_first"
    assert CHANGED_FILE_INVENTORY_MISMATCH in codes
    assert OUTSIDE_SCORED_SCOPE in codes
    assert verification["decision"]["automation_allowed"] is False
    assert verification["decision"]["merge_authorized"] is False


def test_candidate_visibility_stays_quiet_without_candidate() -> None:
    payload = build_candidate_visibility(
        check_intelligence={"failed_checks": []},
        evidence_graph={},
        pr_quality_action_report={},
        changed_files=[],
        pattern_insights={},
        verification_evidence={},
    )

    assert payload["status"] == "no_candidate"
    assert payload["candidate_count"] == 0
    assert payload["patch_score"] == {}
    assert payload["protected_verifier"] == {}
    assert render_markdown(payload) == ""


def test_candidate_visibility_cli_writes_read_only_artifacts(tmp_path: Path, capsys) -> None:
    inputs = {
        "check-intelligence.json": _formatting_failure(),
        "evidence-graph.json": {},
        "action-report.json": {},
        "pattern-insights.json": _pattern_insights(),
        "verification-evidence.json": _verification_evidence(),
    }
    for name, payload in inputs.items():
        (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / "changed-files.txt").write_text("src/sdetkit/example.py\n", encoding="utf-8")

    out_dir = tmp_path / "visibility"
    rc = main(
        [
            "--check-intelligence",
            str(tmp_path / "check-intelligence.json"),
            "--evidence-graph",
            str(tmp_path / "evidence-graph.json"),
            "--pr-quality-action-report",
            str(tmp_path / "action-report.json"),
            "--changed-files",
            str(tmp_path / "changed-files.txt"),
            "--pattern-insights",
            str(tmp_path / "pattern-insights.json"),
            "--verification-evidence",
            str(tmp_path / "verification-evidence.json"),
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "candidate_structurally_verified"
    assert printed["decision_boundary"]["automation_allowed"] is False
    assert (out_dir / "candidate-visibility.json").exists()
    assert (out_dir / "candidate-visibility.md").exists()
    assert (out_dir / "diagnostic-vector" / "diagnostic-vector.json").exists()
    assert (out_dir / "remediation-plan" / "remediation-plan.json").exists()
    assert (out_dir / "patch-score" / "patch-score.json").exists()
    assert (out_dir / "protected-verifier" / "protected-verifier-result.json").exists()


def test_candidate_visibility_normalizes_matching_action_report_without_suppressing_candidate() -> (
    None
):
    failed_check = _formatting_failure()["failed_checks"][0]
    action_report = {"primary_blocker": dict(failed_check)}
    payload = build_candidate_visibility(
        check_intelligence=_formatting_failure(),
        evidence_graph={},
        pr_quality_action_report=action_report,
        changed_files=["src/sdetkit/example.py"],
        pattern_insights=_pattern_insights(),
        verification_evidence=_verification_evidence(),
    )

    assert action_report["primary_blocker"]["surface"] == "quality"
    assert payload["candidate_count"] == 1
    assert payload["review_first_plan_count"] == 0
    assert payload["status"] == "candidate_structurally_verified"
    assert payload["protected_verifier"]["decision"]["automation_allowed"] is False
    assert payload["protected_verifier"]["decision"]["merge_authorized"] is False
