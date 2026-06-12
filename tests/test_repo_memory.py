from __future__ import annotations

import copy
import json
from pathlib import Path

from sdetkit.pr_quality_candidate_validation import build_validation_report
from sdetkit.replayable_benchmark_harness import (
    EVIDENCE_SHADOW_FAIL,
    INVENTORY_CLAIM_MISMATCH_FAIL,
    LIVE_EVIDENCE_SOURCE,
    NETWORK_BOUNDARY_REQUIRED_FAIL,
    PROOF_MUTATION_FAIL,
    UNCLAIMED_WRITE_FAIL,
    VERIFICATION_EVIDENCE_SOURCE,
    build_benchmark_report,
    load_scenarios,
)
from sdetkit.repo_memory import (
    LIVE_PROFILE_STATUS,
    LIVE_PROOF_STATE,
    build_repo_memory_profile,
    main,
    render_markdown,
)
from sdetkit.trusted_flaky_test_registry_producer import (
    NO_TEST_OBSERVATIONS,
    build_trusted_registry_evidence,
)

FIXTURES = Path("tests/fixtures/remediation_benchmark")
SCENARIOS = [
    FIXTURES / "nop_formatting_patch.json",
    FIXTURES / "oracle_formatting_patch.json",
    FIXTURES / "unsafe_protected_path_patch.json",
]
CANDIDATE_FIXTURES = Path("tests/fixtures/pr_quality_candidate_visibility")
CANDIDATE_SCENARIOS = [
    CANDIDATE_FIXTURES / "formatting_candidate_verified.json",
    CANDIDATE_FIXTURES / "broader_diff_review_first.json",
]


def _candidate_validation_report() -> dict:
    return build_validation_report(CANDIDATE_SCENARIOS)


def _benchmark_report() -> dict:
    return build_benchmark_report(load_scenarios(SCENARIOS))


