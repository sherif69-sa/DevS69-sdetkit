from __future__ import annotations

import copy
import json
from pathlib import Path

from sdetkit.replayable_benchmark_harness import (
    build_benchmark_report,
    build_diagnostic_worker_benchmark_report,
    build_security_freshness_benchmark_report,
    evaluate_scenario,
    load_diagnostic_worker_scenarios,
    load_scenarios,
    load_security_freshness_scenarios,
    main,
    render_markdown,
)

FIXTURES = Path("tests/fixtures/remediation_benchmark")
SCENARIO_PATHS = [
    FIXTURES / "nop_formatting_patch.json",
    FIXTURES / "oracle_formatting_patch.json",
    FIXTURES / "unsafe_protected_path_patch.json",
]
DIAGNOSTIC_WORKER_PATHS = [
    FIXTURES / "runtime_guard_worker_oracle.json",
    FIXTURES / "runtime_guard_worker_nop.json",
    FIXTURES / "runtime_guard_worker_unsafe.json",
]
SECURITY_FRESHNESS_PATHS = [
    FIXTURES / "security_freshness_stale_runtime_oracle.json",
    FIXTURES / "security_freshness_current_primary_oracle.json",
    FIXTURES / "security_freshness_authority_unsafe.json",
]


def _scenarios() -> list[dict]:
    return load_scenarios(SCENARIO_PATHS)


def _scenario(scenario_type: str) -> dict:
    return next(item for item in _scenarios() if item["scenario_type"] == scenario_type)


def test_replayable_benchmark_harness_proves_required_fixture_contracts() -> None:
    report = build_benchmark_report(_scenarios())

    assert report["schema_version"] == "sdetkit.replayable_benchmark_harness.v1"
    assert report["status"] == "passed"
    assert report["scenario_count"] == 3
    assert report["passed_count"] == 3
    assert report["failed_count"] == 0

    contract = report["required_contract"]
    assert contract["all_required_present"] is True
    assert contract["all_required_passed"] is True
    assert contract["nop_fail_rate"] == 1.0
    assert contract["oracle_pass_rate"] == 1.0
    assert contract["unsafe_patch_rejection_rate"] == 1.0

    boundary = report["safety_boundary"]
    assert boundary["execution_model"] == "read_only_in_process_fixture_evaluation"
    assert boundary["automation_allowed_count"] == 0
    assert boundary["merge_authorized_count"] == 0
    assert boundary["semantic_equivalence_claimed_count"] == 0
    assert boundary["preserved"] is True
    assert report["attempt_scored_count"] == 3


def test_replayable_benchmark_oracle_passes_structural_verification_only() -> None:
    result = evaluate_scenario(_scenario("oracle_pass"))

    patch_decision = result["patch_score"]["decision"]
    verifier_decision = result["protected_verifier_result"]["decision"]

    assert result["passed"] is True
    assert patch_decision["status"] == "candidate_for_protected_verification"
    assert verifier_decision["status"] == "structurally_verified_candidate"
    assert verifier_decision["structural_verification_passed"] is True
    assert verifier_decision["semantic_equivalence_proven"] is False
    assert verifier_decision["automation_allowed"] is False
    assert verifier_decision["merge_authorized"] is False


def test_replayable_benchmark_nop_attempt_fails_safety_chain() -> None:
    result = evaluate_scenario(_scenario("nop_fail"))

    assert result["passed"] is True
    assert result["patch_score"]["decision"]["status"] == "blocked_review_first"
    assert result["protected_verifier_result"]["decision"]["status"] == "blocked_review_first"


def test_replayable_benchmark_unsafe_protected_patch_fails_safety_chain() -> None:
    result = evaluate_scenario(_scenario("unsafe_patch_fail"))

    assert result["passed"] is True
    assert result["patch_score"]["decision"]["status"] == "blocked_review_first"
    assert result["protected_verifier_result"]["decision"]["status"] == "blocked_review_first"


def test_replayable_benchmark_marks_wrong_expected_outcome_failed() -> None:
    scenarios = _scenarios()
    invalid_oracle = copy.deepcopy(_scenario("oracle_pass"))
    invalid_oracle["expected"]["verifier_status"] = "blocked_review_first"
    scenarios = [
        invalid_oracle if item["scenario_type"] == "oracle_pass" else item for item in scenarios
    ]

    report = build_benchmark_report(scenarios)

    assert report["status"] == "failed"
    assert report["failed_count"] == 1
    oracle = next(item for item in report["scenarios"] if item["scenario_type"] == "oracle_pass")
    assert oracle["status"] == "failed"


