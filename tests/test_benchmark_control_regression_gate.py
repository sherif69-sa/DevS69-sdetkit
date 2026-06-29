from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from sdetkit.benchmark_control_regression_gate import (
    BASELINE_SCHEMA_VERSION,
    DEFAULT_BASELINE_PATH,
    SCHEMA_VERSION,
    build_regression_report,
    load_baseline,
    main,
    render_markdown,
)
from sdetkit.benchmark_control_scorecard import (
    build_scorecard,
    load_benchmark_reports,
)
from sdetkit.replayable_benchmark_harness import (
    build_execution_plan_handoff_benchmark_report,
    load_execution_plan_handoff_scenarios,
)

FIXTURES = Path("tests/fixtures/remediation_benchmark")
SCENARIOS = [
    FIXTURES / "execution_plan_handoff_observed_oracle.json",
    FIXTURES / "execution_plan_handoff_not_provided.json",
    FIXTURES / "execution_plan_handoff_authority_unsafe.json",
]


def _write(path: Path, payload: dict) -> Path:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _scorecard(tmp_path: Path) -> dict:
    benchmark = build_execution_plan_handoff_benchmark_report(
        load_execution_plan_handoff_scenarios(SCENARIOS)
    )
    benchmark_path = _write(tmp_path / "benchmark.json", benchmark)
    return build_scorecard(load_benchmark_reports([benchmark_path]))


def test_canonical_reviewed_baseline_accepts_current_scorecard(
    tmp_path: Path,
) -> None:
    baseline = load_baseline(DEFAULT_BASELINE_PATH)
    report = build_regression_report(
        _scorecard(tmp_path),
        baseline,
        scorecard_path="candidate.json",
        baseline_path=DEFAULT_BASELINE_PATH.as_posix(),
    )

    assert baseline["schema_version"] == BASELINE_SCHEMA_VERSION
    assert report["schema_version"] == SCHEMA_VERSION
    assert report["status"] == "passed"
    assert report["regression_detected"] is False
    assert report["regression_count"] == 0
    assert report["regressions"] == []

    boundary = report["decision_boundary"]
    assert boundary["reporting_only"] is True
    assert boundary["current_pr_decision_input"] is False
    assert boundary["automation_allowed"] is False
    assert boundary["patch_application_allowed"] is False
    assert boundary["merge_authorized"] is False
    assert boundary["semantic_equivalence_proven"] is False
    assert boundary["executes_plan"] is False
    assert boundary["executes_patch"] is False


def test_dimension_and_score_regression_is_reported(
    tmp_path: Path,
) -> None:
    candidate = _scorecard(tmp_path)
    candidate["status"] = "failed"
    candidate["overall_score"] = 95.0
    candidate["dimension_scores"]["scenario_health"] = 80.0

    report = build_regression_report(
        candidate,
        load_baseline(DEFAULT_BASELINE_PATH),
    )

    failed = {item["check"] for item in report["regressions"]}
    assert report["status"] == "failed"
    assert report["regression_detected"] is True
    assert "scorecard_status" in failed
    assert "overall_score" in failed
    assert "dimension:scenario_health" in failed


def test_missing_mode_and_reduced_coverage_are_reported(
    tmp_path: Path,
) -> None:
    candidate = _scorecard(tmp_path)
    candidate["benchmark_modes"] = []
    candidate["report_count"] = 0
    candidate["scenario_count"] = 0

    report = build_regression_report(
        candidate,
        load_baseline(DEFAULT_BASELINE_PATH),
    )

    failed = {item["check"] for item in report["regressions"]}
    assert "required_modes" in failed
    assert "report_count" in failed
    assert "scenario_count" in failed


def test_authority_expansion_is_rejected(
    tmp_path: Path,
) -> None:
    candidate = _scorecard(tmp_path)
    candidate["expanded_authority_fields"] = ["automation_allowed_count"]
    candidate["decision_boundary"]["automation_allowed"] = True

    report = build_regression_report(
        candidate,
        load_baseline(DEFAULT_BASELINE_PATH),
    )

    failed = {item["check"] for item in report["regressions"]}
    assert "expanded_authority" in failed
    assert "authority:automation_allowed" in failed
    assert report["decision_boundary"]["automation_allowed"] is False


def test_unreviewed_or_automatic_baseline_is_invalid(
    tmp_path: Path,
) -> None:
    baseline = deepcopy(load_baseline(DEFAULT_BASELINE_PATH))
    baseline["activation"]["requires_human_review"] = False
    path = _write(tmp_path / "invalid-baseline.json", baseline)

    with pytest.raises(ValueError, match="human review"):
        load_baseline(path)

    baseline["activation"]["requires_human_review"] = True
    baseline["activation"]["automatic_updates_allowed"] = True
    _write(path, baseline)

    with pytest.raises(ValueError, match="automatic baseline updates"):
        load_baseline(path)


def test_cli_writes_deterministic_pass_and_failure_reports(
    tmp_path: Path,
    capsys,
) -> None:
    scorecard_path = _write(
        tmp_path / "scorecard.json",
        _scorecard(tmp_path),
    )
    out_dir = tmp_path / "pass"

    rc = main(
        [
            "--scorecard",
            str(scorecard_path),
            "--baseline",
            str(DEFAULT_BASELINE_PATH),
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    saved = json.loads((out_dir / "benchmark-control-regression.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "benchmark-control-regression.md").read_text(encoding="utf-8")

    assert printed == saved
    assert saved["status"] == "passed"
    assert "# Benchmark Control Regression Gate" in markdown
    assert "Current PR decision input: `false`" in markdown
    assert render_markdown(saved) == markdown

    failed = _scorecard(tmp_path)
    failed["overall_score"] = 90.0
    failed["status"] = "failed"
    failed_path = _write(tmp_path / "failed-scorecard.json", failed)

    failure_rc = main(
        [
            "--scorecard",
            str(failed_path),
            "--baseline",
            str(DEFAULT_BASELINE_PATH),
            "--out-dir",
            str(tmp_path / "failed"),
            "--format",
            "json",
        ]
    )
    assert failure_rc == 1
