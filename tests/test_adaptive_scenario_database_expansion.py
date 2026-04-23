from __future__ import annotations

import json
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


def test_adaptive_pr_reviewer_matrix_has_expected_dimensions() -> None:
    mod = _load_module()
    rows = mod._generate_adaptive_pr_reviewer_matrix()

    assert len(rows) == 1080
    assert rows[0]["kind"] == "adaptive_pr_reviewer_matrix"
    assert rows[0]["phase_id"] == 1
    assert rows[0]["reviewer_mode"] == "human-first"


def test_build_db_sets_higher_target_and_meets_it_for_repo() -> None:
    mod = _load_module()
    payload = mod.build_db(Path("."))

    assert payload["summary"]["target_minimum"] == 3000
    assert payload["summary"]["total_scenarios"] >= 3000
    assert payload["summary"]["meets_target"] is True
    assert payload["summary"]["kinds"].get("adaptive_reviewer_matrix", 0) == 7560
    assert payload["summary"]["kinds"].get("adaptive_pr_reviewer_matrix", 0) == 1080
    assert payload["summary"]["kinds"].get("reviewer_agent_handoff", 0) > 0
    assert payload["summary"]["kinds"].get("mistake_learning_event", 0) > 0
    assert payload["summary"]["kinds"].get("pr_outcome_feedback", 0) > 0
    learning = payload["summary"].get("adaptive_learning", {})
    assert learning.get("learning_signal_total", 0) >= 10
    assert isinstance(learning.get("precision_ready"), bool)


def test_mistake_learning_events_are_extracted_from_artifact_failures(tmp_path: Path) -> None:
    mod = _load_module()
    artifact = tmp_path / "docs/artifacts/adaptive-postcheck-2026-04-23.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        json.dumps(
            {
                "summary": {"failed_required": 2, "failed_warn": 1},
                "failed_steps": ["release_gate"],
                "doctor": {"failed_check_ids": ["pyproject"]},
                "checks": [
                    {"check": "intelligence_matrix_present", "passed": False},
                    {"check": "scenario_database_minimum_coverage", "passed": True},
                ],
            }
        ),
        encoding="utf-8",
    )

    rows = mod._extract_mistake_learning_scenarios(tmp_path)
    scenario_ids = {row["scenario_id"] for row in rows}
    assert any("failed-step-release-gate" in sid for sid in scenario_ids)
    assert any("doctor-failed-pyproject" in sid for sid in scenario_ids)
    assert any("check-failed-intelligence-matrix-present" in sid for sid in scenario_ids)


def test_pr_outcome_feedback_is_extracted_from_adaptive_artifact(tmp_path: Path) -> None:
    mod = _load_module()
    artifact = tmp_path / "docs/artifacts/adaptive-postcheck-2026-04-23.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        json.dumps(
            {
                "status": "watch",
                "ok": False,
                "summary": {
                    "confidence_band": "manual-review",
                    "failed_required": 1,
                },
                "confidence_guidance": {"routing": "manual-reviewer-required"},
            }
        ),
        encoding="utf-8",
    )
    rows = mod._extract_pr_outcome_feedback_scenarios(tmp_path)
    scenario_ids = {row["scenario_id"] for row in rows}
    assert any("status::watch" in sid for sid in scenario_ids)
    assert any("ok::false" in sid for sid in scenario_ids)
    assert any("confidence_band::manual-review" in sid for sid in scenario_ids)
    assert any("routing::manual-reviewer-required" in sid for sid in scenario_ids)
