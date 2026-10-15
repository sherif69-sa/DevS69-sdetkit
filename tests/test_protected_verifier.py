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
REMEDIATION_PLAN_CONTEXT = _key(("remediation", "plan", "context"))
CURRENT_PR_DECISION_INPUT = _key(("current", "pr", "decision", "input"))
PROTECTED_VERIFIER_EXECUTION_CHANGED = _key(("protected", "verifier", "execution", "changed"))
SELECTED_PLAN = _key(("selected", "plan"))
SELECTED_PLAN_PRESENT = _key(("selected", "plan", "present"))


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


RUNTIME_PROOF_LIVE_BENCHMARK = _key(("live", "benchmark"))
BENCHMARK_RUNTIME_CONTRACT_COLLECTION_STATUS = _key(("runtime", "contract", "collection", "status"))
BENCHMARK_RUNTIME_CONTRACT_STATUS = _key(("runtime", "contract", "status"))
BENCHMARK_RUNTIME_CONTRACT_SCENARIO_COUNT = _key(("runtime", "contract", "scenario", "count"))
BENCHMARK_RUNTIME_CONTRACT_RECORD_COUNT = _key(("runtime", "contract", "record", "count"))
BENCHMARK_RUNTIME_CONTRACT_SECURITY_RELEVANCE_COUNT = _key(
    ("runtime", "contract", "security", "relevance", "count")
)
BENCHMARK_RUNTIME_CONTRACT_AUTHORITY_BOUNDARY_PRESERVED_COUNT = _key(
    ("runtime", "contract", "authority", "boundary", "preserved", "count")
)
BENCHMARK_RUNTIME_CONTRACT_EXPANDED_AUTHORITY_FIELDS = _key(
    ("runtime", "contract", "expanded", "authority", "fields")
)
BENCHMARK_RUNTIME_CONTRACT_PATCH_APPLICATION_ALLOWED = _key(
    ("runtime", "contract", "patch", "application", "allowed")
)
BENCHMARK_RUNTIME_CONTRACT_SECURITY_DISMISSAL_ALLOWED = _key(
    ("runtime", "contract", "security", "dismissal", "allowed")
)
BENCHMARK_RUNTIME_CONTRACT_MERGE_AUTHORIZED = _key(("runtime", "contract", "merge", "authorized"))
BENCHMARK_RUNTIME_CONTRACT_SEMANTIC_EQUIVALENCE_CLAIM = _key(
    ("runtime", "contract", "semantic", "equivalence", "claim")
)


PR_QUALITY_BENCHMARK_CONTRACT_COLLECTION_STATUS = _key(
    ("benchmark", "contract", "collection", "status")
)
PR_QUALITY_BENCHMARK_CONTRACT_STATUS = _key(("benchmark", "contract", "status"))
PR_QUALITY_BENCHMARK_CONTRACT_SCENARIO_COUNT = _key(("benchmark", "contract", "scenario", "count"))
PR_QUALITY_BENCHMARK_CONTRACT_RECORD_COUNT = _key(("benchmark", "contract", "record", "count"))
PR_QUALITY_BENCHMARK_CONTRACT_SECURITY_RELEVANCE_COUNT = _key(
    ("benchmark", "contract", "security", "relevance", "count")
)
PR_QUALITY_BENCHMARK_CONTRACT_AUTHORITY_BOUNDARY_PRESERVED_COUNT = _key(
    ("benchmark", "contract", "authority", "boundary", "preserved", "count")
)
PR_QUALITY_BENCHMARK_CONTRACT_EXPANDED_AUTHORITY_FIELDS = _key(
    ("benchmark", "contract", "expanded", "authority", "fields")
)
PR_QUALITY_BENCHMARK_CONTRACT_PATCH_APPLICATION_ALLOWED = _key(
    ("benchmark", "contract", "patch", "application", "allowed")
)
PR_QUALITY_BENCHMARK_CONTRACT_SECURITY_DISMISSAL_ALLOWED = _key(
    ("benchmark", "contract", "security", "dismissal", "allowed")
)
PR_QUALITY_BENCHMARK_CONTRACT_MERGE_AUTHORIZED = _key(
    ("benchmark", "contract", "merge", "authorized")
)
PR_QUALITY_BENCHMARK_CONTRACT_SEMANTIC_EQUIVALENCE_CLAIM = _key(
    ("benchmark", "contract", "semantic", "equivalence", "claim")
)
PR_QUALITY_BENCHMARK_CONTRACT_REPLAY_OUTPUT_KEY = _key(
    ("pr", "quality", "benchmark", "contract", "replay", "evidence")
)
PR_QUALITY_BENCHMARK_REPLAY_HEADING = " ".join(
    ("Runtime", "proof", "PR", "Quality", "benchmark", "replay", "evidence")
)
PR_QUALITY_BENCHMARK_REPLAY_MERGE_FALSE_LINE = " ".join(
    (
        "Merge",
        "authorized",
        "by",
        "runtime",
        "proof",
        "PR",
        "Quality",
        "benchmark",
        "replay",
        "evidence:",
        "`false`",
    )
)


