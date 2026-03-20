from __future__ import annotations

from pathlib import Path

from sdetkit import kits


def test_blueprint_payload_exposes_upgrade_layers_and_operating_model() -> None:
    payload = kits.blueprint_payload(
        goal="upgrade umbrella architecture with agentos optimization",
        selected_kits=["release", "integration"],
        limit=3,
    )

    assert payload["selected_kits"][0]["id"] == "release-confidence"
    assert payload["architecture_layers"][0]["name"] == "experience-surface"
    assert payload["operating_model"][0]["cadence"] == "continuous"
    assert "AgentOS run success rate" in payload["metrics"]
    backlog_ids = {item["id"] for item in payload["upgrade_backlog"]}
    assert "umbrella-routing" in backlog_ids
    assert "agent-control-plane" in backlog_ids
    assert "integration-topology" in backlog_ids


def test_optimize_payload_aligns_doctor_quality_gate_agentos_and_topology(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='x'\nversion='0.1.0'\n", encoding="utf-8"
    )
    (tmp_path / "quality.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (tmp_path / "premium-gate.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (tmp_path / "ci.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (tmp_path / "constraints-ci.txt").write_text("ruff==0.15.7\n", encoding="utf-8")
    (tmp_path / ".sdetkit").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".sdetkit" / "gate.fast.snapshot.json").write_text("{}", encoding="utf-8")
    (tmp_path / "examples" / "kits" / "integration").mkdir(parents=True, exist_ok=True)
    (tmp_path / "examples" / "kits" / "integration" / "profile.json").write_text(
        "{}\n", encoding="utf-8"
    )
    (tmp_path / "examples" / "kits" / "integration" / "heterogeneous-topology.json").write_text(
        "{}\n", encoding="utf-8"
    )
    (tmp_path / "templates" / "automations").mkdir(parents=True, exist_ok=True)
    (tmp_path / "templates" / "automations" / "repo-health-audit.yaml").write_text(
        "metadata:\n  id: repo-health-audit\n", encoding="utf-8"
    )

    payload = kits.optimize_payload(
        root=tmp_path,
        goal="upgrade umbrella architecture with agentos optimization",
        selected_kits=["release", "integration"],
        limit=3,
    )

    assert payload["doctor_lane"]["command"].startswith("sdetkit doctor --dev --ci --repo")
    assert "--upgrade-audit" in payload["doctor_lane"]["command"]
    assert payload["quality_gate_lane"]["commands"][0] == "bash quality.sh ci"
    assert payload["quality_gate_lane"]["commands"][1] == "bash premium-gate.sh --mode full"
    assert payload["auto_fix_lane"]["commands"][0] == "bash quality.sh type"
    assert payload["quality_boost_lane"]["command"] == "bash quality.sh boost"
    assert payload["quality_boost_lane"]["phases"][0] == "doctor-first"
    assert payload["integration_lane"]["coverage"] == "topology-aware"
    assert (
        payload["agentos_lane"]["commands"][1]
        == "sdetkit agent run 'template:repo-health-audit' --approve"
    )
    statuses = {item["domain"]: item["status"] for item in payload["alignment_matrix"]}
    assert statuses["doctor"] == "ready"
    assert statuses["quality-gate"] == "ready"
    assert statuses["integration-topology"] == "ready"
    booster_ids = {item["id"] for item in payload["performance_boosters"]}
    assert "ci-constraints" in booster_ids
    assert "topology-premium-loop" in booster_ids
    assert payload["doctor_quality_contract"]["auto_fix_commands"]
    assert payload["operating_sequence"][1]["stage"] == "intelligent-autofix"
    assert payload["next_boosts"][0]["id"] == "quality-boost"
