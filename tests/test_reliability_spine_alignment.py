from __future__ import annotations

import json
from pathlib import Path

from sdetkit.reliability_spine_alignment import (
    FLAKY_TEST_REGISTRY_EVIDENCE_MODULE,
    NEXT_RECOMMENDED_PR,
    PR_QUALITY_LIVE_WORKSPACE_MODULE,
    REPO_MEMORY_PROFILE_HISTORY_MODULE,
    SECURITY_FINDING_DIAGNOSIS_MODULE,
    SECURITY_REVIEWED_DISPOSITION_HISTORY_MODULE,
    SPINE_STAGES,
    TRUSTED_FLAKY_TEST_REGISTRY_PRODUCER_MODULE,
    TRUSTED_HISTORY_EVIDENCE_MODULE,
    TRUSTED_TEST_OBSERVATION_CAPTURE_MODULE,
    TRUSTED_TEST_OBSERVATION_CLASSIFICATION_MODULE,
    TRUSTED_TEST_OBSERVATION_HISTORY_MODULE,
    build_alignment_components,
    build_alignment_report,
    main,
    render_alignment_markdown,
)


def test_alignment_components_cover_current_reliability_spine() -> None:
    report = build_alignment_report()
    components = report["components"]
    modules = {component["module"] for component in components}

    assert report["schema_version"] == "sdetkit.reliability_spine_alignment.v1"
    assert report["component_count"] >= 15
    assert "check_intelligence" in modules
    assert "trajectory_store" in modules
    assert "trajectory_history_report" in modules
    assert "trajectory_pattern_insights" in modules
    assert "maintenance_autopilot" in modules
    assert "patch_scorer" in modules
    assert "protected_verifier" in modules
    assert "replayable_benchmark_harness" in modules
    assert "repo_memory" in modules
    assert "isolated_proof_runner" in modules
    assert "git_inventory_collector" in modules
    assert "network_boundary" in modules
    assert "proof_runtime_guard" in modules
    assert "pr_quality_runtime_proof_artifacts" in modules
    assert PR_QUALITY_LIVE_WORKSPACE_MODULE in modules
    assert REPO_MEMORY_PROFILE_HISTORY_MODULE in modules
    assert TRUSTED_HISTORY_EVIDENCE_MODULE in modules
    assert FLAKY_TEST_REGISTRY_EVIDENCE_MODULE in modules
    assert TRUSTED_FLAKY_TEST_REGISTRY_PRODUCER_MODULE in modules
    assert TRUSTED_TEST_OBSERVATION_CAPTURE_MODULE in modules
    assert TRUSTED_TEST_OBSERVATION_HISTORY_MODULE in modules
    assert TRUSTED_TEST_OBSERVATION_CLASSIFICATION_MODULE in modules
    assert SECURITY_FINDING_DIAGNOSIS_MODULE in modules
    assert SECURITY_REVIEWED_DISPOSITION_HISTORY_MODULE in modules


def test_alignment_statuses_show_aligned_partial_and_planned_layers() -> None:
    report = build_alignment_report()
    status_counts = report["status_counts"]

    assert status_counts["aligned"] >= 13
    assert status_counts["partially_aligned"] >= 6
    assert status_counts.get("planned", 0) == 0
    assert report["next_recommended_pr"] == NEXT_RECOMMENDED_PR


def test_alignment_stage_counts_cover_every_spine_stage() -> None:
    report = build_alignment_report()
    stage_counts = report["stage_counts"]

    for stage in SPINE_STAGES:
        assert stage in stage_counts
        assert stage_counts[stage] >= 1


