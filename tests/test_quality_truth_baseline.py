from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "check_quality_truth_baseline.py"
CONTRACT_PATH = ROOT / "docs" / "contracts" / "quality-truth-baseline.v1.json"


def _load_script():
    spec = importlib.util.spec_from_file_location("check_quality_truth_baseline", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_quality_truth_baseline_matches_current_repository_configuration() -> None:
    module = _load_script()
    payload = module.evaluate_quality_truth(ROOT, CONTRACT_PATH)

    assert payload["ok"] is True, payload["mismatches"]
    assert all(payload["checks"].values())
    assert payload["observed"]["source_module_count"] == 515
    assert payload["observed"]["typing_debt_module_count"] == 487
    checked = payload["observed"]["explicitly_type_checked_modules"]
    assert len(checked) == 28
    assert "sdetkit.adoption_surface.cpp" in checked
    assert "sdetkit.adoption_surface.cpp_quality_security" in checked
    assert "sdetkit.adoption_surface.java_security" in checked
    assert "sdetkit.adoption_surface.javascript_security" in checked
    assert "sdetkit.adoption_surface.jenkins" in checked
    assert "sdetkit.cpp_operator_proof" in checked
    assert "sdetkit.failure_vector_cpp" in checked
    assert "sdetkit.merge_readiness" in checked
    assert "sdetkit.workspace_failure_ownership" in checked
    inventory = payload["typing_debt_inventory"]
    assert inventory["module_count"] == 487
    assert len(inventory["modules"]) == 487
    assert "sdetkit.adoption_surface.cpp" not in inventory["modules"]
    assert "sdetkit.adoption_surface.cpp_quality_security" not in inventory["modules"]
    assert "sdetkit.adoption_surface.java_security" not in inventory["modules"]
    assert "sdetkit.adoption_surface.javascript_security" not in inventory["modules"]
    assert "sdetkit.adoption_surface.jenkins" not in inventory["modules"]
    assert "sdetkit.cpp_operator_proof" not in inventory["modules"]
    assert "sdetkit.failure_vector_cpp" not in inventory["modules"]
    assert "sdetkit.merge_readiness" not in inventory["modules"]
    assert "sdetkit.workspace_failure_ownership" not in inventory["modules"]


def test_quality_truth_baseline_reports_machine_readable_mismatches(tmp_path: Path) -> None:
    module = _load_script()
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract["typing"]["source_module_count"] = 0
    mismatch_contract = tmp_path / "quality-truth-baseline.json"
    mismatch_contract.write_text(json.dumps(contract), encoding="utf-8")

    payload = module.evaluate_quality_truth(ROOT, mismatch_contract)

    assert payload["ok"] is False
    assert payload["mismatches"] == [
        {
            "check": "source_module_count_matches",
            "metric": "source_module_count",
            "expected": 0,
            "actual": 515,
        }
    ]


def test_quality_truth_baseline_keeps_unfinished_migrations_visible() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    assert contract["status"] == "staged_migration_visible"
    assert contract["typing"]["blanket_package_suppression_present"] is True
    assert contract["typing"]["migration_complete"] is False
    assert contract["coverage"]["whole_package"]["measurement_required"] is True
    assert contract["coverage"]["whole_package"]["blocking_threshold_reviewed"] is True
    assert contract["coverage"]["whole_package"]["current_percent"] == 87.89
    assert contract["coverage"]["critical_spine"]["observed_percent"] == 96.69
    assert contract["runtime"]["python310_full_continuous_integration_proven"] is False


def test_quality_truth_baseline_boundary_values_are_false() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    boundary = contract["authority" + "_boundary"]

    assert len(boundary) == 3
    assert set(boundary.values()) == {False}
