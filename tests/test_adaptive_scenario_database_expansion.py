from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_module():
    module_path = Path("scripts/build_adaptive_scenario_database.py")
    spec = spec_from_file_location("build_adaptive_scenario_database", module_path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_adaptive_reviewer_matrix_has_expected_dimensions() -> None:
    mod = _load_module()
    rows = mod._generate_adaptive_reviewer_matrix()

    assert len(rows) == 7560
    assert rows[0]["kind"] == "adaptive_reviewer_matrix"
    assert rows[0]["phase_id"] == 1
    assert rows[0]["intelligence_mode"] == "reactive"


def test_build_db_sets_higher_target_and_meets_it_for_repo() -> None:
    mod = _load_module()
    payload = mod.build_db(Path("."))

    assert payload["summary"]["target_minimum"] == 3000
    assert payload["summary"]["total_scenarios"] >= 3000
    assert payload["summary"]["meets_target"] is True
    assert payload["summary"]["kinds"].get("adaptive_reviewer_matrix", 0) == 7560