def test_alignment_identifies_safe_automation_gaps() -> None:
    report = build_alignment_report()
    gaps_by_module = {item["module"]: item["gaps"] for item in report["gaps"]}

    assert "maintenance_autopilot" in gaps_by_module
    assert "patch_scorer" in gaps_by_module
    assert "protected_verifier" in gaps_by_module
    assert "replayable_benchmark_harness" in gaps_by_module
    assert "repo_memory" not in gaps_by_module
    assert "isolated_proof_runner" in gaps_by_module
    assert "git_inventory_collector" not in gaps_by_module
    assert "network_boundary" not in gaps_by_module
    assert "proof_runtime_guard" in gaps_by_module
    assert "pr_quality_runtime_proof_artifacts" not in gaps_by_module
    assert "current_head_failure_bundle" not in gaps_by_module
    assert "remediation_plan_engine" not in gaps_by_module
    assert "operator_evidence_loop" not in gaps_by_module
    assert PR_QUALITY_LIVE_WORKSPACE_MODULE not in gaps_by_module
    assert REPO_MEMORY_PROFILE_HISTORY_MODULE not in gaps_by_module
    assert TRUSTED_HISTORY_EVIDENCE_MODULE not in gaps_by_module
    assert TRUSTED_FLAKY_TEST_REGISTRY_PRODUCER_MODULE not in gaps_by_module
    assert TRUSTED_TEST_OBSERVATION_CAPTURE_MODULE not in gaps_by_module
    assert TRUSTED_TEST_OBSERVATION_HISTORY_MODULE not in gaps_by_module
    assert TRUSTED_TEST_OBSERVATION_CLASSIFICATION_MODULE not in gaps_by_module
    assert FLAKY_TEST_REGISTRY_EVIDENCE_MODULE not in gaps_by_module
    assert SECURITY_FINDING_DIAGNOSIS_MODULE not in gaps_by_module
    assert SECURITY_REVIEWED_DISPOSITION_HISTORY_MODULE not in gaps_by_module
    assert "adaptive_diagnosis" not in gaps_by_module
    assert any("protected_verifier" in gap for gap in gaps_by_module["maintenance_autopilot"])
    assert any("semantic equivalence" in gap for gap in gaps_by_module["patch_scorer"])
    assert any("semantic equivalence" in gap for gap in gaps_by_module["protected_verifier"])
    assert not any("network-isolated" in gap for gap in gaps_by_module["isolated_proof_runner"])
    assert any("external filesystem" in gap for gap in gaps_by_module["isolated_proof_runner"])
    assert any("containment" in gap for gap in gaps_by_module["replayable_benchmark_harness"])
    assert not any("PR Quality" in gap for gap in gaps_by_module["replayable_benchmark_harness"])
    assert "repo_memory" not in gaps_by_module
    assert "network_boundary" not in gaps_by_module
    assert any("external filesystem" in gap for gap in gaps_by_module["proof_runtime_guard"])


def test_alignment_closes_pr_quality_registry_visibility_without_authority() -> None:
    components = {item.module: item for item in build_alignment_components()}
    registry = components[FLAKY_TEST_REGISTRY_EVIDENCE_MODULE]
    producer = components[TRUSTED_FLAKY_TEST_REGISTRY_PRODUCER_MODULE]
    memory = components["repo_memory"]
    history = components[REPO_MEMORY_PROFILE_HISTORY_MODULE]
    trusted = components[TRUSTED_HISTORY_EVIDENCE_MODULE]
    runtime = components["pr_quality_runtime_proof_artifacts"]
    report = components["pr_quality_action_report"]

    assert registry.status == "aligned"
    assert registry.gaps == ()
    assert "aggregate-only" in registry.recommended_next_action
    assert "PR Quality" in registry.recommended_next_action

    assert "aggregate accepted-main context" in (producer.recommended_next_action)
    assert "PR Quality" in producer.recommended_next_action

    assert not any("trusted-main workflow population" in gap for gap in memory.gaps)
    assert not any("PR Quality visibility" in gap for gap in memory.gaps)
    assert memory.gaps == ()
    assert "runtime-verified network-boundary evidence" in memory.recommended_next_action

    assert "aggregate producer-vetted registry context" in history.role
    assert "aggregate-only" in history.recommended_next_action
    assert "aggregate producer-vetted registry context" in trusted.role
    assert "registry aggregate" in trusted.recommended_next_action
    assert "aggregate producer-vetted registry evidence" in runtime.role
    assert "registry aggregate visibility" in runtime.recommended_next_action
    assert "aggregate producer-vetted registry summaries" in report.role
    assert "no-authority" in report.recommended_next_action


def test_alignment_closes_exact_failure_and_git_profile_visibility_gaps() -> None:
    components = {item.module: item for item in build_alignment_components()}

    adaptive = components["adaptive_diagnosis"]
    scorer = components["patch_scorer"]
    inventory = components["git_inventory_collector"]

    assert adaptive.status == "aligned"
    assert adaptive.gaps == ()
    assert "confidence-scored exact-failure" in adaptive.recommended_next_action
    assert "review-first" in adaptive.recommended_next_action

    assert scorer.status == "partially_aligned"
    assert "existing PR Quality candidate handoff" in scorer.recommended_next_action
    assert "unwired from automation" in scorer.recommended_next_action

    assert inventory.status == "aligned"
    assert inventory.gaps == ()
    assert "runtime-proof-artifacts.json" in inventory.existing_artifacts
    assert "pr_quality_action_report" in inventory.integration_points
    assert "multi-profile visibility" in inventory.recommended_next_action
    assert NEXT_RECOMMENDED_PR == "none"


