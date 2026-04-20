from __future__ import annotations

from scripts import check_phase4_governance_contract as contract


def test_policy_compatibility_validation_rejects_missing_required_fields() -> None:
    failures = contract._validate_policy_and_compatibility(
        governance_checks=[
            {
                "check_id": "c1",
                "status": "pass",
                "reason_code": "",
                "evidence_refs": [],
                "owner_hint": "ops",
                "policy_domain": "contract",
            }
        ],
        policy_decisions=[
            {
                "decision_id": "d1",
                "policy_id": "p1",
                "disposition": "accepted",
                "rationale_code": "",
                "impact_tier": "",
            }
        ],
        compatibility_contract={
            "supported_tiers": ["tier0"],
            "deprecation_boundaries": [],
            "compatibility_guards": [],
        },
        release_evidence_contract={"required_artifacts": [], "retention_window_days": 0},
    )

    assert any("reason_code" in failure for failure in failures)
    assert any("rationale_code" in failure for failure in failures)
    assert any("impact_tier" in failure for failure in failures)
    assert any("deprecation_boundaries" in failure for failure in failures)
    assert any("required_artifacts" in failure for failure in failures)
    assert any("retention_window_days" in failure for failure in failures)


def test_policy_compatibility_validation_accepts_valid_payload() -> None:
    failures = contract._validate_policy_and_compatibility(
        governance_checks=[
            {
                "check_id": "c1",
                "status": "pass",
                "reason_code": "contract_satisfied",
                "evidence_refs": ["docs/index.md"],
                "owner_hint": "ops",
                "policy_domain": "contract",
            }
        ],
        policy_decisions=[
            {
                "decision_id": "d1",
                "policy_id": "p1",
                "disposition": "accepted",
                "rationale_code": "audit_readiness",
                "impact_tier": "now",
            }
        ],
        compatibility_contract={
            "supported_tiers": ["tier0"],
            "deprecation_boundaries": ["notice"],
            "compatibility_guards": ["make phase4-governance-contract"],
        },
        release_evidence_contract={
            "required_artifacts": ["docs/index.md"],
            "retention_window_days": 30,
        },
    )
    assert failures == []
