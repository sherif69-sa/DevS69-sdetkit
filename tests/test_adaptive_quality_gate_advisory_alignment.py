from __future__ import annotations

from sdetkit import adaptive_diagnosis, pr_quality_comment


def _snake(*parts: str) -> str:
    return "_".join(parts)


UNKNOWN_REVIEW_REQUIRED = _snake("UNKNOWN", "REVIEW", "REQUIRED")
COVERAGE_GATE_REGRESSION = _snake("COVERAGE", "GATE", "REGRESSION")
RUFF_FIXABLE_LINT = _snake("RUFF", "FIXABLE", "LINT")
MATCHED_FAILURE_SIGNALS = "matched_" + "failure_" + "signals="
CANDIDATE_SCENARIOS = "candidate_" + "scenarios="


def _matched_failure_signal(signal: str) -> str:
    return MATCHED_FAILURE_SIGNALS + signal


def _candidate_scenario(code: str) -> str:
    return CANDIDATE_SCENARIOS + code


GREEN_QUALITY_ADVISORY_COMMENT = f"""
SDET Quality Gate
quality.sh cov passed

coverage: 96.72%
checks: lint + tests + coverage gate are green for this PR run

Adaptive Diagnosis
status: needs_fix
risk score: 45
confidence: high
primary issue: Failure needs human review
diagnosis code: {UNKNOWN_REVIEW_REQUIRED}

Why developers miss it:
Unknown failures should not be guessed into a safe-fix route.

Smallest safe fix:
Check candidate {COVERAGE_GATE_REGRESSION}: Compare missing coverage lines to the PR diff and add focused tests for changed behavior.

Proof command:
bash quality.sh cov

Auto-fix status:
SDETKit will keep this review-first because the current evidence is not safe for automatic remediation.
"""


def _codes(payload: dict[str, object]) -> set[str]:
    diagnoses = payload.get("diagnoses", [])
    assert isinstance(diagnoses, list)
    return {
        str(item.get("code")) for item in diagnoses if isinstance(item, dict) and item.get("code")
    }


def _unknown_payload() -> dict[str, object]:
    return {
        "schema_version": adaptive_diagnosis.SCHEMA_VERSION,
        "ok": False,
        "status": "needs_fix",
        "risk_score": 45,
        "confidence": "high",
        "diagnosis_count": 1,
        "diagnoses": [
            {
                "code": UNKNOWN_REVIEW_REQUIRED,
                "severity": "high",
                "confidence": "medium",
                "title": "Failure needs human review",
                "diagnosis": "The log contains failure-like text that needs a human.",
                "why_developers_miss_it": "Unknown failures should not be guessed into a safe-fix route.",
                "recommended_fix": [
                    "Check candidate {COVERAGE_GATE_REGRESSION} before changing product code."
                ],
                "proof_commands": ["bash quality.sh cov"],
                "evidence": [
                    _matched_failure_signal("coverage-failure"),
                    _candidate_scenario(COVERAGE_GATE_REGRESSION),
                ],
            }
        ],
        "fix_plan": [
            {
                "code": UNKNOWN_REVIEW_REQUIRED,
                "safe_to_auto_fix": False,
                "reason": "unknown diagnosis remains review-first",
            }
        ],
    }


def _ruff_fixable_payload() -> dict[str, object]:
    return {
        "schema_version": adaptive_diagnosis.SCHEMA_VERSION,
        "ok": False,
        "status": "needs_fix",
        "risk_score": 35,
        "confidence": "high",
        "diagnosis_count": 1,
        "diagnoses": [
            {
                "code": RUFF_FIXABLE_LINT,
                "severity": "medium",
                "confidence": "high",
                "title": "Ruff found fixable lint",
                "why_developers_miss_it": "The import drift is mechanical.",
                "recommended_fix": ["Run ruff check --fix on the affected file."],
                "proof_commands": ["python -m ruff check tests/test_example.py"],
                "evidence": ["ruff_rules=I001"],
            }
        ],
        "fix_plan": [
            {
                "code": RUFF_FIXABLE_LINT,
                "safe_to_auto_fix": True,
            }
        ],
    }


def test_green_quality_gate_advisory_comment_does_not_create_unknown_review_required() -> None:
    payload = adaptive_diagnosis.analyze_evidence(log_text=GREEN_QUALITY_ADVISORY_COMMENT)

    assert payload["ok"] is True
    assert payload["status"] == "clear"
    assert payload["risk_score"] == 0
    assert payload["diagnosis_count"] == 0
    assert UNKNOWN_REVIEW_REQUIRED not in _codes(payload)