def test_alignment_markdown_renders_operator_audit() -> None:
    markdown = render_alignment_markdown(build_alignment_report())

    assert "# Reliability spine alignment audit" in markdown
    assert "## Status counts" in markdown
    assert "## Stage counts" in markdown
    assert "## Components" in markdown
    assert "`check_intelligence`: `aligned`" in markdown
    assert "`maintenance_autopilot`: `partially_aligned`" in markdown
    assert "`adaptive_diagnosis`: `aligned`" in markdown
    assert "`trajectory_pattern_insights`: `aligned`" in markdown
    assert "`current_head_failure_bundle`: `aligned`" in markdown
    assert "`remediation_plan_engine`: `aligned`" in markdown
    assert "`operator_evidence_loop`: `aligned`" in markdown
    assert "`patch_scorer`: `partially_aligned`" in markdown
    assert "`protected_verifier`: `partially_aligned`" in markdown
    assert "`replayable_benchmark_harness`: `partially_aligned`" in markdown
    assert "`repo_memory`: `aligned`" in markdown
    assert "`isolated_proof_runner`: `partially_aligned`" in markdown
    assert "`git_inventory_collector`: `aligned`" in markdown
    assert "`network_boundary`: `aligned`" in markdown
    assert "`proof_runtime_guard`: `partially_aligned`" in markdown
    assert "`pr_quality_runtime_proof_artifacts`: `aligned`" in markdown
    assert f"`{PR_QUALITY_LIVE_WORKSPACE_MODULE}`: `aligned`" in markdown
    assert f"`{REPO_MEMORY_PROFILE_HISTORY_MODULE}`: `aligned`" in markdown
    assert f"`{TRUSTED_HISTORY_EVIDENCE_MODULE}`: `aligned`" in markdown
    assert f"`{FLAKY_TEST_REGISTRY_EVIDENCE_MODULE}`: `aligned`" in markdown
    assert f"`{TRUSTED_FLAKY_TEST_REGISTRY_PRODUCER_MODULE}`: `aligned`" in markdown
    assert f"`{TRUSTED_TEST_OBSERVATION_CAPTURE_MODULE}`: `aligned`" in markdown
    assert f"`{TRUSTED_TEST_OBSERVATION_HISTORY_MODULE}`: `aligned`" in markdown
    assert f"`{SECURITY_FINDING_DIAGNOSIS_MODULE}`: `aligned`" in markdown
    assert f"`{SECURITY_REVIEWED_DISPOSITION_HISTORY_MODULE}`: `aligned`" in markdown


