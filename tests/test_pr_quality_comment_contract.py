from __future__ import annotations

from sdetkit import adaptive_diagnosis, pr_quality_comment


def _snake(*parts: str) -> str:
    return "_".join(parts)


UNKNOWN_REVIEW_REQUIRED = _snake("UNKNOWN", "REVIEW", "REQUIRED")
RUFF_FIXABLE_LINT = _snake("RUFF", "FIXABLE", "LINT")


def _payload(code: str, status: str = "needs_fix", safe: bool = False) -> dict[str, object]:
    return {
        "schema_version": adaptive_diagnosis.SCHEMA_VERSION,
        "ok": status in {"clear", "monitor"},
        "status": status,
        "risk_score": 45 if status == "needs_fix" else 5,
        "confidence": "high",
        "diagnosis_count": 1,
        "diagnoses": [
            {
                "code": code,
                "severity": "high" if status == "needs_fix" else "low",
                "confidence": "high",
                "title": "Synthetic diagnosis",
                "diagnosis": "Synthetic diagnosis for comment rendering.",
                "why_developers_miss_it": "The route can be confused with a safe fix.",
                "recommended_fix": ["Review the evidence and choose the smallest safe action."],
                "proof_commands": ["python -m pytest -q tests/test_example.py"],
                "evidence": ["synthetic evidence"],
            }
        ],
        "fix_plan": [
            {
                "code": code,
                "safe_to_auto_fix": safe,
                "reason": "synthetic test plan",
            }
        ],
    }


def test_clear_payload_has_no_comment_contract() -> None:
    payload = {
        "schema_version": adaptive_diagnosis.SCHEMA_VERSION,
        "ok": True,
        "status": "clear",
        "diagnosis_count": 0,
        "diagnoses": [],
        "fix_plan": [],
    }

    contract = pr_quality_comment.diagnosis_comment_contract(payload)

    assert contract["should_render"] is False
    assert contract["reason"] == "No actionable adaptive diagnosis comment is needed."
    assert pr_quality_comment.render_adaptive_diagnosis_comment(payload) == ""


def test_monitor_payload_has_no_comment_contract() -> None:
    payload = _payload(UNKNOWN_REVIEW_REQUIRED, status="monitor")

    contract = pr_quality_comment.diagnosis_comment_contract(payload)

    assert contract["should_render"] is False
    assert pr_quality_comment.render_adaptive_diagnosis_comment(payload) == ""


def test_unknown_review_required_contract_is_review_first() -> None:
    payload = _payload(UNKNOWN_REVIEW_REQUIRED)

    contract = pr_quality_comment.diagnosis_comment_contract(payload)

    assert contract["should_render"] is True
    assert contract["review_first"] is True
    assert contract["safe_to_auto_fix"] is False
    assert contract["heading"] == "### Review-first Adaptive Diagnosis"
    assert contract["route_heading"] == "Human review route:"


def test_unknown_review_required_comment_uses_human_review_language() -> None:
    rendered = pr_quality_comment.render_adaptive_diagnosis_comment(
        _payload(UNKNOWN_REVIEW_REQUIRED)
    )

    assert "### Review-first Adaptive Diagnosis" in rendered
    assert "Human review route:" in rendered
    assert "Smallest safe fix:" not in rendered
    assert "SDETKit will keep this review-first" in rendered


def test_safe_ruff_contract_remains_mechanical() -> None:
    payload = _payload(RUFF_FIXABLE_LINT, safe=True)

    contract = pr_quality_comment.diagnosis_comment_contract(payload)

    assert contract["should_render"] is True
    assert contract["review_first"] is False
    assert contract["safe_to_auto_fix"] is True
    assert contract["heading"] == "### Adaptive Diagnosis"
    assert contract["route_heading"] == "Smallest safe fix:"


def test_safe_ruff_comment_keeps_ruff_route() -> None:
    rendered = pr_quality_comment.render_adaptive_diagnosis_comment(
        _payload(RUFF_FIXABLE_LINT, safe=True)
    )

    assert "### Adaptive Diagnosis" in rendered
    assert "Ruff fixable lint route:" in rendered
    assert "Smallest safe fix:" in rendered
    assert "Human review route:" not in rendered


def test_comment_contract_handles_missing_fix_plan() -> None:
    payload = _payload(UNKNOWN_REVIEW_REQUIRED)
    payload["fix_plan"] = []

    contract = pr_quality_comment.diagnosis_comment_contract(payload)

    assert contract["should_render"] is True
    assert contract["review_first"] is True
    assert contract["safe_to_auto_fix"] is False


def test_comment_contract_uses_primary_diagnosis_only() -> None:
    payload = _payload(UNKNOWN_REVIEW_REQUIRED)
    diagnoses = payload["diagnoses"]
    assert isinstance(diagnoses, list)
    diagnoses.append(
        {
            "code": RUFF_FIXABLE_LINT,
            "severity": "medium",
            "confidence": "high",
            "title": "Secondary",
        }
    )

    contract = pr_quality_comment.diagnosis_comment_contract(payload)

    assert contract["code"] == UNKNOWN_REVIEW_REQUIRED
    assert contract["review_first"] is True
