from __future__ import annotations

import json
import subprocess
import sys

from sdetkit import upgrade_hub


def test_build_upgrade_hub_summary_exposes_hidden_feature_candidates() -> None:
    payload = upgrade_hub.build_upgrade_hub_summary(".")
    assert payload["name"] == "upgrade-hub"
    assert payload["total_closeout_entries"] > 0
    assert "continuous_upgrade" in payload["lane_distribution"]
    assert payload["high_signal_hidden_features"]
    assert payload["repo_inventory"]["closeout_modules"] > 0
    assert payload["repo_inventory"]["contract_scripts"] > 0
    assert payload["cli_visibility"]["hidden_count"] > 0
    assert payload["playbooks_coverage"]["promoted_playbooks_count"] > 0
    assert payload["integration_opportunities"]


def test_upgrade_hub_cli_json_contract() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "sdetkit", "upgrade-hub", "--format", "json", "--top", "5"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["name"] == "upgrade-hub"
    assert len(data["high_signal_hidden_features"]) == 5
    assert "upgrade_hub_json" in data["actions"]
