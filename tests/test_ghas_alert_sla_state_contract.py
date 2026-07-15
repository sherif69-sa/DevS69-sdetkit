from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/ghas_tracker_state.js"
WORKFLOW = ROOT / ".github/workflows/ghas-alert-sla-bot.yml"


def _node_json(source: str) -> Any:
    completed = subprocess.run(
        ["node", "-e", source],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_sla_metrics_preserve_collected_counts_and_unknown_state() -> None:
    source = f"""
const helper = require({json.dumps(str(HELPER))});
const summarize = (result) => ({{
  total: helper.countOrUnknown(result),
  aged7: helper.metricOrUnknown(
    result,
    (alerts) => alerts.filter((alert) => alert.ageDays >= 7).length,
  ),
  aged14: helper.metricOrUnknown(
    result,
    (alerts) => alerts.filter((alert) => alert.ageDays >= 14).length,
  ),
}});
const value = {{
  empty: summarize(helper.collectedAlerts([], 'empty')),
  collected: summarize(helper.collectedAlerts([
    {{ageDays: 2}},
    {{ageDays: 8}},
    {{ageDays: 20}},
  ], 'collected')),
  unavailable: summarize(helper.unavailableAlerts('unavailable', new Error('forbidden'))),
  invalid: summarize(helper.collectedAlerts(null, 'invalid')),
}};
process.stdout.write(JSON.stringify(value));
"""

    assert _node_json(source) == {
        "empty": {"total": 0, "aged7": 0, "aged14": 0},
        "collected": {"total": 3, "aged7": 2, "aged14": 1},
        "unavailable": {
            "total": "unknown",
            "aged7": "unknown",
            "aged14": "unknown",
        },
        "invalid": {
            "total": "unknown",
            "aged7": "unknown",
            "aged14": "unknown",
        },
    }


def test_sla_workflow_never_treats_alert_state_as_an_array() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    expected_metrics = (
        "const codeAlertCount = countOrUnknown(codeAlerts);",
        "const dependabotAlertCount = countOrUnknown(dependabotAlerts);",
        "const secretAlertCount = countOrUnknown(secretAlerts);",
        "const codeAged7 = metricOrUnknown(codeAlerts,",
        "const dependabotAged7 = metricOrUnknown(",
        "const secretAged7 = metricOrUnknown(secretAlerts,",
        "${codeAlertCount}",
        "${dependabotAlertCount}",
        "${secretAlertCount}",
        "${secretBypassed}",
        "${codeAged7}",
        "${dependabotAged7}",
        "${secretAged7}",
    )
    assert all(token in text for token in expected_metrics)

    forbidden_wrapper_array_access = (
        "${codeAlerts.length}",
        "${dependabotAlerts.length}",
        "${secretAlerts.length}",
        "${secretBypassed.length}",
        "countAtLeast(codeAlerts,",
        "countAtLeast(dependabotAlerts,",
        "countAtLeast(secretAlerts,",
    )
    assert not any(token in text for token in forbidden_wrapper_array_access)

    assert "## Collection status" in text
    assert "process.env.GHAS_TOKEN || github.token" in text
    assert "dismissAlert" not in text
    assert "updateRepositorySecurityConfiguration" not in text