def test_protected_verifier_reports_remediation_plan_context_without_decision_authority() -> None:
    remediation_plan = _safe_plan()
    remediation_plan["schema_version"] = ".".join(("sdetkit", "remediation", "plan", "v1"))

    baseline = verify_patch(
        patch_score=_candidate_patch_score(),
    )
    payload = verify_patch(
        patch_score=_candidate_patch_score(),
        remediation_plan=remediation_plan,
    )

    context = payload[REMEDIATION_PLAN_CONTEXT]
    selected = context[SELECTED_PLAN]

    assert context["schema_version"] == ".".join(
        (
            "sdetkit",
            "protected",
            "verifier",
            "remediation",
            "plan",
            "context",
            "v1",
        )
    )
    assert context["collection_status"] == "collected"
    assert context["status"] == "plan_selected"
    assert context["source_schema"] == ".".join(("sdetkit", "remediation", "plan", "v1"))
    assert context["plan_count"] == 1
    assert context[SELECTED_PLAN_PRESENT] is True
    assert selected["diagnosis_id"] == "formatting-autopilot"
    assert selected["failure_surface"] == "formatting"
    assert selected["classification"] == "formatting_only"
    assert selected["safe_to_auto_fix"] is True
    assert selected["allowed_strategy"] == "run_pre_commit"
    assert selected["affected_files"] == ["src/sdetkit/example.py"]
    assert context["reporting_only"] is True
    assert context[CURRENT_PR_DECISION_INPUT] is False
    assert context[PROTECTED_VERIFIER_EXECUTION_CHANGED] is False
    assert context["decision_boundary"] == {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "automatic_security_fix_allowed": False,
        "automatic_dismissal_allowed": False,
    }

    assert payload["decision"] == baseline["decision"]
    assert payload["risk_flags"] == baseline["risk_flags"] == []

    markdown = render_markdown(payload)
    assert "## Remediation plan context" in markdown
    assert "Status: `plan_selected`" in markdown
    assert "Current PR decision input: `false`" in markdown
    assert "ProtectedVerifier execution changed: `false`" in markdown
    assert "Patch application allowed by remediation-plan context: `false`" in markdown


def test_protected_verifier_cli_accepts_optional_remediation_plan_context(
    tmp_path: Path,
) -> None:
    patch_score_path = tmp_path / "patch-score.json"
    remediation_plan_path = tmp_path / "remediation-plan.json"
    out_dir = tmp_path / "protected-verifier"

    remediation_plan = _safe_plan()
    remediation_plan["schema_version"] = ".".join(("sdetkit", "remediation", "plan", "v1"))

    patch_score_path.write_text(
        json.dumps(_candidate_patch_score()),
        encoding="utf-8",
    )
    remediation_plan_path.write_text(
        json.dumps(remediation_plan),
        encoding="utf-8",
    )

    rc = main(
        [
            "--patch-score",
            str(patch_score_path),
            "--remediation-plan",
            str(remediation_plan_path),
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0

    payload = json.loads((out_dir / "protected-verifier-decision.json").read_text(encoding="utf-8"))
    context = payload[REMEDIATION_PLAN_CONTEXT]

    assert context["status"] == "plan_selected"
    assert context[SELECTED_PLAN_PRESENT] is True
    assert context["reporting_only"] is True
    assert context[CURRENT_PR_DECISION_INPUT] is False
    assert context[PROTECTED_VERIFIER_EXECUTION_CHANGED] is False
    assert payload["decision"]["patch_application_allowed"] is False
    assert payload["decision"]["merge_authorized"] is False
    assert payload["decision"]["semantic_equivalence_proven"] is False
