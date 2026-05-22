from __future__ import annotations

import json
from pathlib import Path

from sdetkit.patch_scorer import main, score_patch


def _safe_plan() -> dict:
    return {
        "plans": [
            {
                "diagnosis_id": "formatting-autopilot",
                "failure_surface": "formatting",
                "classification": "formatting_only",
                "safe_to_auto_fix": True,
                "allowed_strategy": "run_pre_commit",
                "blocked_reason": "",
                "risk_level": "low",
                "affected_files": ["src/sdetkit/example.py"],
                "exact_fix_scope": {
                    "allowed_files": ["src/sdetkit/example.py"],
                    "allowed_strategy": "run_pre_commit",
                    "scope": "deterministic formatting or whitespace only",
                },
                "proof_commands": ["python -m pre_commit run -a"],
            }
        ]
    }


def _review_first_plan() -> dict:
    return {
        "plans": [
            {
                "diagnosis_id": "release-case",
                "failure_surface": "release",
                "classification": "release_artifact",
                "safe_to_auto_fix": False,
                "allowed_strategy": "review_first_release_validation",
                "blocked_reason": "release artifacts require clean build and metadata validation",
                "risk_level": "high",
                "affected_files": ["pyproject.toml"],
                "exact_fix_scope": {"allowed_files": []},
                "proof_commands": [
                    "python -m build",
                    "python -m twine check dist/*",
                ],
            }
        ]
    }


def _matching_safe_insights() -> dict:
    return {
        "recurring_review_first_surfaces": [],
        "recurring_safe_fix_patterns": [
            {
                "failure_class": "formatting_only",
                "action": "run_pre_commit",
                "count": 2,
            }
        ],
    }


def test_patch_scorer_marks_exact_formatting_patch_as_verification_candidate_only() -> None:
    payload = score_patch(
        remediation_plan=_safe_plan(),
        proposed_patch={
            "patch_id": "format-patch",
            "changed_files": ["src/sdetkit/example.py"],
        },
        pattern_insights=_matching_safe_insights(),
    )

    assert payload["score"] == 100
    assert payload["risk_flags"] == []
    assert payload["decision"]["status"] == "candidate_for_protected_verification"
    assert payload["decision"]["candidate_for_protected_verification"] is True
    assert payload["decision"]["automation_allowed"] is False
    assert payload["proof_requirements"] == ["python -m pre_commit run -a"]
    assert payload["history_evidence"]["safe_fix_pattern_match"] is True


def test_patch_scorer_blocks_out_of_scope_and_protected_test_changes() -> None:
    payload = score_patch(
        remediation_plan=_safe_plan(),
        proposed_patch={
            "patch_id": "broad-patch",
            "changed_files": [
                "src/sdetkit/example.py",
                "tests/test_example.py",
            ],
        },
        pattern_insights=_matching_safe_insights(),
    )

    codes = {flag["code"] for flag in payload["risk_flags"]}
    assert payload["score"] == 0
    assert "OUTSIDE_EXACT_FIX_SCOPE" in codes
    assert "PROTECTED_PATH_CHANGED" in codes
    assert payload["decision"]["status"] == "blocked_review_first"
    assert payload["decision"]["candidate_for_protected_verification"] is False
    assert payload["decision"]["automation_allowed"] is False


def test_patch_scorer_blocks_review_first_release_plan() -> None:
    payload = score_patch(
        remediation_plan=_review_first_plan(),
        proposed_patch={
            "patch_id": "release-patch",
            "changed_files": ["pyproject.toml"],
        },
        pattern_insights={},
    )

    codes = {flag["code"] for flag in payload["risk_flags"]}
    assert payload["score"] == 0
    assert "PLAN_REVIEW_FIRST" in codes
    assert "NON_FORMATTING_SURFACE" in codes
    assert "PROTECTED_PATH_CHANGED" in codes
    assert payload["decision"]["status"] == "blocked_review_first"


def test_patch_scorer_keeps_unproven_safe_pattern_read_only() -> None:
    payload = score_patch(
        remediation_plan=_safe_plan(),
        proposed_patch={
            "patch_id": "first-observed-format-patch",
            "changed_files": ["src/sdetkit/example.py"],
        },
        pattern_insights={},
    )

    assert payload["score"] == 90
    assert payload["risk_flags"][0]["code"] == "SAFE_PATTERN_NOT_REPEATED"
    assert payload["risk_flags"][0]["blocking"] is False
    assert payload["decision"]["status"] == "candidate_for_protected_verification"
    assert payload["decision"]["automation_allowed"] is False


def test_patch_scorer_blocks_matching_review_first_surface_history() -> None:
    payload = score_patch(
        remediation_plan=_safe_plan(),
        proposed_patch={
            "patch_id": "format-review-history",
            "changed_files": ["src/sdetkit/example.py"],
        },
        pattern_insights={
            "recurring_review_first_surfaces": [{"value": "formatting", "count": 2}],
            "recurring_safe_fix_patterns": [],
        },
    )

    assert payload["score"] == 0
    assert payload["risk_flags"][0]["code"] == "RECURRING_REVIEW_FIRST_SURFACE"
    assert payload["decision"]["status"] == "blocked_review_first"


def test_patch_scorer_cli_writes_json_and_markdown(tmp_path: Path, capsys) -> None:
    remediation_path = tmp_path / "remediation-plan.json"
    proposed_path = tmp_path / "proposed-patch.json"
    insights_path = tmp_path / "pattern-insights.json"
    out_dir = tmp_path / "patch-score"

    remediation_path.write_text(json.dumps(_safe_plan()), encoding="utf-8")
    proposed_path.write_text(
        json.dumps(
            {
                "patch_id": "format-patch",
                "changed_files": ["src/sdetkit/example.py"],
            }
        ),
        encoding="utf-8",
    )
    insights_path.write_text(json.dumps(_matching_safe_insights()), encoding="utf-8")

    rc = main(
        [
            "--remediation-plan",
            str(remediation_path),
            "--proposed-patch",
            str(proposed_path),
            "--pattern-insights",
            str(insights_path),
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    score = json.loads((out_dir / "patch-score.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "patch-score.md").read_text(encoding="utf-8")

    assert printed["score"] == 100
    assert score["decision"]["status"] == "candidate_for_protected_verification"
    assert score["decision"]["automation_allowed"] is False
    assert "# Patch safety score" in markdown
    assert "ProtectedVerifier must exist and pass" in markdown