def test_replayable_benchmark_markdown_renders_contract_and_boundaries() -> None:
    markdown = render_markdown(build_benchmark_report(_scenarios()))

    assert "# Replayable Benchmark Harness report" in markdown
    assert "All required scenarios passed: `true`" in markdown
    assert "NOP fail rate: `1.0000`" in markdown
    assert "Oracle pass rate: `1.0000`" in markdown
    assert "Unsafe patch rejection rate: `1.0000`" in markdown
    assert "Automation allowed count: `0`" in markdown
    assert "It does not apply patches or execute proof commands." in markdown


def test_replayable_benchmark_cli_writes_report_artifacts(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir = tmp_path / "benchmark-report"
    argv: list[str] = []
    for path in SCENARIO_PATHS:
        argv.extend(["--scenario", str(path)])
    argv.extend(["--out-dir", str(out_dir), "--format", "json"])

    rc = main(argv)

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    saved = json.loads((out_dir / "benchmark-report.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "benchmark-report.md").read_text(encoding="utf-8")

    assert printed["status"] == "passed"
    assert printed["scenario_count"] == 3
    assert saved["required_contract"]["all_required_passed"] is True
    assert "Replayable Benchmark Harness report" in markdown


def test_replayable_benchmark_runtime_guard_worker_mode_proves_oracle_nop_and_unsafe() -> None:
    report = build_diagnostic_worker_benchmark_report(
        load_diagnostic_worker_scenarios(DIAGNOSTIC_WORKER_PATHS)
    )

    assert report["status"] == "passed"
    assert report["report_mode"] == "diagnostic_worker_runtime_guard_fixture"
    assert report["scenario_count"] == 3
    assert report["passed_count"] == 3
    assert report["required_contract"]["all_required_passed"] is True
    assert report["required_contract"]["oracle_pass_rate"] == 1.0
    assert report["required_contract"]["nop_pass_rate"] == 1.0
    assert report["required_contract"]["unsafe_authority_rejection_rate"] == 1.0
    assert report["safety_boundary"]["contributes_to_current_pr_decision"] is False
    assert report["safety_boundary"]["feeds_repo_memory"] is False
    assert report["safety_boundary"]["protected_verifier_semantics_expanded"] is False
    assert report["safety_boundary"]["automation_allowed_count"] == 0
    assert report["safety_boundary"]["merge_authorized_count"] == 0


def test_replayable_benchmark_runtime_guard_worker_markdown_is_non_authorizing() -> None:
    report = build_diagnostic_worker_benchmark_report(
        load_diagnostic_worker_scenarios(DIAGNOSTIC_WORKER_PATHS)
    )
    markdown = render_markdown(report)

    assert "Required runtime-guard worker replay contract" in markdown
    assert "Oracle pass rate: `1.0000`" in markdown
    assert "NOP pass rate: `1.0000`" in markdown
    assert "Unsafe authority rejection rate: `1.0000`" in markdown
    assert "Current PR decision input: `false`" in markdown
    assert "Feeds RepoMemory: `false`" in markdown
    assert "ProtectedVerifier semantics expanded: `false`" in markdown
    assert "does not expand ProtectedVerifier semantic claims" in markdown


def test_replayable_benchmark_runtime_guard_worker_cli_writes_report(
    tmp_path: Path, capsys
) -> None:
    out_dir = tmp_path / "worker-benchmark-report"
    argv: list[str] = []
    for path in DIAGNOSTIC_WORKER_PATHS:
        argv.extend(["--diagnostic-worker-scenario", str(path)])
    argv.extend(["--out-dir", str(out_dir), "--format", "json"])

    rc = main(argv)

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    saved = json.loads((out_dir / "benchmark-report.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "benchmark-report.md").read_text(encoding="utf-8")
    assert printed["status"] == "passed"
    assert printed["scenario_count"] == 3
    assert saved["report_mode"] == "diagnostic_worker_runtime_guard_fixture"
    assert saved["safety_boundary"]["feeds_repo_memory"] is False
    assert "Current PR decision input: `false`" in markdown


def test_replayable_benchmark_security_freshness_worker_mode_proves_stale_current_and_unsafe() -> (
    None
):
    report = build_security_freshness_benchmark_report(
        load_security_freshness_scenarios(SECURITY_FRESHNESS_PATHS)
    )

    assert report["status"] == "passed"
    assert report["report_mode"] == "diagnostic_worker_security_freshness_fixture"
    assert report["scenario_count"] == 3
    assert report["passed_count"] == 3
    assert report["required_contract"]["all_required_passed"] is True
    assert report["required_contract"]["stale_exclusion_pass_rate"] == 1.0
    assert report["required_contract"]["current_primary_pass_rate"] == 1.0
    assert report["required_contract"]["unsafe_authority_rejection_rate"] == 1.0
    assert report["safety_boundary"]["contributes_to_current_pr_decision"] is False
    assert report["safety_boundary"]["feeds_repo_memory"] is False
    assert report["safety_boundary"]["executes_patch"] is False
    assert report["safety_boundary"]["automation_allowed_count"] == 0
    assert report["safety_boundary"]["merge_authorized_count"] == 0
    assert report["safety_boundary"]["protected_verifier_semantics_expanded"] is False


def test_replayable_benchmark_security_freshness_markdown_is_non_authorizing() -> None:
    report = build_security_freshness_benchmark_report(
        load_security_freshness_scenarios(SECURITY_FRESHNESS_PATHS)
    )
    markdown = render_markdown(report)

    assert "Required security-freshness worker replay contract" in markdown
    assert "Stale exclusion pass rate: `1.0000`" in markdown
    assert "Current security primary pass rate: `1.0000`" in markdown
    assert "Unsafe authority rejection rate: `1.0000`" in markdown
    assert "Current PR decision input: `false`" in markdown
    assert "Feeds RepoMemory: `false`" in markdown
    assert "ProtectedVerifier semantics expanded: `false`" in markdown
    assert "does not authorize security dismissal, remediation, or merge" in markdown


def test_replayable_benchmark_security_freshness_cli_writes_report(tmp_path: Path, capsys) -> None:
    out_dir = tmp_path / "security-freshness-benchmark-report"
    argv: list[str] = []
    for path in SECURITY_FRESHNESS_PATHS:
        argv.extend(["--security-freshness-scenario", str(path)])
    argv.extend(["--out-dir", str(out_dir), "--format", "json"])

    rc = main(argv)

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    saved = json.loads((out_dir / "benchmark-report.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "benchmark-report.md").read_text(encoding="utf-8")
    assert printed["status"] == "passed"
    assert printed["scenario_count"] == 3
    assert saved["report_mode"] == "diagnostic_worker_security_freshness_fixture"
    assert saved["safety_boundary"]["feeds_repo_memory"] is False
    assert "Current PR decision input: `false`" in markdown


SAFETYGATE_EVIDENCE_PATH = FIXTURES / "oracle_safetygate_repo_memory_evidence.json"


def test_replayable_benchmark_replays_safetygate_repo_memory_evidence() -> None:
    report = build_benchmark_report(load_scenarios(SCENARIO_PATHS + [SAFETYGATE_EVIDENCE_PATH]))

    safety_gate = report["safety_gate_evidence"]
    assert report["status"] == "passed"
    assert safety_gate["collection_status"] == "collected"
    assert safety_gate["status"] == "safety_gate_evidence_replayed"
    assert safety_gate["scenario_count"] == 1
    assert safety_gate["record_count"] == 1
    assert safety_gate["safe_fix_allowed_count"] == 1
    assert safety_gate["review_first_count"] == 0
    assert safety_gate["reporting_only_count"] == 1
    assert safety_gate["report_paths"] == ["build/pr-quality/failure-bundle/failure-bundle.md"]
    assert safety_gate["decision_boundary"] == {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }

    scenario = next(
        item
        for item in report["scenarios"]
        if item["scenario_id"] == "oracle-safetygate-repo-memory-evidence"
    )
    assert scenario["passed"] is True
    assert scenario["safety_gate_evidence"]["source"] == "trajectory.safety_gate"
    assert scenario["safety_gate_evidence"]["safe_fix_allowed_count"] == 1

    markdown = render_markdown(report)
    assert "## SafetyGate evidence replay" in markdown
    assert "Safe-fix allowed records: `1`" in markdown
    assert "Automation allowed by SafetyGate evidence: `false`" in markdown
    assert "Merge authorized by SafetyGate evidence: `false`" in markdown


def test_replayable_benchmark_rejects_authority_expanding_safetygate_evidence() -> None:
    scenario = load_scenarios([SAFETYGATE_EVIDENCE_PATH])[0]
    scenario["pattern_insights"]["safety_gate_evidence"]["decision_boundary"][
        "merge_authorized"
    ] = True

    try:
        evaluate_scenario(scenario)
    except ValueError as exc:
        assert "SafetyGate benchmark evidence expands authority: merge_authorized" in str(exc)
    else:
        raise AssertionError("expected authority-expanding SafetyGate evidence to fail")


def test_replayable_benchmark_passes_safetygate_evidence_into_protected_verifier() -> None:
    scenario = load_scenarios([SAFETYGATE_EVIDENCE_PATH])[0]

    result = evaluate_scenario(scenario)

    verifier_safety_gate = result["protected_verifier_result"]["safety_gate_evidence"]
    assert verifier_safety_gate["collection_status"] == "collected"
    assert verifier_safety_gate["source"] == "trajectory.safety_gate"
    assert verifier_safety_gate["safe_fix_allowed_count"] == 1
    assert verifier_safety_gate["expanded_authority_fields"] == []
    assert result["protected_verifier_result"]["decision"]["automation_allowed"] is False
    assert result["protected_verifier_result"]["decision"]["merge_authorized"] is False