def test_green_quality_gate_advisory_comment_renders_no_adaptive_block() -> None:
    payload = adaptive_diagnosis.analyze_evidence(log_text=GREEN_QUALITY_ADVISORY_COMMENT)

    assert pr_quality_comment.render_adaptive_diagnosis_comment(payload) == ""


def test_green_quality_gate_with_exit_code_still_requires_review() -> None:
    payload = adaptive_diagnosis.analyze_evidence(
        log_text=GREEN_QUALITY_ADVISORY_COMMENT + "\nProcess completed with exit code 1\n"
    )

    assert payload["status"] in {"needs_attention", "needs_fix"}
    assert UNKNOWN_REVIEW_REQUIRED in _codes(payload)
    diagnosis = payload["diagnoses"][0]
    assert _matched_failure_signal("ci-exit-code") in diagnosis["evidence"]


def test_green_quality_gate_with_fast_gate_failure_still_requires_review() -> None:
    payload = adaptive_diagnosis.analyze_evidence(
        log_text=GREEN_QUALITY_ADVISORY_COMMENT + "\ngate fast: FAIL\nfailed_steps:\n- pytest\n"
    )

    assert payload["status"] in {"needs_attention", "needs_fix"}
    assert UNKNOWN_REVIEW_REQUIRED in _codes(payload)
    diagnosis = payload["diagnoses"][0]
    assert any(item.startswith("matched_failure_signals=") for item in diagnosis["evidence"])


def test_real_coverage_threshold_failure_still_routes_to_unknown_review() -> None:
    payload = adaptive_diagnosis.analyze_evidence(
        log_text="coverage fail under configured threshold"
    )

    assert payload["status"] in {"needs_attention", "needs_fix"}
    assert UNKNOWN_REVIEW_REQUIRED in _codes(payload)
    diagnosis = payload["diagnoses"][0]
    assert _matched_failure_signal("coverage-failure") in diagnosis["evidence"]


def test_review_first_unknown_comment_uses_human_review_heading() -> None:
    rendered = pr_quality_comment.render_adaptive_diagnosis_comment(_unknown_payload())

    assert "### Review-first Adaptive Diagnosis" in rendered
    assert "Human review route:" in rendered
    assert "Smallest safe fix:" not in rendered
    assert UNKNOWN_REVIEW_REQUIRED in rendered
    assert "SDETKit will keep this review-first" in rendered


def test_safe_mechanical_comment_keeps_smallest_safe_fix_heading() -> None:
    rendered = pr_quality_comment.render_adaptive_diagnosis_comment(_ruff_fixable_payload())

    assert "### Adaptive Diagnosis" in rendered
    assert "### Review-first Adaptive Diagnosis" not in rendered
    assert "Smallest safe fix:" in rendered
    assert "Human review route:" not in rendered
    assert "Ruff fixable lint route:" in rendered


def test_green_advisory_suppression_is_not_triggered_by_plain_unknown_failure() -> None:
    payload = adaptive_diagnosis.analyze_evidence(
        log_text="custom integrity report needs review\nProcess completed with exit code 42"
    )

    assert payload["status"] in {"needs_attention", "needs_fix"}
    assert UNKNOWN_REVIEW_REQUIRED in _codes(payload)
    diagnosis = payload["diagnoses"][0]
    assert _matched_failure_signal("ci-exit-code") in diagnosis["evidence"]


def test_green_advisory_suppression_requires_review_first_context() -> None:
    payload = adaptive_diagnosis.analyze_evidence(
        log_text="""
        quality.sh cov passed
        checks: lint + tests + coverage gate are green for this PR run
        ordinary operator note with no adaptive review-first diagnosis
        """
    )

    assert payload["status"] == "clear"
    assert payload["diagnosis_count"] == 0


def test_green_advisory_suppression_handles_coverage_regression_candidate_text() -> None:
    payload = adaptive_diagnosis.analyze_evidence(
        log_text=f"""
        quality.sh cov passed
        coverage: 97.10%
        checks: lint + tests + coverage gate are green for this PR run
        Adaptive Diagnosis
        status: needs_fix
        diagnosis code: {UNKNOWN_REVIEW_REQUIRED}
        Check candidate {COVERAGE_GATE_REGRESSION} before changing code.
        """
    )

    assert payload["status"] == "clear"
    assert payload["diagnosis_count"] == 0
