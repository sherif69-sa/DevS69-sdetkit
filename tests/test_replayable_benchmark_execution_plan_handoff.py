from __future__ import annotations

import json
from pathlib import Path

from sdetkit.replayable_benchmark_harness import (
    build_execution_plan_handoff_benchmark_report,
    load_execution_plan_handoff_scenarios,
    main,
    render_markdown,
)

FIXTURES = Path("tests/fixtures/remediation_benchmark")
SCENARIO_PATHS = [
    FIXTURES / "execution_plan_handoff_observed_oracle.json",
    FIXTURES / "execution_plan_handoff_not_provided.json",
    FIXTURES / "execution_plan_handoff_authority_unsafe.json",
]


def _scenarios() -> list[dict]:
    return load_execution_plan_handoff_scenarios(SCENARIO_PATHS)


def test_execution_plan_handoff_benchmark_proves_required_contract() -> None:
    report = build_execution_plan_handoff_benchmark_report(_scenarios())

    assert report["schema_version"] == (
        "sdetkit.replayable_benchmark_harness.execution_plan_handoff.v1"
    )
    assert report["report_mode"] == "diagnostic_execution_plan_handoff_fixture"
    assert report["status"] == "passed"
    assert report["scenario_count"] == 3
    assert report["passed_count"] == 3
    assert report["failed_count"] == 0

    contract = report["required_contract"]
    assert contract["all_required_present"] is True
    assert contract["all_required_passed"] is True
    assert contract["observed_handoff_pass_rate"] == 1.0
    assert contract["not_provided_pass_rate"] == 1.0
    assert contract["unsafe_authority_rejection_rate"] == 1.0

    boundary = report["safety_boundary"]
    assert boundary["contributes_to_current_pr_decision"] is False
    assert boundary["feeds_repo_memory"] is False
    assert boundary["executes_plan"] is False
    assert boundary["executes_patch"] is False
    assert boundary["automation_allowed_count"] == 0
    assert boundary["merge_authorized_count"] == 0
    assert boundary["preserved"] is True


def test_execution_plan_handoff_benchmark_retains_and_rejects_expected_evidence() -> None:
    report = build_execution_plan_handoff_benchmark_report(_scenarios())
    results = {item["scenario_type"]: item for item in report["scenarios"]}

    observed = results["execution_plan_handoff_oracle_pass"]
    assert observed["execution_plan_handoff_status"] == "observed"
    assert observed["planned_command_count"] == 1
    assert observed["trajectory_record_count"] == 1

    not_provided = results["execution_plan_handoff_nop_pass"]
    assert not_provided["execution_plan_handoff_status"] == "not_provided"
    assert not_provided["planned_command_count"] == 0
    assert not_provided["trajectory_record_count"] == 1

    unsafe = results["execution_plan_handoff_authority_fail"]
    assert unsafe["trajectory_record_count"] == 0
    assert "command evidence cannot allow execution" in unsafe["observed_error"]


def test_execution_plan_handoff_benchmark_markdown_is_non_authorizing() -> None:
    markdown = render_markdown(build_execution_plan_handoff_benchmark_report(_scenarios()))

    assert "Required execution-plan handoff replay contract" in markdown
    assert "Observed handoff pass rate: `1.0000`" in markdown
    assert "Not-provided handoff pass rate: `1.0000`" in markdown
    assert "Unsafe authority rejection rate: `1.0000`" in markdown
    assert "Current PR decision input: `false`" in markdown
    assert "Feeds RepoMemory: `false`" in markdown
    assert "Executes plan: `false`" in markdown
    assert "does not execute plans" in markdown


def test_execution_plan_handoff_benchmark_cli_writes_report(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir = tmp_path / "execution-plan-benchmark"
    argv: list[str] = []
    for path in SCENARIO_PATHS:
        argv.extend(["--execution-plan-handoff-scenario", str(path)])
    argv.extend(["--out-dir", str(out_dir), "--format", "json"])

    rc = main(argv)

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    saved = json.loads((out_dir / "benchmark-report.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "benchmark-report.md").read_text(encoding="utf-8")

    assert printed["status"] == "passed"
    assert printed["scenario_count"] == 3
    assert saved["report_mode"] == "diagnostic_execution_plan_handoff_fixture"
    assert saved["safety_boundary"]["executes_plan"] is False
    assert "Required execution-plan handoff replay contract" in markdown
