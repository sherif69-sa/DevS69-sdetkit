from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from sdetkit import review


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
    assert payload2["changed_since_previous"][0]["kind"] in {"status", "severity", "action_pressure", "stable"}
    assert "inspect_compare_json" in payload2["artifact_index"]
    assert payload2["adaptive_review"]["escalation"]["needed"] is True
    assert "review_plan_json" in payload2["artifact_index"]
    assert "review_tracks_json" in payload2["artifact_index"]


def test_review_repo_plus_data_surfaces_cross_surface_conflict(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname='demo'\nversion='0.1.0'\n", encoding="utf-8")
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
    assert release_payload["artifact_index"]["profile_packet_json"].endswith("release-decision.json")
    assert monitor_payload["artifact_index"]["profile_packet_json"].endswith("trend-watch.json")
    assert "review_plan_json" in release_payload["artifact_index"]
    assert "review_tracks_json" in monitor_payload["artifact_index"]
    release_now = [item for item in release_payload["prioritized_actions"] if item.get("tier") == "now"]
    monitor_now = [item for item in monitor_payload["prioritized_actions"] if item.get("tier") == "now"]
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


def test_review_tracks_ranked_with_supporting_and_conflicting_evidence(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    workspace = tmp_path / "workspace"
    out = tmp_path / "out"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname='demo'\nversion='0.1.0'\n", encoding="utf-8")
    (repo / "events.csv").write_text("id,type\nE1,open\nE1,open\n", encoding="utf-8")

    rc, payload, _, _ = review.run_review(target=repo, out_dir=out, workspace_root=workspace)

    assert rc == 2
    tracks = payload["likely_issue_tracks"]
    assert tracks
    assert tracks[0]["supporting_evidence"]
    assert "verification_steps" in tracks[0]
    assert isinstance(tracks[0]["conflicting_evidence"], list)
