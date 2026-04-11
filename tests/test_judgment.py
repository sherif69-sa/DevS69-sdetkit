from __future__ import annotations

from sdetkit.judgment import build_judgment


def test_judgment_emits_shared_shape() -> None:
    payload = build_judgment(
        workflow="inspect",
        findings=[
            {
                "id": "f1",
                "kind": "cross_file_mismatches",
                "severity": "high",
                "priority": 65,
                "why_it_matters": "Mismatch may indicate data loss risk.",
                "next_action": "Validate id coverage.",
            }
        ],
        supporting_evidence=[{"kind": "cross_file_mismatches", "value": 1}],
        conflicting_evidence=[],
        completeness=1.0,
        stability=0.7,
        previous_summary="stable",
        workflow_ok=True,
    )
    assert payload["schema_version"] == "sdetkit.judgment.v1"
    assert payload["status"] in {"pass", "watch", "fail"}
    assert "confidence" in payload
    assert "top_judgment" in payload
    assert isinstance(payload["recommendations"], list)
    assert "judgment_guideline" in payload
    assert "guideline_catalog" in payload


def test_judgment_contradictions_raise_priority() -> None:
    payload = build_judgment(
        workflow="inspect-compare",
        findings=[
            {
                "id": "f1",
                "kind": "id_drift",
                "severity": "high",
                "priority": 45,
                "why_it_matters": "ID drift detected.",
                "next_action": "Review ID drift.",
            }
        ],
        supporting_evidence=[{"kind": "id_drift", "value": 1}],
        conflicting_evidence=[{"id": "c1", "kind": "cross_surface_disagreement", "message": "conflict"}],
        completeness=1.0,
        stability=0.4,
        workflow_ok=False,
        blocking=True,
    )
    assert payload["contradictions"]
    assert payload["recommendations"][0]["id"] == "rec-contradictions"
    assert payload["judgment_guideline"]["id"] == "guideline-contradictions-first"


def test_judgment_non_ok_without_blocking_is_watch() -> None:
    payload = build_judgment(
        workflow="inspect",
        findings=[{"id": "f1", "kind": "minor", "severity": "medium", "priority": 10, "why_it_matters": "minor"}],
        supporting_evidence=[{"kind": "minor", "value": 1}],
        conflicting_evidence=[],
        completeness=1.0,
        stability=0.7,
        workflow_ok=False,
        blocking=False,
    )
    assert payload["status"] == "watch"


def test_judgment_guideline_matrix_for_key_scenarios() -> None:
    fail_payload = build_judgment(
        workflow="review",
        findings=[{"id": "f1", "kind": "risk", "severity": "high", "priority": 75, "why_it_matters": "risk"}],
        supporting_evidence=[{"kind": "risk", "value": 1}],
        conflicting_evidence=[],
        completeness=0.8,
        stability=0.6,
        workflow_ok=False,
        blocking=True,
    )
    assert fail_payload["status"] == "fail"
    assert fail_payload["judgment_guideline"]["id"] == "guideline-blocking-risk"

    watch_payload = build_judgment(
        workflow="review",
        findings=[{"id": "f1", "kind": "minor", "severity": "low", "priority": 15, "why_it_matters": "minor"}],
        supporting_evidence=[],
        conflicting_evidence=[{"id": "c1", "kind": "disagreement"}],
        completeness=0.4,
        stability=0.3,
        workflow_ok=False,
        blocking=False,
    )
    assert watch_payload["status"] == "watch"
    assert watch_payload["judgment_guideline"]["id"] == "guideline-contradictions-first"

    pass_payload = build_judgment(
        workflow="review",
        findings=[],
        supporting_evidence=[{"kind": "ok", "value": 1}],
        conflicting_evidence=[],
        completeness=1.0,
        stability=1.0,
        workflow_ok=True,
        blocking=False,
    )
    assert pass_payload["status"] == "pass"
    assert pass_payload["confidence"]["level"] == "high"
    assert pass_payload["judgment_guideline"]["id"] == "guideline-pass-high-confidence"
