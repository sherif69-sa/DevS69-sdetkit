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

    assert payload["ok"] is True
    assert all(payload["checks"].values())
    assert payload["observed"]["source_module_count"] == 487
    assert payload["observed"]["typing_debt_module_count"] == 474
    assert (
        "sdetkit.failure_vector_adapters" in payload["observed"]["explicitly_type_checked_modules"]
    )
    assert payload["typing_debt_inventory"]["module_count"] == 474
    assert len(payload["typing_debt_inventory"]["modules"]) == 474


def test_quality_truth_baseline_keeps_unfinished_migrations_visible() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    assert contract["status"] == "staged_migration_visible"
    assert contract["typing"]["blanket_package_suppression_present"] is True
    assert contract["typing"]["migration_complete"] is False
    assert contract["typing"]["new_unrecorded_suppression_allowed"] is False
    assert contract["coverage"]["whole_package"]["measurement_required"] is True
    assert contract["coverage"]["whole_package"]["blocking_threshold_reviewed"] is True
    assert contract["coverage"]["whole_package"]["current_percent"] == 87.89
    assert contract["coverage"]["critical_spine"]["observed_percent"] == 96.69
    assert contract["runtime"]["python_310_full_ci_proven"] is False


def test_quality_truth_baseline_denies_false_green_shortcuts() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    assert contract["authority_boundary"] == {
        "tests_may_be_weakened": False,
        "quality_gates_may_be_hidden": False,
        "unmeasured_quality_may_be_claimed": False,
    }
