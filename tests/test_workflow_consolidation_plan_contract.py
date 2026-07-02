from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "check_workflow_consolidation_plan.py"
TOPOLOGY = ROOT / "docs" / "contracts" / "workflow-topology.v1.json"
PLAN = ROOT / "docs" / "contracts" / "workflow-consolidation-plan.v1.json"


def _load_checker() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_workflow_consolidation_plan", CHECKER)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _contracts() -> tuple[dict, dict]:
    topology = json.loads(TOPOLOGY.read_text(encoding="utf-8"))
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    return topology, plan


def _codes(report: dict) -> set[str]:
    return {str(item.get("code")) for item in report["violations"]}


def test_repository_consolidation_plan_has_complete_parity() -> None:
    module = _load_checker()
    topology, plan = _contracts()

    report = module.evaluate_plan(topology, plan)

    assert report["status"] == "passed", report["violations"]
    assert report["metrics"] == {
        "workflow_count": 57,
        "primary_workflow_count": 12,
        "merge_bundle_workflow_count": 24,
        "retirement_candidate_workflow_count": 7,
        "standalone_supporting_workflow_count": 14,
        "compatibility_bridge_workflow_count": 3,
        "reusable_workflow_count": 1,
        "trusted_publisher_workflow_count": 2,
    }
    assert report["authority_boundary"]["workflow_retirement_allowed"] is False
    assert report["authority_boundary"]["merge_authorized"] is False


def test_every_workflow_has_exactly_one_disposition() -> None:
    module = _load_checker()
    topology, plan = _contracts()
    report = module.evaluate_plan(topology, plan)

    inventory = {
        item.removeprefix(".github/workflows/") for item in topology["inventory"]
    }
    assert set(report["classifications"]) == inventory
    assert all(
        row["disposition"]
        in {"primary", "merge_bundle", "retirement_candidate", "standalone_supporting"}
        for row in report["classifications"].values()
    )


def test_missing_workflow_classification_is_rejected() -> None:
    module = _load_checker()
    topology, plan = _contracts()
    broken = deepcopy(plan)
    broken["standalone_supporting"].remove("release-candidate.yml")

    report = module.evaluate_plan(topology, broken)

    assert "workflow_disposition_coverage_mismatch" in _codes(report)
    violation = next(
        item
        for item in report["violations"]
        if item["code"] == "workflow_disposition_coverage_mismatch"
    )
    assert violation["missing"] == ["release-candidate.yml"]


def test_duplicate_workflow_disposition_is_rejected() -> None:
    module = _load_checker()
    topology, plan = _contracts()
    broken = deepcopy(plan)
    broken["candidate_retire_or_absorb"].append("release-candidate.yml")

    report = module.evaluate_plan(topology, broken)

    assert "workflow_disposition_overlap" in _codes(report)


def test_stale_declared_workflow_count_is_rejected() -> None:
    module = _load_checker()
    topology, plan = _contracts()
    broken = deepcopy(plan)
    broken["current_workflow_count"] = 56

    report = module.evaluate_plan(topology, broken)

    assert "workflow_count_drift" in _codes(report)


def test_primary_anchor_or_budget_drift_is_rejected() -> None:
    module = _load_checker()
    topology, plan = _contracts()
    broken = deepcopy(plan)
    broken["keep_primary"] = [
        item for item in broken["keep_primary"] if item != "ci.yml"
    ]
    broken["target_primary_workflow_count"] = 11

    report = module.evaluate_plan(topology, broken)

    assert "primary_anchor_drift" in _codes(report)
    assert "primary_target_drift" in _codes(report)


def test_zero_signal_issue_creation_must_remain_disabled() -> None:
    module = _load_checker()
    topology, plan = _contracts()
    broken = deepcopy(plan)
    broken["zero_signal_issue_policy"][
        "create_issue_when_actionable_finding_count_is_zero"
    ] = True

    report = module.evaluate_plan(topology, broken)

    assert "zero_signal_issue_creation_not_prohibited" in _codes(report)


def test_metadata_classifications_cannot_reference_unknown_workflows() -> None:
    module = _load_checker()
    topology, plan = _contracts()
    broken = deepcopy(plan)
    broken["trusted_publishers"].append("missing-publisher.yml")

    report = module.evaluate_plan(topology, broken)

    assert "classification_references_unknown_workflow" in _codes(report)