def test_alignment_cli_writes_json_and_markdown(tmp_path: Path, capsys) -> None:
    json_out = tmp_path / "alignment.json"
    markdown_out = tmp_path / "alignment.md"

    rc = main(
        [
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    saved = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = markdown_out.read_text(encoding="utf-8")

    assert printed["report"]["component_count"] == saved["component_count"]
    assert saved["next_recommended_pr"] == NEXT_RECOMMENDED_PR
    assert "Reliability spine alignment audit" in markdown


def test_alignment_component_validation_rejects_bad_status() -> None:
    from sdetkit import reliability_spine_alignment as alignment

    try:
        alignment._component(
            module="bad",
            role="bad",
            status="unknown_status",
            stages=("evidence",),
        )
    except ValueError as exc:
        assert "invalid alignment status" in str(exc)
    else:
        raise AssertionError("expected invalid status to raise")


def test_alignment_component_validation_rejects_bad_stage() -> None:
    from sdetkit import reliability_spine_alignment as alignment

    try:
        alignment._component(
            module="bad",
            role="bad",
            status="aligned",
            stages=("not_a_stage",),
        )
    except ValueError as exc:
        assert "invalid spine stages" in str(exc)
    else:
        raise AssertionError("expected invalid stage to raise")


def test_alignment_has_no_behavior_mutation_surfaces() -> None:
    components = build_alignment_components()
    report_modules = {
        "reliability_spine_alignment",
        "trajectory_history_report",
        "pr_quality_action_report",
        "patch_scorer",
        "protected_verifier",
        "replayable_benchmark_harness",
        "repo_memory",
        "isolated_proof_runner",
        "git_inventory_collector",
        "network_boundary",
        "proof_runtime_guard",
        "pr_quality_runtime_proof_artifacts",
        PR_QUALITY_LIVE_WORKSPACE_MODULE,
        REPO_MEMORY_PROFILE_HISTORY_MODULE,
        TRUSTED_HISTORY_EVIDENCE_MODULE,
        FLAKY_TEST_REGISTRY_EVIDENCE_MODULE,
        TRUSTED_FLAKY_TEST_REGISTRY_PRODUCER_MODULE,
        TRUSTED_TEST_OBSERVATION_CAPTURE_MODULE,
        TRUSTED_TEST_OBSERVATION_HISTORY_MODULE,
        SECURITY_FINDING_DIAGNOSIS_MODULE,
        SECURITY_REVIEWED_DISPOSITION_HISTORY_MODULE,
    }

    assert "maintenance_autopilot" not in report_modules
    assert all(component.module for component in components)


def test_current_head_failure_bundle_alignment_is_closed() -> None:
    components = {item.module: item for item in build_alignment_components()}

    component = components["current_head_failure_bundle"]

    assert component.status == "aligned"
    assert component.gaps == ()
    assert "trajectory" in component.stages
    assert "history" in component.stages
    assert "trajectory_store" in component.integration_points
    assert "trajectory_history_report" in component.integration_points
    assert (
        component.recommended_next_action
        == "keep same-head trajectory links reporting-only and authority-denied"
    )


def test_remediation_plan_engine_alignment_is_closed() -> None:
    components = {item.module: item for item in build_alignment_components()}

    component = components["remediation_plan_engine"]

    assert component.status == "aligned"
    assert component.gaps == ()
    assert "reporting" in component.stages
    assert "patch_scorer" in component.integration_points
    assert "protected_verifier" in component.integration_points
    assert "ProtectedVerifier remediation-plan context" in component.existing_artifacts
    assert (
        component.recommended_next_action == "keep remediation-plan context reporting-only "
        "until structural and semantic proof mature"
    )


def test_operator_evidence_loop_alignment_is_closed() -> None:
    components = {item.module: item for item in build_alignment_components()}

    component = components["operator_evidence_loop"]

    assert component.status == "aligned"
    assert component.gaps == ()
    assert "history" in component.stages
    assert "proof" in component.stages
    assert "trajectory_history_report" in component.integration_points
    assert "patch_scorer" in component.integration_points
    assert "protected_verifier" in component.integration_points
    assert "read-only reporting projections" in component.existing_artifacts
    assert (
        component.recommended_next_action == "keep producer artifacts optional, "
        "reporting-only, and excluded from "
        "operator classification"
    )


def test_trusted_test_observation_history_alignment_is_closed() -> None:
    components = {item.module: item for item in build_alignment_components()}

    component = components[TRUSTED_TEST_OBSERVATION_HISTORY_MODULE]

    assert component.status == "aligned"
    assert component.gaps == ()
    assert component.stages == (
        "evidence",
        "history",
        "reporting",
    )
    assert component.existing_artifacts == (
        "trusted-test-observation-history.jsonl",
        "trusted-test-observation-history-summary.json",
        "trusted-test-observation-history-summary.md",
    )
    assert TRUSTED_TEST_OBSERVATION_CAPTURE_MODULE in component.integration_points
    assert "CI Full CI lane" in component.integration_points
    assert "RepoMemory Profile History workflow" in component.integration_points
    assert TRUSTED_TEST_OBSERVATION_CLASSIFICATION_MODULE in component.integration_points
    assert (
        component.recommended_next_action
        == "keep immutable history as the only input to the dedicated "
        "fingerprint classification contract"
    )


def test_flaky_registry_alignment_starts_after_persisted_observation_history() -> None:
    components = {item.module: item for item in build_alignment_components()}

    capture = components[TRUSTED_TEST_OBSERVATION_CAPTURE_MODULE]
    history = components[TRUSTED_TEST_OBSERVATION_HISTORY_MODULE]
    classification = components[TRUSTED_TEST_OBSERVATION_CLASSIFICATION_MODULE]
    producer = components[TRUSTED_FLAKY_TEST_REGISTRY_PRODUCER_MODULE]
    registry = components[FLAKY_TEST_REGISTRY_EVIDENCE_MODULE]
    repo_memory = components["repo_memory"]

    assert (
        capture.recommended_next_action
        == "preserve capture as raw input and route it only through trusted "
        "observation history before any flaky-test classification"
    )
    assert "RepoMemory Profile History workflow" in history.integration_points
    assert classification.status == "aligned"
    assert classification.gaps == ()

    assert producer.status == "aligned"
    assert producer.gaps == ()
    assert (
        producer.recommended_next_action
        == "keep producer-vetted registry output advisory-only while exposing aggregate accepted-main context to PR Quality"
    )

    assert registry.status == "aligned"
    assert registry.gaps == ()
    assert "RepoMemory Profile History workflow" in registry.integration_points
    assert TRUSTED_FLAKY_TEST_REGISTRY_PRODUCER_MODULE in registry.integration_points
    assert "repo_memory" in registry.integration_points

    assert TRUSTED_TEST_OBSERVATION_HISTORY_MODULE in repo_memory.integration_points
    assert not any(
        "producer-vetted fingerprint registry population" in gap for gap in repo_memory.gaps
    )
    assert not any("trusted-main workflow population" in gap for gap in repo_memory.gaps)
    assert not any("PR Quality visibility" in gap for gap in repo_memory.gaps)


def test_trusted_observation_classification_alignment_is_closed() -> None:
    components = {item.module: item for item in build_alignment_components()}

    component = components[TRUSTED_TEST_OBSERVATION_CLASSIFICATION_MODULE]

    assert component.status == "aligned"
    assert component.gaps == ()
    assert component.stages == (
        "evidence",
        "diagnosis",
        "history",
        "reporting",
    )
    assert component.existing_artifacts == (
        "trusted-test-observation-classification.json",
        "trusted-test-observation-classification.md",
    )
    assert TRUSTED_TEST_OBSERVATION_HISTORY_MODULE in component.integration_points
    assert (
        component.recommended_next_action
        == "keep the dedicated artifact advisory-only and route it only "
        "through the trusted producer fingerprint adapter before workflow integration"
    )


def test_trusted_producer_validation_handoff_alignment_is_closed() -> None:
    components = {item.module: item for item in build_alignment_components()}

    producer = components[TRUSTED_FLAKY_TEST_REGISTRY_PRODUCER_MODULE]
    registry = components[FLAKY_TEST_REGISTRY_EVIDENCE_MODULE]
    repo_memory = components["repo_memory"]

    assert producer.status == "aligned"
    assert producer.gaps == ()
    assert TRUSTED_TEST_OBSERVATION_CLASSIFICATION_MODULE in producer.integration_points
    assert "classification_handoff summary" in producer.existing_artifacts
    assert (
        producer.recommended_next_action
        == "keep producer-vetted registry output advisory-only while exposing aggregate accepted-main context to PR Quality"
    )

    assert registry.status == "aligned"
    assert registry.gaps == ()
    assert TRUSTED_FLAKY_TEST_REGISTRY_PRODUCER_MODULE in registry.integration_points
    assert "repo_memory" in registry.integration_points
    assert "RepoMemory Profile History workflow" in registry.integration_points
    assert (
        registry.recommended_next_action
        == "keep producer-vetted registry evidence aggregate-only and advisory-only in PR Quality"
    )
    assert "PR Quality" in registry.recommended_next_action

    assert not any(
        "producer-vetted fingerprint registry population" in gap for gap in repo_memory.gaps
    )
    assert not any("trusted-main workflow population" in gap for gap in repo_memory.gaps)
    assert not any("PR Quality visibility" in gap for gap in repo_memory.gaps)


def test_alignment_closes_verified_network_backend_contract_without_overclaim() -> None:
    components = {item.module: item for item in build_alignment_components()}
    network = components["network_boundary"]
    runner = components["isolated_proof_runner"]
    benchmark = components["replayable_benchmark_harness"]
    memory = components["repo_memory"]

    assert network.status == "aligned"
    assert network.gaps == ()
    assert "runtime-probe" in network.role
    assert "controlled loopback backend probe" in network.existing_artifacts
    assert "filesystem or process containment" in network.recommended_next_action

    assert runner.status == "partially_aligned"
    assert not any("network-isolated" in gap for gap in runner.gaps)
    assert any("external filesystem" in gap for gap in runner.gaps)
    assert "runtime-reprobed network isolation" in runner.recommended_next_action

    assert benchmark.status == "partially_aligned"
    assert any("external filesystem" in gap for gap in benchmark.gaps)
    assert "verified network-backend contract" in benchmark.recommended_next_action
    assert "authority" in benchmark.recommended_next_action

    assert memory.status == "aligned"
    assert memory.gaps == ()
    assert "runtime-verified network-boundary evidence" in memory.recommended_next_action
