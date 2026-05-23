from __future__ import annotations

import json
from pathlib import Path

from sdetkit.reliability_spine_alignment import (
    SPINE_STAGES,
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


def test_alignment_statuses_show_aligned_partial_and_planned_layers() -> None:
    report = build_alignment_report()
    status_counts = report["status_counts"]

    assert status_counts["aligned"] >= 8
    assert status_counts["partially_aligned"] >= 10
    assert status_counts.get("planned", 0) == 0
    assert report["next_recommended_pr"] == "feature/repo-memory-live-proof-outcomes"


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
    assert "repo_memory" in gaps_by_module
    assert "isolated_proof_runner" in gaps_by_module
    assert "git_inventory_collector" in gaps_by_module
    assert any("protected_verifier" in gap for gap in gaps_by_module["maintenance_autopilot"])
    assert any("semantic equivalence" in gap for gap in gaps_by_module["patch_scorer"])
    assert any("semantic equivalence" in gap for gap in gaps_by_module["protected_verifier"])
    assert any("network isolation" in gap for gap in gaps_by_module["isolated_proof_runner"])
    assert any("workflow evidence" in gap for gap in gaps_by_module["git_inventory_collector"])
    assert any("anti-cheat" in gap for gap in gaps_by_module["replayable_benchmark_harness"])
    assert any("live Git-grounded" in gap for gap in gaps_by_module["repo_memory"])


def test_alignment_markdown_renders_operator_audit() -> None:
    markdown = render_alignment_markdown(build_alignment_report())

    assert "# Reliability spine alignment audit" in markdown
    assert "## Status counts" in markdown
    assert "## Stage counts" in markdown
    assert "## Components" in markdown
    assert "`check_intelligence`: `aligned`" in markdown
    assert "`maintenance_autopilot`: `partially_aligned`" in markdown
    assert "`trajectory_pattern_insights`: `aligned`" in markdown
    assert "`patch_scorer`: `partially_aligned`" in markdown
    assert "`protected_verifier`: `partially_aligned`" in markdown
    assert "`replayable_benchmark_harness`: `partially_aligned`" in markdown
    assert "`repo_memory`: `partially_aligned`" in markdown
    assert "`isolated_proof_runner`: `partially_aligned`" in markdown
    assert "`git_inventory_collector`: `partially_aligned`" in markdown


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
    assert saved["next_recommended_pr"] == "feature/repo-memory-live-proof-outcomes"
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
    }

    assert "maintenance_autopilot" not in report_modules
    assert all(component.module for component in components)
