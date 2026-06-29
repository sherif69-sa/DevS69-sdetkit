from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit.benchmark_control_scorecard import (
    SCHEMA_VERSION,
    build_scorecard,
    load_benchmark_reports,
    main,
    render_markdown,
)
from sdetkit.replayable_benchmark_harness import (
    build_execution_plan_handoff_benchmark_report,
    load_execution_plan_handoff_scenarios,
)

FIXTURES = Path("tests/fixtures/remediation_benchmark")
EXECUTION_PLAN_SCENARIOS = [
    FIXTURES / "execution_plan_handoff_observed_oracle.json",
    FIXTURES / "execution_plan_handoff_not_provided.json",
    FIXTURES / "execution_plan_handoff_authority_unsafe.json",
]


def _base_report(*, status: str = "passed") -> dict:
    passed = 3 if status == "passed" else 2
    failed = 0 if status == "passed" else 1
    return {
        "schema_version": "sdetkit.replayable_benchmark_harness.v1",
        "status": status,
        "scenario_count": 3,
        "passed_count": passed,
        "failed_count": failed,
        "required_contract": {
            "all_required_present": True,
            "all_required_passed": status == "passed",
        },
        "safety_boundary": {
            "preserved": True,
            "automation_allowed_count": 0,
            "merge_authorized_count": 0,
            "semantic_equivalence_claimed_count": 0,
        },
    }


def _execution_plan_report() -> dict:
    return build_execution_plan_handoff_benchmark_report(
        load_execution_plan_handoff_scenarios(EXECUTION_PLAN_SCENARIOS)
    )


def _write(path: Path, payload: dict) -> Path:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def test_scorecard_aggregates_distinct_benchmark_modes(tmp_path: Path) -> None:
    base_path = _write(tmp_path / "base.json", _base_report())
    plan_path = _write(tmp_path / "plan.json", _execution_plan_report())

    reports = load_benchmark_reports([base_path, plan_path])
    scorecard = build_scorecard(reports)

    assert scorecard["schema_version"] == SCHEMA_VERSION
    assert scorecard["status"] == "passed"
    assert scorecard["overall_score"] == 100.0
    assert scorecard["report_count"] == 2
    assert scorecard["passed_report_count"] == 2
    assert scorecard["scenario_count"] == 6
    assert scorecard["passed_scenario_count"] == 6
    assert scorecard["failed_scenario_count"] == 0
    assert scorecard["scenario_pass_rate"] == 1.0
    assert scorecard["required_contract_pass_count"] == 2
    assert scorecard["boundary_preserved_count"] == 2
    assert scorecard["benchmark_modes"] == [
        "default_fixture",
        "diagnostic_execution_plan_handoff_fixture",
    ]
    assert scorecard["expanded_authority_fields"] == []

    boundary = scorecard["decision_boundary"]
    assert boundary["reporting_only"] is True
    assert boundary["current_pr_decision_input"] is False
    assert boundary["automation_allowed"] is False
    assert boundary["patch_application_allowed"] is False
    assert boundary["merge_authorized"] is False
    assert boundary["semantic_equivalence_proven"] is False
    assert boundary["executes_plan"] is False
    assert boundary["executes_patch"] is False


def test_scorecard_surfaces_failed_contract_without_authorizing_action(
    tmp_path: Path,
) -> None:
    failed_path = _write(tmp_path / "failed.json", _base_report(status="failed"))

    scorecard = build_scorecard(load_benchmark_reports([failed_path]))

    assert scorecard["status"] == "failed"
    assert scorecard["overall_score"] == 41.67
    assert scorecard["failed_report_count"] == 1
    assert scorecard["failed_scenario_count"] == 1
    assert scorecard["dimension_scores"] == {
        "report_status": 0.0,
        "required_contracts": 0.0,
        "safety_boundaries": 100.0,
        "scenario_health": 66.67,
    }
    assert scorecard["decision_boundary"]["automation_allowed"] is False
    assert scorecard["decision_boundary"]["merge_authorized"] is False


def test_scorecard_rejects_duplicate_report_identity(tmp_path: Path) -> None:
    first = _write(tmp_path / "first.json", _base_report())
    second = _write(tmp_path / "second.json", _base_report())

    with pytest.raises(
        ValueError,
        match="duplicate benchmark report identity",
    ):
        load_benchmark_reports([first, second])


def test_scorecard_detects_authority_expansion(tmp_path: Path) -> None:
    unsafe = _base_report()
    unsafe["safety_boundary"]["automation_allowed_count"] = 1
    unsafe["safety_boundary"]["preserved"] = True
    path = _write(tmp_path / "unsafe.json", unsafe)

    scorecard = build_scorecard(load_benchmark_reports([path]))

    assert scorecard["status"] == "failed"
    assert scorecard["boundary_preserved_count"] == 0
    assert scorecard["expanded_authority_fields"] == ["automation_allowed_count"]
    assert scorecard["dimension_scores"]["safety_boundaries"] == 0.0


def test_scorecard_markdown_and_cli_are_deterministic(
    tmp_path: Path,
    capsys,
) -> None:
    base_path = _write(tmp_path / "base.json", _base_report())
    plan_path = _write(tmp_path / "plan.json", _execution_plan_report())
    out_dir = tmp_path / "scorecard"

    rc = main(
        [
            "--benchmark-report",
            str(base_path),
            "--benchmark-report",
            str(plan_path),
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    saved = json.loads((out_dir / "benchmark-control-scorecard.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "benchmark-control-scorecard.md").read_text(encoding="utf-8")

    assert printed == saved
    assert saved["status"] == "passed"
    assert "# Benchmark Control Scorecard" in markdown
    assert "| `report_status` | `100.00` |" in markdown
    assert "Current PR decision input: `false`" in markdown
    assert "Merge authorized: `false`" in markdown
    assert render_markdown(saved) == markdown
