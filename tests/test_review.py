from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from sdetkit import review
from sdetkit.review_engine import plan_adaptive_probes


def test_review_repeated_run_tracks_changes_and_compare_artifacts(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    data = tmp_path / "orders.csv"
    out = tmp_path / "review-out"

    data.write_text("id,status\nA1,ok\n", encoding="utf-8")
    rc1, payload1, _, _ = review.run_review(
        target=data,
        out_dir=out,
        workspace_root=workspace,
    )
    assert rc1 == 0
    assert payload1["workflow"] == "review"
    assert payload1["history"]["has_previous_review"] is False

    data.write_text("id,status\nA1,ok\nA1,ok\n", encoding="utf-8")
    rc2, payload2, json_path, txt_path = review.run_review(
        target=data,
        out_dir=out,
        workspace_root=workspace,
    )

    assert rc2 == 2
    assert json_path.exists()
    assert txt_path.exists()
    assert payload2["history"]["has_previous_review"] is True
    assert payload2["changed_since_previous"][0]["kind"] in {
        "status",
        "severity",
        "action_pressure",
        "stable",
    }
    assert "inspect_compare_json" in payload2["artifact_index"]
    assert payload2["adaptive_review"]["escalation"]["needed"] is True
    assert "review_plan_json" in payload2["artifact_index"]
    assert "review_tracks_json" in payload2["artifact_index"]


def test_review_repo_plus_data_surfaces_cross_surface_conflict(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        "[project]\nname='demo'\nversion='0.1.0'\n", encoding="utf-8"
    )
    (repo / "data.csv").write_text("id,status\nA1,ok\n", encoding="utf-8")

    rc, payload, _, _ = review.run_review(
        target=repo,
        out_dir=tmp_path / "out",
        workspace_root=tmp_path / "workspace",
        no_workspace=True,
    )

    assert rc == 2
    assert payload["detection"]["repo_like"] is True
    assert payload["detection"]["data_like"] is True
    assert payload["conflicting_evidence"]
    assert payload["contradiction_graph"]["clusters"]
    assert payload["adaptive_review"]["escalation"]["needed"] is True


def test_cli_review_command_outputs_json(tmp_path: Path) -> None:
    data = tmp_path / "events.csv"
    data.write_text("id,type\nE1,open\n", encoding="utf-8")

    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "review",
            str(data),
            "--workspace-root",
            str(tmp_path / "workspace"),
            "--format",
            "json",
            "--no-workspace",
        ],
        text=True,
        capture_output=True,
    )

    assert run.returncode == 0
    payload = json.loads(run.stdout)
    assert payload["workflow"] == "review"
    assert payload["path"].endswith("events.csv")
    assert payload["schema_version"] == "sdetkit.review.v3"
    assert payload["contract_version"] == "sdetkit.review.contract.v1"
    assert "operator_summary" in payload
    assert payload["five_heads"]["schema_version"] == "sdetkit.review.five-heads.v1"


def test_cli_review_command_outputs_operator_json_contract_only(tmp_path: Path) -> None:
    data = tmp_path / "events.csv"
    out_dir = tmp_path / "out"
    data.write_text("id,type\nE1,open\n", encoding="utf-8")

    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "review",
            str(data),
            "--workspace-root",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(out_dir),
            "--format",
            "operator-json",
            "--no-workspace",
        ],
        text=True,
        capture_output=True,
    )

    assert run.returncode == 0
    payload = json.loads(run.stdout)
    assert payload["contract_version"] == "sdetkit.review.contract.v1"
    assert "situation" in payload
    assert "actions" in payload
    assert "workflow" not in payload
    artifact_payload = json.loads(
        (out_dir / "review-operator-summary.json").read_text(encoding="utf-8")
    )
    assert payload == artifact_payload


def test_cli_review_supports_work_id_and_context_for_ai_handoff(tmp_path: Path) -> None:
    data = tmp_path / "events.csv"
    data.write_text("id,type\nE1,open\n", encoding="utf-8")
    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "review",
            str(data),
            "--workspace-root",
            str(tmp_path / "workspace"),
            "--format",
            "operator-json",
            "--work-id",
            "INC-4821",
            "--work-context",
            "owner=platform",
            "--work-context",
            "component=review",
            "--no-workspace",
        ],
        text=True,
        capture_output=True,
    )
    assert run.returncode == 0
    payload = json.loads(run.stdout)
    assert payload["request_context"]["work_id"] == "INC-4821"
    assert payload["request_context"]["work_context"] == {
        "owner": "platform",
        "component": "review",
    }


