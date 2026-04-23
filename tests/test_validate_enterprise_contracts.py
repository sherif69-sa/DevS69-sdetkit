from __future__ import annotations

import importlib.util
from pathlib import Path


_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_enterprise_contracts.py"
_SPEC = importlib.util.spec_from_file_location("validate_enterprise_contracts_script", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
validate_enterprise_contracts = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(validate_enterprise_contracts)


def test_adaptive_postcheck_contract_requires_new_checks() -> None:
    payload = {
        "owner_routing": {
            "adaptive_learning_precision_ready": {
                "owner": "review-intelligence",
                "severity": "high",
                "sla": "72h",
            }
        },
        "scenarios": {
            "fast": {
                "enabled_checks": ["adaptive_learning_precision_ready"],
                "minimum_pr_outcome_feedback": 3,
                "minimum_mistake_learning_event": 3,
                "minimum_learning_signal_total": 6,
            },
            "balanced": {
                "enabled_checks": ["adaptive_learning_precision_ready"],
                "minimum_pr_outcome_feedback": 5,
                "minimum_mistake_learning_event": 5,
                "minimum_learning_signal_total": 10,
            },
            "strict": {
                "enabled_checks": ["adaptive_learning_precision_ready"],
                "minimum_pr_outcome_feedback": 5,
                "minimum_mistake_learning_event": 5,
                "minimum_learning_signal_total": 10,
            },
        }
    }
    errors = validate_enterprise_contracts._validate_adaptive_postcheck_contract(
        payload, "docs/contracts/adaptive-postcheck-scenarios.v1.json"
    )
    assert any("pr_outcome_feedback_present" in item for item in errors)
    assert any("mistake_learning_signal_depth" in item for item in errors)


def test_adaptive_postcheck_contract_accepts_valid_profile_shape() -> None:
    payload = {
        "owner_routing": {
            "pr_outcome_feedback_present": {
                "owner": "review-intelligence",
                "severity": "high",
                "sla": "72h",
            },
            "mistake_learning_signal_depth": {
                "owner": "quality-intelligence",
                "severity": "high",
                "sla": "72h",
            },
            "adaptive_learning_precision_ready": {
                "owner": "review-intelligence",
                "severity": "high",
                "sla": "72h",
            },
        },
        "scenarios": {
            "fast": {
                "enabled_checks": [
                    "pr_outcome_feedback_present",
                    "mistake_learning_signal_depth",
                    "adaptive_learning_precision_ready",
                ],
                "minimum_pr_outcome_feedback": 3,
                "minimum_mistake_learning_event": 3,
                "minimum_learning_signal_total": 6,
            },
            "balanced": {
                "enabled_checks": [
                    "pr_outcome_feedback_present",
                    "mistake_learning_signal_depth",
                    "adaptive_learning_precision_ready",
                ],
                "minimum_pr_outcome_feedback": 5,
                "minimum_mistake_learning_event": 5,
                "minimum_learning_signal_total": 10,
            },
            "strict": {
                "enabled_checks": [
                    "pr_outcome_feedback_present",
                    "mistake_learning_signal_depth",
                    "adaptive_learning_precision_ready",
                ],
                "minimum_pr_outcome_feedback": 5,
                "minimum_mistake_learning_event": 5,
                "minimum_learning_signal_total": 10,
            },
        }
    }
    errors = validate_enterprise_contracts._validate_adaptive_postcheck_contract(
        payload, "docs/contracts/adaptive-postcheck-scenarios.v1.json"
    )
    assert errors == []


def test_adaptive_postcheck_contract_requires_owner_routing() -> None:
    payload = {"scenarios": {}}
    errors = validate_enterprise_contracts._validate_adaptive_postcheck_contract(
        payload, "docs/contracts/adaptive-postcheck-scenarios.v1.json"
    )
    assert any("owner_routing" in item for item in errors)


def test_adaptive_scenario_database_sample_requires_learning_and_kind_signals() -> None:
    payload = {
        "summary": {
            "kinds": {
                "adaptive_pr_reviewer_matrix": 0,
                "pr_outcome_feedback": 0,
                "mistake_learning_event": 0,
                "reviewer_agent_handoff": 0,
            },
            "adaptive_learning": {
                "pr_outcome_feedback": 1,
                "mistake_learning_event": 1,
                "learning_signal_total": 2,
                "learning_coverage_score": 150,
                "precision_ready": "yes",
            },
        }
    }
    errors = validate_enterprise_contracts._validate_adaptive_scenario_database_sample(
        payload, Path("docs/artifacts/adaptive-scenario-database-2026-04-23.json")
    )
    assert any("summary.kinds" in item for item in errors)
    assert any("learning_coverage_score" in item for item in errors)
    assert any("precision_ready" in item for item in errors)


def test_adaptive_scenario_database_sample_accepts_valid_shape() -> None:
    payload = {
        "summary": {
            "kinds": {
                "adaptive_pr_reviewer_matrix": 1080,
                "pr_outcome_feedback": 6,
                "mistake_learning_event": 7,
                "reviewer_agent_handoff": 9,
            },
            "adaptive_learning": {
                "pr_outcome_feedback": 6,
                "mistake_learning_event": 7,
                "learning_signal_total": 13,
                "learning_coverage_score": 65,
                "precision_ready": True,
            },
        }
    }
    errors = validate_enterprise_contracts._validate_adaptive_scenario_database_sample(
        payload, Path("docs/artifacts/adaptive-scenario-database-2026-04-23.json")
    )
    assert errors == []


def test_adaptive_scenario_sample_with_fallback_prefers_valid_latest(monkeypatch) -> None:
    latest = Path("/tmp/adaptive-scenario-database-latest.json")
    payload = {"schema_version": "sdetkit.adaptive-scenario-database.v1", "summary": {"kinds": {}}}
    monkeypatch.setattr(validate_enterprise_contracts, "_latest_sample", lambda _prefix: latest)
    monkeypatch.setattr(validate_enterprise_contracts, "_load_json", lambda _path: payload)
    monkeypatch.setattr(
        validate_enterprise_contracts, "_validate_adaptive_scenario_database_sample", lambda *_args: []
    )
    monkeypatch.setattr(
        validate_enterprise_contracts,
        "_fresh_adaptive_scenario_database_sample",
        lambda: (_ for _ in ()).throw(AssertionError("fresh sample should not be built")),
    )

    loaded, rel, errors = validate_enterprise_contracts._adaptive_scenario_sample_with_fallback()
    assert loaded is payload
    assert rel == latest
    assert errors == []


def test_adaptive_scenario_sample_with_fallback_builds_when_latest_invalid(monkeypatch) -> None:
    latest = Path("/tmp/adaptive-scenario-database-latest.json")
    stale_payload = {"schema_version": "sdetkit.adaptive-scenario-database.v1", "summary": {"kinds": {}}}
    fresh_payload = {
        "schema_version": "sdetkit.adaptive-scenario-database.v1",
        "summary": {"kinds": {"adaptive_pr_reviewer_matrix": 1}},
    }
    monkeypatch.setattr(validate_enterprise_contracts, "_latest_sample", lambda _prefix: latest)
    monkeypatch.setattr(validate_enterprise_contracts, "_load_json", lambda _path: stale_payload)
    monkeypatch.setattr(
        validate_enterprise_contracts,
        "_validate_adaptive_scenario_database_sample",
        lambda *_args: ["stale"],
    )
    monkeypatch.setattr(
        validate_enterprise_contracts, "_fresh_adaptive_scenario_database_sample", lambda: fresh_payload
    )

    loaded, rel, errors = validate_enterprise_contracts._adaptive_scenario_sample_with_fallback()
    assert loaded is fresh_payload
    assert rel == Path("build/generated-adaptive-scenario-database.json")
    assert errors == []
