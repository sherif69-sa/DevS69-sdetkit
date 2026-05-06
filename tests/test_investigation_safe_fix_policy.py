from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit.investigation_evidence import build_investigation_evidence
from sdetkit.investigation_safe_fix_policy import route_investigation_safe_fix_policy


@pytest.mark.parametrize(
    ("classification", "route"),
    [
        ("PRE_COMMIT_FORMAT_DRIFT", "safe_mechanical_candidate_later"),
        ("RUFF_FIXABLE_LINT", "safe_mechanical_candidate_later"),
    ],
)
def test_mechanical_classes_are_candidates_later_but_not_auto_fix_now(classification, route):
    payload = route_investigation_safe_fix_policy(classification)

    assert payload["schema_version"] == "sdetkit.investigation.safe_fix_policy.v1"
    assert payload["diagnostic_only"] is True
    assert payload["automation_allowed"] is False
    assert payload["classification"] == classification
    assert payload["route"] == route
    assert payload["risk_level"] == "low"
    assert payload["candidate_later"] is True
    assert payload["auto_fix_allowed_now"] is False
    assert payload["safe_to_auto_fix"] is False
    assert payload["requires_human_review"] is True
    assert "Policy" in payload["blocking_reason"]


@pytest.mark.parametrize(
    ("classification", "route"),
    [
        ("GIT_BRANCH_DIVERGED", "command_guidance"),
        ("REMOTE_BRANCH_DRIFT", "sync_guidance"),
        ("MISSING_TEST_DEPENDENCY", "environment_guidance"),
        ("PYTHON_RUNTIME_COMPATIBILITY", "compatibility_pr"),
        ("LOCAL_ENVIRONMENT_FRICTION", "environment_guidance"),
        ("BROKEN_TEST_DOUBLE", "review_first_test_fix"),
        ("MISSING_PUBLIC_API_PARITY", "review_first_product_fix"),
        ("PRODUCT_LOGIC_FAILURE", "review_first_product_fix"),
        ("UNKNOWN_REVIEW_REQUIRED", "review_first_unknown"),
    ],
)
def test_review_first_classes_are_not_candidates(classification, route):
    payload = route_investigation_safe_fix_policy(classification)

    assert payload["diagnostic_only"] is True
    assert payload["automation_allowed"] is False
    assert payload["classification"] == classification
    assert payload["route"] == route
    assert payload["risk_level"] == "review_required"
    assert payload["candidate_later"] is False
    assert payload["auto_fix_allowed_now"] is False
    assert payload["safe_to_auto_fix"] is False
    assert payload["requires_human_review"] is True


def test_unknown_classification_falls_back_to_review_required():
    payload = route_investigation_safe_fix_policy("NEW_FAILURE_CLASS")

    assert payload["classification"] == "NEW_FAILURE_CLASS"
    assert payload["route"] == "review_first_unknown"
    assert payload["candidate_later"] is False
    assert payload["requires_human_review"] is True
    assert "Unrecognized" in payload["reason"]


def test_blank_classification_is_rejected():
    with pytest.raises(OSError, match="classification is required"):
        route_investigation_safe_fix_policy(" ")


def test_evidence_bundle_includes_mechanical_policy_route(tmp_path):
    out_dir = tmp_path / "evidence"

    payload = build_investigation_evidence(
        "PRE_COMMIT_FORMAT_DRIFT",
        "formatting",
        out_dir,
        root=tmp_path,
    )

    assert payload["automation_allowed"] is False
    assert payload["safe_to_auto_fix"] is False
    assert payload["candidate_status"] == "candidate_later_after_policy"
    assert payload["safe_fix_policy"]["route"] == "safe_mechanical_candidate_later"
    assert payload["safe_fix_policy"]["candidate_later"] is True
    assert payload["safe_fix_policy"]["auto_fix_allowed_now"] is False
    written = json.loads((out_dir / "investigation.json").read_text(encoding="utf-8"))
    assert written["safe_fix_policy"] == payload["safe_fix_policy"]
    freeze = (out_dir / "CANDIDATE_FREEZE.md").read_text(encoding="utf-8")
    assert "policy route: **safe_mechanical_candidate_later**" in freeze
    assert "Policy, proof history" in freeze


def test_evidence_bundle_includes_review_first_policy_route(tmp_path):
    out_dir = tmp_path / "evidence"

    payload = build_investigation_evidence(
        "MISSING_PUBLIC_API_PARITY",
        "netclient",
        out_dir,
        root=tmp_path,
    )

    assert payload["candidate_status"] == "review_required"
    assert payload["safe_fix_policy"]["route"] == "review_first_product_fix"
    assert payload["safe_fix_policy"]["candidate_later"] is False
    assert payload["safe_fix_policy"]["auto_fix_allowed_now"] is False
    audit = (out_dir / "AUDIT_RESULT.md").read_text(encoding="utf-8")
    assert "policy route: **review_first_product_fix**" in audit
    assert "Public API gaps are product changes." in audit