def test_cli_review_code_scan_report_influences_adaptive_security_context(tmp_path: Path) -> None:
    data = tmp_path / "events.csv"
    scan = tmp_path / "scan.sarif"
    data.write_text("id,type\nE1,open\n", encoding="utf-8")
    scan.write_text(
        json.dumps(
            {
                "version": "2.1.0",
                "runs": [
                    {
                        "tool": {"driver": {"name": "CodeQL"}},
                        "results": [
                            {"ruleId": "py/sql-injection", "level": "error"},
                            {"ruleId": "py/logging", "level": "warning"},
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "review",
            str(data),
            "--workspace-root",
            str(tmp_path / "workspace"),
            "--format",
            "json",
            "--code-scan-json",
            str(scan),
            "--no-workspace",
        ],
        text=True,
        capture_output=True,
    )
    assert run.returncode == 2
    payload = json.loads(run.stdout)
    assert payload["code_scanning"]["tool"] == "CodeQL"
    assert payload["code_scanning"]["blocking_alerts"] == 1
    assert payload["adaptive_review"]["ai_assistant"]["available"] is True
    assert "code_scan_json" in payload["artifact_index"]


def test_review_profiles_change_judgment_and_artifacts_for_same_input(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    data = tmp_path / "events.csv"
    out_release = tmp_path / "out-release"
    out_monitor = tmp_path / "out-monitor"
    data.write_text("id,type\nE1,open\nE1,open\n", encoding="utf-8")

    release_rc, release_payload, _, _ = review.run_review(
        target=data,
        out_dir=out_release,
        workspace_root=workspace,
        profile="release",
    )
    monitor_rc, monitor_payload, _, _ = review.run_review(
        target=data,
        out_dir=out_monitor,
        workspace_root=workspace,
        profile="monitor",
    )

    assert release_rc == 2
    assert monitor_rc == 2
    assert release_payload["status"] == "fail"
    assert monitor_payload["status"] == "watch"
    assert release_payload["profile"]["name"] == "release"
    assert monitor_payload["profile"]["name"] == "monitor"
    assert release_payload["profile"]["packet_type"] == "release_gate"
    assert monitor_payload["profile"]["packet_type"] == "trend_watch"
    assert release_payload["artifact_index"]["profile_packet_json"].endswith(
        "release-decision.json"
    )
    assert monitor_payload["artifact_index"]["profile_packet_json"].endswith("trend-watch.json")
    assert "review_plan_json" in release_payload["artifact_index"]
    assert "review_tracks_json" in monitor_payload["artifact_index"]
    release_now = [
        item for item in release_payload["prioritized_actions"] if item.get("tier") == "now"
    ]
    monitor_now = [
        item for item in monitor_payload["prioritized_actions"] if item.get("tier") == "now"
    ]
    assert len(release_now) >= len(monitor_now)


def test_review_profile_packets_and_text_are_profile_specific(tmp_path: Path) -> None:
    data = tmp_path / "events.csv"
    workspace = tmp_path / "workspace"
    data.write_text("id,type\nE1,open\nE1,open\n", encoding="utf-8")
    profiles = {
        "release": ("release-decision.json", "release_gate_decision:"),
        "triage": ("incident-board.json", "incident_board:"),
        "forensics": ("evidence-ledger.json", "evidence_ledger:"),
        "monitor": ("trend-watch.json", "trend_watch:"),
    }

    for profile, (packet_name, marker) in profiles.items():
        out_dir = tmp_path / f"out-{profile}"
        rc, payload, _, txt_path = review.run_review(
            target=data,
            out_dir=out_dir,
            workspace_root=workspace,
            profile=profile,
        )
        assert rc == 2
        packet_path = out_dir / packet_name
        assert packet_path.exists()
        packet_payload = json.loads(packet_path.read_text(encoding="utf-8"))
        assert packet_payload["profile"] == profile
        assert packet_payload["packet_type"] == payload["profile"]["packet_type"]
        assert payload["artifact_index"]["profile_packet_json"] == packet_path.as_posix()
        text = txt_path.read_text(encoding="utf-8")
        assert marker in text
        assert "adaptive_review:" in text
        assert "likely_issue_tracks:" in text
        assert "operator_snapshot:" in text
        assert "five_heads:" in text


def test_review_operator_summary_artifact_written(tmp_path: Path) -> None:
    data = tmp_path / "events.csv"
    workspace = tmp_path / "workspace"
    out_dir = tmp_path / "out"
    data.write_text("id,type\nE1,open\nE1,open\n", encoding="utf-8")

    rc, payload, _, _ = review.run_review(
        target=data,
        out_dir=out_dir,
        workspace_root=workspace,
    )

    assert rc == 2
    artifact_path = Path(payload["artifact_index"]["operator_summary_json"])
    assert artifact_path.exists()
    operator_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert operator_payload["contract_version"] == "sdetkit.review.contract.v1"
    assert "judgment_rationale" in operator_payload
    assert "actions" in operator_payload
    assert "five_heads" in operator_payload
    assert operator_payload["adaptive_database"]["schema_version"] == (
        "sdetkit.review.adaptive-database.v1"
    )
    assert operator_payload["doctor_gate_contract"]["enforced_each_run"] is True


def test_cli_review_interactive_navigator_outputs_selected_section(tmp_path: Path) -> None:
    data = tmp_path / "events.csv"
    data.write_text("id,type\nE1,open\n", encoding="utf-8")

    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "review",
            str(data),
            "--workspace-root",
            str(tmp_path / "workspace"),
            "--format",
            "text",
            "--interactive",
            "--no-workspace",
        ],
        input="1\nq\n",
        text=True,
        capture_output=True,
    )

    assert run.returncode == 0
    assert "SDETKit interactive review navigator" in run.stdout
    assert "[situation]" in run.stdout


def test_review_clean_evidence_stops_early_without_deepen_stage(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    data = tmp_path / "clean.csv"
    out = tmp_path / "out-clean"
    data.write_text("id,status\nA1,ok\n", encoding="utf-8")

    rc, payload, _, _ = review.run_review(
        target=data,
        out_dir=out,
        workspace_root=workspace,
    )

    assert rc == 0
    assert payload["adaptive_review"]["escalation"]["needed"] is False
    assert payload["adaptive_review"]["stop_decision"]["stop"] is True
    assert "inspect_compare_json" not in payload["artifact_index"]
    assert payload["adaptive_review"]["executed_probes"] == []


def test_review_tracks_ranked_with_supporting_and_conflicting_evidence(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    workspace = tmp_path / "workspace"
    out = tmp_path / "out"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        "[project]\nname='demo'\nversion='0.1.0'\n", encoding="utf-8"
    )
    (repo / "events.csv").write_text("id,type\nE1,open\nE1,open\n", encoding="utf-8")

    rc, payload, _, _ = review.run_review(target=repo, out_dir=out, workspace_root=workspace)

    assert rc == 2
    tracks = payload["likely_issue_tracks"]
    assert tracks
    assert tracks[0]["supporting_evidence"]
    assert "verification_steps" in tracks[0]
    assert isinstance(tracks[0]["conflicting_evidence"], list)
    assert "probe_impact" in tracks[0]
    assert isinstance(payload["evidence_edges"], list)


def test_review_contradiction_cluster_triggers_probe_selection(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    out = tmp_path / "out"
    workspace = tmp_path / "workspace"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        "[project]\nname='demo'\nversion='0.1.0'\n", encoding="utf-8"
    )
    (repo / "events.csv").write_text("id,type\nE1,open\nE1,open\n", encoding="utf-8")

    rc, payload, _, _ = review.run_review(target=repo, out_dir=out, workspace_root=workspace)

    assert rc == 2
    clusters = payload["contradiction_graph"]["clusters"]
    assert clusters
    probe_ids = {row["probe_id"] for row in payload["adaptive_review"]["executed_probes"]}
    assert "probe:inspect-compare" in probe_ids
    budget = payload["adaptive_review"]["probe_budget"]
    assert budget["total"] == 100
    assert budget["spent"] > 0
    assert budget["remaining"] >= 0
    registry = payload["adaptive_review"]["probe_registry"]
    assert any(row["probe_id"] == "probe:inspect-compare" for row in registry)
    inspect_compare = next(
        row
        for row in payload["adaptive_review"]["executed_probes"]
        if row["probe_id"] == "probe:inspect-compare"
    )
    assert inspect_compare["cost"] == 55
    assert inspect_compare["bounded_contract"]["max_runtime_seconds"] == 20
    assert inspect_compare["chain"]["enabled"] is True


def test_probe_budget_skips_when_budget_is_exhausted() -> None:
    decision = plan_adaptive_probes(
        detection={"workspace_like": True, "data_like": True},
        profile_name="forensics",
        findings=[{"priority": 90, "kind": "inspect"}],
        contradiction_graph={
            "flat_contradictions": [{"id": "c1"}],
            "clusters": [{"cluster_id": "x"}],
        },
        has_previous_review=True,
        changed=[{"kind": "status", "message": "changed"}],
        budget_total=70,
        confidence_score=0.2,
        confidence_threshold=0.45,
    )
    assert decision["executed_probes"]
    assert any(
        row["skip_reason"] == "probe budget exhausted by higher-value probes"
        for row in decision["skipped_probes"]
    )


def test_probe_registry_expands_scenarios_and_recommendations() -> None:
    decision = plan_adaptive_probes(
        detection={
            "workspace_like": True,
            "data_like": True,
            "repo_like": True,
            "inspect_compare_available": True,
        },
        profile_name="release",
        findings=[
            {"priority": 80, "kind": "doctor"},
            {"priority": 65, "kind": "inspect-project"},
        ],
        contradiction_graph={
            "flat_contradictions": [{"id": "c1"}],
            "clusters": [{"cluster_id": "x"}],
        },
        has_previous_review=True,
        changed=[{"kind": "status", "message": "changed"}],
        confidence_score=0.3,
        confidence_threshold=0.6,
    )
    registry_ids = {row["probe_id"] for row in decision["registry"]}
    assert {
        "probe:inspect-compare",
        "probe:workspace-history",
        "probe:doctor-delta",
        "probe:inspect-project-focus",
        "probe:artifact-integrity",
    }.issubset(registry_ids)
    recommendations = {row["probe_id"] for row in decision["recommendation_catalog"]}
    assert recommendations == registry_ids
    ai_packet = decision["ai_assistant"]
    assert ai_packet["schema_version"] == "sdetkit.review.ai-assistant.v1"
    assert ai_packet["available"] is True
    assert ai_packet["probe_catalog"] == decision["recommendation_catalog"]
    assert ai_packet["recommended_prompts"]
    playbook_workflows = {row["workflow"] for row in ai_packet["repo_playbooks"]}
    assert {"doctor", "gate-fast", "gate-release", "review", "inspect-project"}.issubset(
        playbook_workflows
    )
    assert ai_packet["alignment_contract"]["doctor_first"] is True


def test_review_adaptive_database_and_ai_handoff_contract(tmp_path: Path) -> None:
    data = tmp_path / "events.csv"
    data.write_text("id,type\nE1,open\nE1,open\n", encoding="utf-8")
    rc, payload, _, _ = review.run_review(
        target=data,
        out_dir=tmp_path / "out",
        workspace_root=tmp_path / "workspace",
        work_id="WI-555",
        work_context={"owner": "qa"},
        no_workspace=True,
    )
    assert rc == 2
    assert payload["adaptive_database"]["schema_version"] == "sdetkit.review.adaptive-database.v1"
    assert len(payload["adaptive_database"]["top5_actions"]) <= 5
    ai_packet = payload["adaptive_review"]["ai_assistant"]
    assert ai_packet["workflow_alignment"]["review_adaptive_enabled"] is True
    assert ai_packet["reviewer_engine_contract"]["five_heads_required"] is True
    assert ai_packet["doctor_gate_contract"]["doctor_first"] is True
    assert payload["doctor_gate_contract"]["gate_fast_required_for_promotion"] is True


def test_probe_memory_artifact_written_and_exposed(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    repo = tmp_path / "repo"
    data = repo / "events.csv"
    out = tmp_path / "out"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "pyproject.toml").write_text(
        "[project]\nname='demo'\nversion='0.1.0'\n", encoding="utf-8"
    )
    data.write_text("id,type\nE1,open\nE1,open\n", encoding="utf-8")

    rc, payload, _, _ = review.run_review(target=repo, out_dir=out, workspace_root=workspace)

    assert rc in {0, 2}
    probe_memory = payload["adaptive_review"]["probe_memory"]
    assert probe_memory["schema_version"] == "sdetkit.review.probe-memory.v1"
    assert isinstance(probe_memory["normalized_outcomes"], list)
    artifact = Path(probe_memory["workspace_artifact"])
    assert artifact.exists()
    stored = json.loads(artifact.read_text(encoding="utf-8"))
    assert stored["schema_version"] == "sdetkit.review.probe-memory.v1"
    assert "probe:inspect-compare" in stored.get("probes", {})


def test_probe_memory_history_adjusts_next_run_score_inputs(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    repo = tmp_path / "repo"
    data = repo / "events.csv"
    out = tmp_path / "out"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "pyproject.toml").write_text(
        "[project]\nname='demo'\nversion='0.1.0'\n", encoding="utf-8"
    )
    data.write_text("id,type\nE1,open\nE1,open\n", encoding="utf-8")

    rc1, payload1, _, _ = review.run_review(target=repo, out_dir=out, workspace_root=workspace)
    assert rc1 in {0, 2}
    first_probe = next(
        row
        for row in payload1["adaptive_review"]["executed_probes"]
        if row["probe_id"] == "probe:inspect-compare"
    )
    first_score = first_probe["score"]

    rc2, payload2, _, _ = review.run_review(target=repo, out_dir=out, workspace_root=workspace)
    assert rc2 in {0, 2}
    second_probe = next(
        row
        for row in payload2["adaptive_review"]["skipped_probes"]
        if row["probe_id"] == "probe:inspect-compare"
    )
    second_score = second_probe["score"]

    assert second_score != first_score
    history_inputs = {row["input"] for row in second_probe["score_inputs"]}
    assert "history_avg_usefulness" in history_inputs
    assert "history_repeat_hit_saturation" in history_inputs


def test_review_executed_probe_list_contains_only_executed_rows(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    repo = tmp_path / "repo"
    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "pyproject.toml").write_text(
        "[project]\nname='demo'\nversion='0.1.0'\n", encoding="utf-8"
    )
    (repo / "events.csv").write_text("id,type\nE1,open\n", encoding="utf-8")

    review.run_review(target=repo, out_dir=out1, workspace_root=workspace)
    (repo / "events.csv").write_text("id,type\nE1,open\nE1,open\n", encoding="utf-8")
    _, payload, _, _ = review.run_review(target=repo, out_dir=out2, workspace_root=workspace)

    assert all(
        row.get("status") == "executed" for row in payload["adaptive_review"]["executed_probes"]
    )
    assert any(
        row.get("probe_id") == "probe:inspect-compare"
        for row in payload["adaptive_review"]["skipped_probes"]
    )
    moved = [
        row
        for row in payload["adaptive_review"]["skipped_probes"]
        if row.get("probe_id") == "probe:inspect-compare"
    ]
    assert moved
    assert moved[0]["skip_reason"] == "probe planned but not executed in deepen stage"


def test_review_no_workspace_reruns_are_deterministic(tmp_path: Path) -> None:
    data = tmp_path / "events.csv"
    out_dir = tmp_path / "out"
    workspace = tmp_path / "workspace"
    data.write_text("id,type\nE1,open\nE1,open\n", encoding="utf-8")

    rc1, payload1, _, _ = review.run_review(
        target=data,
        out_dir=out_dir,
        workspace_root=workspace,
        no_workspace=True,
    )
    rc2, payload2, _, _ = review.run_review(
        target=data,
        out_dir=out_dir,
        workspace_root=workspace,
        no_workspace=True,
    )

    assert rc1 == rc2
    assert payload1["status"] == payload2["status"]
    assert payload1["top_matters"] == payload2["top_matters"]
    assert payload1["prioritized_actions"] == payload2["prioritized_actions"]
    assert (
        payload1["adaptive_review"]["executed_probes"]
        == payload2["adaptive_review"]["executed_probes"]
    )
    assert (
        payload1["adaptive_review"]["skipped_probes"]
        == payload2["adaptive_review"]["skipped_probes"]
    )


def test_review_recovers_from_corrupt_probe_memory(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    repo = tmp_path / "repo"
    out = tmp_path / "out"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        "[project]\nname='demo'\nversion='0.1.0'\n", encoding="utf-8"
    )
    (repo / "events.csv").write_text("id,type\nE1,open\nE1,open\n", encoding="utf-8")
    scope = review._review_scope_for_target(repo)
    probe_mem = workspace / "probe-memory" / "review" / f"{scope}.json"
    probe_mem.parent.mkdir(parents=True, exist_ok=True)
    probe_mem.write_text("{not-json", encoding="utf-8")

    rc, payload, _, _ = review.run_review(target=repo, out_dir=out, workspace_root=workspace)

    assert rc in {0, 2}
    assert (
        payload["adaptive_review"]["probe_memory"]["schema_version"]
        == "sdetkit.review.probe-memory.v1"
    )
    assert isinstance(payload["adaptive_review"]["probe_memory"]["normalized_outcomes"], list)