def _live_benchmark_report() -> dict:
    git_verified_key = "_".join(("git", "inventory", "verified"))
    oracle = copy.deepcopy(
        next(
            item
            for item in _benchmark_report()["scenarios"]
            if item["scenario_type"] == "oracle_pass"
        )
    )
    oracle[VERIFICATION_EVIDENCE_SOURCE] = LIVE_EVIDENCE_SOURCE
    oracle["isolated_proof_evidence"] = {
        "status": "passed",
        "decision_boundary": {
            git_verified_key: True,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }

    mismatch = copy.deepcopy(oracle)
    mismatch["scenario_id"] = "live-inventory-mismatch"
    mismatch["scenario_type"] = INVENTORY_CLAIM_MISMATCH_FAIL
    mismatch["protected_verifier_result"]["decision"]["status"] = "blocked_review_first"
    mismatch["isolated_proof_evidence"] = {
        "status": "failed",
        "decision_boundary": {
            git_verified_key: False,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }

    mutation = copy.deepcopy(oracle)
    mutation["scenario_id"] = "live-proof-mutation"
    mutation["scenario_type"] = PROOF_MUTATION_FAIL
    mutation["protected_verifier_result"]["decision"]["status"] = "blocked_review_first"
    mutation["isolated_proof_evidence"] = {
        "status": "failed",
        "decision_boundary": {
            git_verified_key: True,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }

    network = copy.deepcopy(oracle)
    network["scenario_id"] = "live-network-boundary-required"
    network["scenario_type"] = NETWORK_BOUNDARY_REQUIRED_FAIL
    network["protected_verifier_result"]["decision"]["status"] = "blocked_review_first"
    network["isolated_proof_evidence"] = {
        "status": "failed",
        "decision_boundary": {
            git_verified_key: True,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }

    unclaimed = copy.deepcopy(oracle)
    unclaimed["scenario_id"] = "live-unclaimed-write"
    unclaimed["scenario_type"] = UNCLAIMED_WRITE_FAIL
    unclaimed["protected_verifier_result"]["decision"]["status"] = "blocked_review_first"
    unclaimed["isolated_proof_evidence"] = {
        "status": "failed",
        "decision_boundary": {
            git_verified_key: True,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }

    shadow = copy.deepcopy(oracle)
    shadow["scenario_id"] = "live-evidence-shadow"
    shadow["scenario_type"] = EVIDENCE_SHADOW_FAIL
    shadow["protected_verifier_result"]["decision"]["status"] = "blocked_review_first"
    shadow["isolated_proof_evidence"] = {
        "status": "failed",
        "decision_boundary": {
            git_verified_key: True,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }

    return {
        "schema_version": "sdetkit.replayable_benchmark_harness.isolated_evidence.v3",
        "report_mode": LIVE_EVIDENCE_SOURCE,
        "status": "passed",
        "required_contract": {
            "all_required_present": True,
            "all_required_passed": True,
        },
        "live_evidence": {
            "git_inventory_verified_count": 5,
            "expected_failed_evidence_count": 5,
            "network_boundary_blocked_count": 1,
            "anti_cheat_rejection_count": 2,
        },
        "safety_boundary": {
            "automation_allowed_count": 0,
            "merge_authorized_count": 0,
            "semantic_equivalence_claimed_count": 0,
            "preserved": True,
        },
        "scenarios": [oracle, mismatch, mutation, network, unclaimed, shadow],
    }


def _flaky_registry_evidence() -> dict:
    return {
        "schema_version": "sdetkit.flaky_test_registry_evidence.v1",
        "collection_status": "collected",
        "status": "advisory_registry_collected",
        "source": {
            "kind": "operator_review_input",
            "reference": "local-proof",
            "classification_schema": "sdetkit.intelligence.flake.v1",
            "input_read_only": True,
            "commands_executed_by_reader": False,
        },
        "entries": [
            {
                "test_id": "tests/test_service.py::test_retry_path",
                "fingerprint": "abcd1234",
                "classification": "flaky",
                "observed_runs": 3,
                "observed_failures": 1,
                "observed_passes": 2,
                "decision": "instability_context_only",
                "review_first": True,
            }
        ],
        "summary": {
            "entry_count": 1,
            "flaky_test_count": 1,
        },
        "decision_boundary": {
            "automatic_quarantine_allowed": False,
            "automatic_rerun_allowed": False,
            "current_failure_suppression_allowed": False,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }


def _pattern_insights() -> dict:
    return {
        "schema_version": "sdetkit.trajectory_pattern_insights.v1",
        "record_count": 5,
        "recurring_safe_fix_patterns": [
            {
                "failure_class": "formatting_only",
                "action": "run_pre_commit",
                "count": 2,
            }
        ],
        "recurring_review_first_surfaces": [
            {
                "value": "security",
                "count": 2,
            }
        ],
    }


def test_repo_memory_records_benchmark_supported_candidate_without_automation() -> None:
    profile = build_repo_memory_profile(
        pattern_insights=_pattern_insights(),
        benchmark_report=_benchmark_report(),
    )

    assert profile["schema_version"] == "sdetkit.repo_memory.v6"
    assert profile["profile_status"] == "benchmark_supported_memory"
    assert profile["memory_mode"] == "read_only_profile"
    assert profile["inputs"]["benchmark_contract_proven"] is True
    assert profile["known_safe_candidate_count"] == 1

    history = profile["safe_fix_history"][0]
    assert history["failure_class"] == "formatting_only"
    assert history["action"] == "run_pre_commit"
    assert history["proof_state"] == "benchmark_supported_candidate"
    assert history["benchmark_supported"] is True
    assert history["automation_allowed"] is False

    boundary = profile["decision_boundary"]
    assert boundary["automation_allowed"] is False
    assert boundary["merge_authorized"] is False
    assert boundary["semantic_equivalence_proven"] is False


def test_repo_memory_records_proof_commands_and_benchmark_rejections() -> None:
    profile = build_repo_memory_profile(
        pattern_insights=_pattern_insights(),
        benchmark_report=_benchmark_report(),
    )

    assert profile["command_profile"]["observed_proof_commands"] == ["python -m pre_commit run -a"]
    assert profile["command_profile"]["commands_executed_by_repo_memory"] is False

    rejections = profile["failure_patterns"]["benchmark_rejections"]
    types = {item["scenario_type"] for item in rejections}
    assert types == {"nop_fail", "unsafe_patch_fail"}
    assert all(item["decision"] == "blocked_review_first" for item in rejections)
    assert all(item["automation_allowed"] is False for item in rejections)


def test_repo_memory_records_review_first_and_flaky_registry_boundaries() -> None:
    profile = build_repo_memory_profile(
        pattern_insights=_pattern_insights(),
        benchmark_report=_benchmark_report(),
    )

    review_first = profile["failure_patterns"]["review_first"]
    assert review_first == [
        {
            "pattern_kind": "review_first_surface",
            "surface": "security",
            "trajectory_count": 2,
            "decision": "review_first",
            "automation_allowed": False,
        }
    ]

    flaky = profile["flaky_test_registry"]
    assert flaky["collection_status"] == "not_collected"
    assert flaky["entries"] == []
    assert "semantic equivalence" in profile["unproven_boundaries"]


def test_repo_memory_does_not_promote_pattern_when_benchmark_contract_fails() -> None:
    benchmark = copy.deepcopy(_benchmark_report())
    benchmark["status"] = "failed"
    benchmark["required_contract"]["all_required_passed"] = False

    profile = build_repo_memory_profile(
        pattern_insights=_pattern_insights(),
        benchmark_report=benchmark,
    )

    assert profile["profile_status"] == "observation_only"
    assert profile["known_safe_candidate_count"] == 0
    history = profile["safe_fix_history"][0]
    assert history["proof_state"] == "trajectory_observed_only"
    assert history["benchmark_supported"] is False
    assert history["automation_allowed"] is False


def test_repo_memory_markdown_renders_memory_and_safety_boundary() -> None:
    markdown = render_markdown(
        build_repo_memory_profile(
            pattern_insights=_pattern_insights(),
            benchmark_report=_benchmark_report(),
        )
    )

    assert "# RepoMemory profile" in markdown
    assert "Status: `benchmark_supported_memory`" in markdown
    assert "Known safe candidates: `1`" in markdown
    assert "proof_state=`benchmark_supported_candidate`" in markdown
    assert "benchmark scenario=`nop-formatting-patch`" in markdown
    assert "Collection status: `not_collected`" in markdown
    assert "Automation allowed: `false`" in markdown
    assert "Semantic equivalence proven: `false`" in markdown


def test_repo_memory_cli_writes_profile_artifacts(tmp_path: Path, capsys) -> None:
    insights_path = tmp_path / "pattern-insights.json"
    benchmark_path = tmp_path / "benchmark-report.json"
    out_dir = tmp_path / "repo-memory"

    insights_path.write_text(json.dumps(_pattern_insights()), encoding="utf-8")
    benchmark_path.write_text(json.dumps(_benchmark_report()), encoding="utf-8")

    rc = main(
        [
            "--pattern-insights",
            str(insights_path),
            "--benchmark-report",
            str(benchmark_path),
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    saved = json.loads((out_dir / "repo-memory-profile.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "repo-memory-profile.md").read_text(encoding="utf-8")

    assert printed["profile_status"] == "benchmark_supported_memory"
    assert printed["known_safe_candidate_count"] == 1
    assert saved["decision_boundary"]["automation_allowed"] is False
    assert "# RepoMemory profile" in markdown


def test_repo_memory_records_live_git_grounded_proof_outcomes_without_authority() -> None:
    profile = build_repo_memory_profile(
        pattern_insights=_pattern_insights(),
        benchmark_report=_benchmark_report(),
        live_benchmark_report=_live_benchmark_report(),
    )

    assert profile["profile_status"] == LIVE_PROFILE_STATUS
    assert profile["inputs"]["live_contract_proven"] is True
    assert profile["live_safe_candidate_count"] == 1

    history = profile["safe_fix_history"][0]
    assert history["proof_state"] == LIVE_PROOF_STATE
    assert history["live_proof_supported"] is True
    assert history["evidence_source"] == LIVE_EVIDENCE_SOURCE
    assert history["automation_allowed"] is False

    provenance = profile["proof_provenance"]
    assert provenance["fixture_contract_proven"] is True
    assert provenance["live_contract_proven"] is True
    assert provenance["git_verified_scenario_count"] == 5
    assert provenance["expected_failed_scenario_count"] == 5
    assert provenance["network_boundary_blocked_scenario_count"] == 1
    assert provenance["anti_cheat_rejection_scenario_count"] == 2

    live_rejections = profile["failure_patterns"]["live_rejections"]
    assert {item["scenario_type"] for item in live_rejections} == {
        INVENTORY_CLAIM_MISMATCH_FAIL,
        PROOF_MUTATION_FAIL,
        NETWORK_BOUNDARY_REQUIRED_FAIL,
        UNCLAIMED_WRITE_FAIL,
        EVIDENCE_SHADOW_FAIL,
    }
    assert all(item["decision"] == "blocked_review_first" for item in live_rejections)
    assert all(item["automation_allowed"] is False for item in live_rejections)

    boundary = profile["decision_boundary"]
    assert boundary["automation_allowed"] is False
    assert boundary["merge_authorized"] is False
    assert boundary["semantic_equivalence_proven"] is False


def test_repo_memory_keeps_fixture_support_when_live_contract_is_invalid() -> None:
    live_report = copy.deepcopy(_live_benchmark_report())
    live_report["status"] = "failed"
    live_report["required_contract"]["all_required_passed"] = False

    profile = build_repo_memory_profile(
        pattern_insights=_pattern_insights(),
        benchmark_report=_benchmark_report(),
        live_benchmark_report=live_report,
    )

    assert profile["profile_status"] == "benchmark_supported_memory"
    assert profile["live_safe_candidate_count"] == 0
    assert profile["failure_patterns"]["live_rejections"] == []

    history = profile["safe_fix_history"][0]
    assert history["proof_state"] == "benchmark_supported_candidate"
    assert history["fixture_supported"] is True
    assert history["live_proof_supported"] is False


def test_repo_memory_cli_accepts_live_benchmark_report(tmp_path: Path, capsys) -> None:
    insights_path = tmp_path / "pattern-insights.json"
    benchmark_path = tmp_path / "benchmark-report.json"
    live_path = tmp_path / "live-benchmark-report.json"
    out_dir = tmp_path / "repo-memory-live"

    insights_path.write_text(json.dumps(_pattern_insights()), encoding="utf-8")
    benchmark_path.write_text(json.dumps(_benchmark_report()), encoding="utf-8")
    live_path.write_text(json.dumps(_live_benchmark_report()), encoding="utf-8")

    rc = main(
        [
            "--pattern-insights",
            str(insights_path),
            "--benchmark-report",
            str(benchmark_path),
            "--live-benchmark-report",
            str(live_path),
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    saved = json.loads((out_dir / "repo-memory-profile.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "repo-memory-profile.md").read_text(encoding="utf-8")

    assert printed["profile_status"] == LIVE_PROFILE_STATUS
    assert printed["live_safe_candidate_count"] == 1
    assert saved["proof_provenance"]["live_contract_proven"] is True
    assert "Live Git-grounded contract proven: `true`" in markdown
    assert "Live safe candidates: `1`" in markdown
    assert "Network boundary blocked scenarios: `1`" in markdown
    assert "Anti-cheat rejection scenarios: `2`" in markdown


def test_repo_memory_ingests_flaky_test_registry_as_advisory_context_only() -> None:
    profile = build_repo_memory_profile(
        pattern_insights=_pattern_insights(),
        benchmark_report=_benchmark_report(),
        flaky_test_registry_evidence=_flaky_registry_evidence(),
    )

    flaky = profile["flaky_test_registry"]
    assert flaky["collection_status"] == "collected"
    assert flaky["status"] == "advisory_registry_collected"
    assert flaky["entry_count"] == 1
    assert flaky["entries"][0]["decision"] == "instability_context_only"
    assert flaky["decision_boundary"]["automatic_quarantine_allowed"] is False
    assert flaky["decision_boundary"]["current_failure_suppression_allowed"] is False
    assert flaky["decision_boundary"]["automation_allowed"] is False

    boundary = profile["decision_boundary"]
    assert boundary["automation_allowed"] is False
    assert boundary["merge_authorized"] is False
    assert boundary["semantic_equivalence_proven"] is False


def test_repo_memory_rejects_authority_expanding_flaky_test_registry() -> None:
    evidence = _flaky_registry_evidence()
    evidence["decision_boundary"]["current_failure_suppression_allowed"] = True

    try:
        build_repo_memory_profile(
            pattern_insights=_pattern_insights(),
            benchmark_report=_benchmark_report(),
            flaky_test_registry_evidence=evidence,
        )
    except ValueError as exc:
        assert "expands authority" in str(exc)
    else:
        raise AssertionError("expected authority-expanding flaky evidence to be rejected")


def test_repo_memory_markdown_renders_flaky_history_no_authority_boundary() -> None:
    markdown = render_markdown(
        build_repo_memory_profile(
            pattern_insights=_pattern_insights(),
            benchmark_report=_benchmark_report(),
            flaky_test_registry_evidence=_flaky_registry_evidence(),
        )
    )

    assert "Status: `advisory_registry_collected`" in markdown
    assert "Automatic quarantine allowed: `false`" in markdown
    assert "Current failure suppression allowed: `false`" in markdown
    assert "Automation allowed by flaky-test history: `false`" in markdown


def test_repo_memory_rejects_hidden_entry_authority_and_bad_registry_schema() -> None:
    hidden_authority = _flaky_registry_evidence()
    hidden_authority["entries"][0]["automation_allowed"] = True

    try:
        build_repo_memory_profile(
            pattern_insights=_pattern_insights(),
            benchmark_report=_benchmark_report(),
            flaky_test_registry_evidence=hidden_authority,
        )
    except ValueError as exc:
        assert "entry expands authority" in str(exc)
    else:
        raise AssertionError("expected entry-level authority expansion to be rejected")

    unsupported = _flaky_registry_evidence()
    unsupported["schema_version"] = "unsupported.registry.v1"

    try:
        build_repo_memory_profile(
            pattern_insights=_pattern_insights(),
            benchmark_report=_benchmark_report(),
            flaky_test_registry_evidence=unsupported,
        )
    except ValueError as exc:
        assert "schema is not supported" in str(exc)
    else:
        raise AssertionError("expected unsupported registry schema to be rejected")


def test_repo_memory_cli_accepts_advisory_flaky_registry_evidence(
    tmp_path: Path,
    capsys,
) -> None:
    insights_path = tmp_path / "pattern-insights.json"
    benchmark_path = tmp_path / "benchmark-report.json"
    flaky_path = tmp_path / "flaky-test-registry-evidence.json"
    out_dir = tmp_path / "repo-memory-with-flaky-context"

    insights_path.write_text(json.dumps(_pattern_insights()), encoding="utf-8")
    benchmark_path.write_text(json.dumps(_benchmark_report()), encoding="utf-8")
    flaky_path.write_text(json.dumps(_flaky_registry_evidence()), encoding="utf-8")

    rc = main(
        [
            "--pattern-insights",
            str(insights_path),
            "--benchmark-report",
            str(benchmark_path),
            "--flaky-test-registry-evidence",
            str(flaky_path),
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    capsys.readouterr()
    saved = json.loads((out_dir / "repo-memory-profile.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "repo-memory-profile.md").read_text(encoding="utf-8")

    assert saved["flaky_test_registry"]["collection_status"] == "collected"
    assert saved["flaky_test_registry"]["entry_count"] == 1
    assert saved["flaky_test_registry"]["decision_boundary"]["automation_allowed"] is False
    assert "Current failure suppression allowed: `false`" in markdown


def test_repo_memory_ingests_trusted_main_no_observation_registry_without_claims() -> None:
    profile = build_repo_memory_profile(
        pattern_insights=_pattern_insights(),
        benchmark_report=_benchmark_report(),
        flaky_test_registry_evidence=build_trusted_registry_evidence(
            source_run_id="run-1417",
            source_head_sha="a5545fa1",
        ),
    )

    flaky = profile["flaky_test_registry"]
    assert flaky["collection_status"] == "collected"
    assert flaky["entry_count"] == 0
    assert flaky["entries"] == []
    assert flaky["source"]["kind"] == "trusted_main_artifact"
    assert flaky["source"]["observation_status"] == NO_TEST_OBSERVATIONS
    assert flaky["source"]["observations_collected"] is False
    assert flaky["decision_boundary"]["automation_allowed"] is False
    assert flaky["decision_boundary"]["merge_authorized"] is False
    assert "trusted accepted-main observation history" in profile["recommended_next_action"]


def test_repo_memory_rejects_unsupported_flaky_classification_schema() -> None:
    evidence = _flaky_registry_evidence()
    evidence["source"]["classification_schema"] = "unsupported.classification.v1"

    try:
        build_repo_memory_profile(
            pattern_insights=_pattern_insights(),
            benchmark_report=_benchmark_report(),
            flaky_test_registry_evidence=evidence,
        )
    except ValueError as exc:
        assert "classification schema is not supported" in str(exc)
    else:
        raise AssertionError("expected unsupported classification schema to be rejected")


def test_repo_memory_rejects_entries_in_trusted_no_observation_registry() -> None:
    evidence = build_trusted_registry_evidence(
        source_run_id="run-1417",
        source_head_sha="a5545fa1",
    )
    evidence["entries"] = [_flaky_registry_evidence()["entries"][0]]
    evidence["summary"]["entry_count"] = 1
    evidence["summary"]["flaky_test_count"] = 1

    try:
        build_repo_memory_profile(
            pattern_insights=_pattern_insights(),
            benchmark_report=_benchmark_report(),
            flaky_test_registry_evidence=evidence,
        )
    except ValueError as exc:
        assert "no-observation registry cannot contain entries" in str(exc)
    else:
        raise AssertionError("expected false trusted-main entry claim to be rejected")


def test_repo_memory_markdown_renders_trusted_no_observation_status() -> None:
    markdown = render_markdown(
        build_repo_memory_profile(
            pattern_insights=_pattern_insights(),
            benchmark_report=_benchmark_report(),
            flaky_test_registry_evidence=build_trusted_registry_evidence(
                source_run_id="run-1417",
                source_head_sha="a5545fa1",
            ),
        )
    )

    assert "Source kind: `trusted_main_artifact`" in markdown
    assert "Observation status: `no_test_observations_available`" in markdown
    assert "Entries: `0`" in markdown
    assert "Automation allowed by flaky-test history: `false`" in markdown


def test_repo_memory_retains_controlled_candidate_validation_as_advisory_only() -> None:
    profile = build_repo_memory_profile(
        pattern_insights=_pattern_insights(),
        benchmark_report=_benchmark_report(),
        live_benchmark_report=_live_benchmark_report(),
        controlled_candidate_validation_evidence=_candidate_validation_report(),
    )

    controlled = profile["controlled_candidate_validation"]
    assert controlled["collection_status"] == "collected"
    assert controlled["status"] == "controlled_validation_passed"
    assert controlled["scenario_count"] == 2
    assert controlled["passed_count"] == 2
    assert controlled["structurally_verified_count"] == 1
    assert controlled["review_first_count"] == 1
    assert controlled["current_pr_decision_input"] is False
    assert controlled["decision_boundary"]["automation_allowed"] is False
    assert controlled["decision_boundary"]["merge_authorized"] is False
    assert profile["live_safe_candidate_count"] == 1
    assert profile["decision_boundary"]["automation_allowed"] is False

    markdown = render_markdown(profile)
    assert "Controlled candidate validation evidence" in markdown
    assert "Status: `controlled_validation_passed`" in markdown
    assert "Current PR decision input: `false`" in markdown
    assert "Automation allowed by controlled validation: `false`" in markdown


def test_repo_memory_rejects_controlled_validation_that_can_influence_current_pr() -> None:
    evidence = _candidate_validation_report()
    evidence["boundary"]["contributes_to_current_pr_decision"] = True

    try:
        build_repo_memory_profile(
            pattern_insights=_pattern_insights(),
            benchmark_report=_benchmark_report(),
            controlled_candidate_validation_evidence=evidence,
        )
    except ValueError as exc:
        assert "cannot contribute to a current PR decision" in str(exc)
    else:
        raise AssertionError("expected decision-influencing controlled validation to be rejected")


def test_repo_memory_cli_accepts_controlled_validation_without_promotion(
    tmp_path: Path,
    capsys,
) -> None:
    insights_path = tmp_path / "pattern-insights.json"
    benchmark_path = tmp_path / "benchmark-report.json"
    controlled_path = tmp_path / "candidate-validation.json"
    out_dir = tmp_path / "repo-memory-controlled-validation"

    insights_path.write_text(json.dumps(_pattern_insights()), encoding="utf-8")
    benchmark_path.write_text(json.dumps(_benchmark_report()), encoding="utf-8")
    controlled_path.write_text(json.dumps(_candidate_validation_report()), encoding="utf-8")

    rc = main(
        [
            "--pattern-insights",
            str(insights_path),
            "--benchmark-report",
            str(benchmark_path),
            "--controlled-candidate-validation-evidence",
            str(controlled_path),
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    saved = json.loads((out_dir / "repo-memory-profile.json").read_text(encoding="utf-8"))
    assert printed["controlled_candidate_validation_status"] == "controlled_validation_passed"
    assert saved["controlled_candidate_validation"]["current_pr_decision_input"] is False
    assert (
        saved["controlled_candidate_validation"]["decision_boundary"]["automation_allowed"] is False
    )


def test_repo_memory_rejects_controlled_scenario_semantic_equivalence_claim() -> None:
    evidence = _candidate_validation_report()
    evidence["scenarios"][0]["semantic_equivalence_proven"] = True

    try:
        build_repo_memory_profile(
            pattern_insights=_pattern_insights(),
            benchmark_report=_benchmark_report(),
            controlled_candidate_validation_evidence=evidence,
        )
    except ValueError as exc:
        assert "scenario expands authority" in str(exc)
    else:
        raise AssertionError("expected semantic-equivalence-claiming scenario to be rejected")


def test_repo_memory_surfaces_safety_gate_evidence_without_authority() -> None:
    insights = _pattern_insights()
    insights["safety_gate_evidence"] = {
        "collection_status": "collected",
        "status": "safety_gate_evidence_observed",
        "source": "trajectory.safety_gate",
        "record_count": 1,
        "safe_fix_allowed_count": 1,
        "review_first_count": 0,
        "reporting_only_count": 1,
        "report_paths": ["build/pr-quality/failure-bundle/failure-bundle.md"],
        "decision_boundary": {
            "automation_allowed": False,
            "patch_application_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }

    profile = build_repo_memory_profile(
        pattern_insights=insights,
        benchmark_report=_benchmark_report(),
        live_benchmark_report=_live_benchmark_report(),
    )

    safety_gate = profile["safety_gate_evidence"]
    assert profile["inputs"]["safety_gate_evidence_record_count"] == 1
    assert safety_gate["collection_status"] == "collected"
    assert safety_gate["safe_fix_allowed_count"] == 1
    assert safety_gate["review_first_count"] == 0
    assert safety_gate["decision_boundary"] == {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }

    markdown = render_markdown(profile)
    assert "## SafetyGate trajectory evidence" in markdown
    assert "Safe-fix allowed records: `1`" in markdown
    assert "Automation allowed by SafetyGate evidence: `false`" in markdown
    assert "Merge authorized by SafetyGate evidence: `false`" in markdown


def test_repo_memory_rejects_authority_expanding_safety_gate_evidence() -> None:
    insights = _pattern_insights()
    insights["safety_gate_evidence"] = {
        "collection_status": "collected",
        "status": "safety_gate_evidence_observed",
        "source": "trajectory.safety_gate",
        "record_count": 1,
        "safe_fix_allowed_count": 1,
        "review_first_count": 0,
        "reporting_only_count": 1,
        "decision_boundary": {
            "automation_allowed": True,
            "patch_application_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }

    try:
        build_repo_memory_profile(
            pattern_insights=insights,
            benchmark_report=_benchmark_report(),
        )
    except ValueError as exc:
        assert "SafetyGate evidence expands authority: automation_allowed" in str(exc)
    else:
        raise AssertionError("expected authority-expanding SafetyGate evidence to fail")


def test_repo_memory_surfaces_trajectory_authority_evidence_without_authority() -> None:
    insights = _pattern_insights()
    insights["authority_boundary_evidence"] = {
        "collection_status": "collected",
        "status": "authority_boundary_evidence_observed",
        "source": "trajectory.authority_boundary",
        "record_count": 2,
        "review_first_count": 1,
        "auto_fix_allowed_count": 1,
        "reporting_only_count": 2,
        "sources": ["pr_quality", "trajectory_store"],
        "decision_boundary": {
            "automation_allowed": False,
            "patch_application_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
            "automatic_security_fix_allowed": False,
            "automatic_dismissal_allowed": False,
        },
    }

    profile = build_repo_memory_profile(
        pattern_insights=insights,
        benchmark_report=_benchmark_report(),
    )

    authority = profile["trajectory_authority_evidence"]
    assert profile["inputs"]["trajectory_authority_record_count"] == 2
    assert authority["collection_status"] == "collected"
    assert authority["status"] == "authority_boundary_evidence_observed"
    assert authority["record_count"] == 2
    assert authority["review_first_count"] == 1
    assert authority["auto_fix_allowed_count"] == 1
    assert authority["reporting_only_count"] == 2
    assert authority["sources"] == ["pr_quality", "trajectory_store"]
    assert authority["decision_boundary"] == {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "automatic_security_fix_allowed": False,
        "automatic_dismissal_allowed": False,
    }

    markdown = render_markdown(profile)
    assert "## Trajectory authority boundary evidence" in markdown
    assert "Patch automation allowed by trajectory authority: `false`" in markdown
    assert "Security dismissal allowed by trajectory authority: `false`" in markdown


def test_repo_memory_rejects_authority_expanding_trajectory_authority_evidence() -> None:
    insights = _pattern_insights()
    insights["authority_boundary_evidence"] = {
        "collection_status": "collected",
        "status": "authority_boundary_evidence_observed",
        "source": "trajectory.authority_boundary",
        "record_count": 1,
        "review_first_count": 0,
        "auto_fix_allowed_count": 1,
        "reporting_only_count": 1,
        "sources": ["pr_quality"],
        "decision_boundary": {
            "automation_allowed": False,
            "patch_application_allowed": True,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
            "automatic_security_fix_allowed": False,
            "automatic_dismissal_allowed": False,
        },
    }

    try:
        build_repo_memory_profile(
            pattern_insights=insights,
            benchmark_report=_benchmark_report(),
        )
    except ValueError as exc:
        assert "trajectory authority evidence expands authority" in str(exc)
    else:
        raise AssertionError("expected authority expansion to be rejected")
