from __future__ import annotations

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
