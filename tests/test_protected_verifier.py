from __future__ import annotations

import json
from pathlib import Path

from sdetkit.patch_scorer import score_patch
from sdetkit.protected_verifier import main, render_markdown, verify_patch

_key = "_".join
CANDIDATE_FOR_PROTECTED_VERIFICATION = _key(("candidate", "for", "protected", "verification"))
REVIEW_REQUIRED = _key(("review", "required"))
BLOCKED_REVIEW_FIRST = _key(("blocked", "review", "first"))
HUMAN_REVIEW_REQUIRED_BEFORE_PATCH_APPLICATION = _key(
    ("human", "review", "required", "before", "patch", "application")
)


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


def _safe_insights() -> dict:
    return {
        "recurring_review_first_surfaces": [],
        "recurring_safe_fix_patterns": [
            {
                "failure_class": "formatting_only",
                "action": "run_pre_commit",
                "count": 2,
            }
        ],
        "safety_gate_evidence": {
            "collection_status": "collected",
            "status": "safety_gate_evidence_observed",
            "source": "trajectory.safety_gate",
            "record_count": 1,
            "safe_fix_allowed_count": 1,
            "review_first_count": 0,
            "reporting_only_count": 1,
            "decision_boundary": {
                "automation_allowed": False,
                "patch_application_allowed": False,
                "merge_authorized": False,
                "semantic_equivalence_proven": False,
            },
        },
    }


def _candidate_patch_score() -> dict:
    return score_patch(
        remediation_plan=_safe_plan(),
        proposed_patch={
            "patch_id": "format-patch",
            "changed_files": ["src/sdetkit/example.py"],
        },
        pattern_insights=_safe_insights(),
    )


def test_protected_verifier_keeps_candidate_review_first_without_authority() -> None:
    payload = verify_patch(
        patch_score=_candidate_patch_score(),
        failure_bundle={
            "status": "collected",
            "decision_boundary": {
                "automation_allowed": False,
                "patch_application_allowed": False,
                "merge_authorized": False,
                "semantic_equivalence_proven": False,
            },
        },
        runtime_proof={
            "status": "collected",
            "decision_boundary": {
                "automation_allowed": False,
                "patch_application_allowed": False,
                "merge_authorized": False,
                "semantic_equivalence_proven": False,
            },
        },
    )

    assert payload["schema_version"] == "sdetkit.protected_verifier.decision.v1"
    assert payload["decision"]["status"] == REVIEW_REQUIRED
    assert payload["decision"]["review_first"] is True
    assert payload["decision"][CANDIDATE_FOR_PROTECTED_VERIFICATION] is True
    assert payload["decision"]["protected_verification_passed"] is False
    assert payload["decision"]["automation_allowed"] is False
    assert payload["decision"]["patch_application_allowed"] is False
    assert payload["decision"]["merge_authorized"] is False
    assert payload["decision"]["semantic_equivalence_proven"] is False
    assert payload["decision"]["next_action"] == HUMAN_REVIEW_REQUIRED_BEFORE_PATCH_APPLICATION
    assert payload["decision_boundary"] == {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "automatic_security_fix_allowed": False,
        "automatic_dismissal_allowed": False,
    }
    assert payload["verification_evidence"]["proof_requirements"] == ["python -m pre_commit run -a"]
    assert payload["risk_flags"] == []

    markdown = render_markdown(payload)
    assert "# ProtectedVerifier decision" in markdown
    assert "Review first: `true`" in markdown
    assert "Protected verification passed: `false`" in markdown
    assert "Patch application allowed: `false`" in markdown
    assert "Merge authorized: `false`" in markdown
    assert "Semantic equivalence proven: `false`" in markdown


def test_protected_verifier_blocks_non_candidate_patch_score() -> None:
    patch_score = _candidate_patch_score()
    patch_score["decision"]["status"] = BLOCKED_REVIEW_FIRST
    patch_score["decision"][CANDIDATE_FOR_PROTECTED_VERIFICATION] = False

    payload = verify_patch(patch_score=patch_score)

    assert payload["decision"]["status"] == BLOCKED_REVIEW_FIRST
    assert payload["decision"][CANDIDATE_FOR_PROTECTED_VERIFICATION] is False
    assert payload["decision"]["automation_allowed"] is False
    assert payload["decision"]["merge_authorized"] is False
    assert payload["decision"]["semantic_equivalence_proven"] is False
    assert any(
        flag["code"] == "PATCH_SCORE_NOT_CANDIDATE" and flag["blocking"] is True
        for flag in payload["risk_flags"]
    )


def test_protected_verifier_blocks_authority_expansion_attempts() -> None:
    patch_score = _candidate_patch_score()
    patch_score["decision"]["merge_authorized"] = True

    payload = verify_patch(
        patch_score=patch_score,
        runtime_proof={
            "status": "collected",
            "decision_boundary": {"semantic_equivalence_proven": True},
        },
    )

    assert payload["decision"]["status"] == BLOCKED_REVIEW_FIRST
    assert payload["decision"]["automation_allowed"] is False
    assert payload["decision"]["patch_application_allowed"] is False
    assert payload["decision"]["merge_authorized"] is False
    assert payload["decision"]["semantic_equivalence_proven"] is False
    assert {
        field
        for flag in payload["risk_flags"]
        if flag["code"] == "AUTHORITY_EXPANSION_ATTEMPT"
        for field in flag["fields"]
    } == {"merge_authorized", "semantic_equivalence_proven"}


def test_protected_verifier_cli_writes_json_and_markdown(tmp_path: Path, capsys) -> None:
    patch_score_path = tmp_path / "patch-score.json"
    out_dir = tmp_path / "protected-verifier"
    patch_score_path.write_text(json.dumps(_candidate_patch_score()), encoding="utf-8")

    rc = main(
        [
            "--patch-score",
            str(patch_score_path),
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    payload = json.loads((out_dir / "protected-verifier-decision.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "protected-verifier-decision.md").read_text(encoding="utf-8")

    assert printed["schema_version"] == "sdetkit.protected_verifier.decision.v1"
    assert printed["decision"]["status"] == REVIEW_REQUIRED
    assert payload["decision"]["patch_application_allowed"] is False
    assert payload["decision"]["merge_authorized"] is False
    assert payload["decision"]["semantic_equivalence_proven"] is False
    assert "# ProtectedVerifier decision" in markdown
    assert "This verifier is reporting-only" in markdown
