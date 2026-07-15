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


def test_sla_metrics_preserve_collected_counts_and_age_buckets() -> None:
    source = f"""
const helper = require({json.dumps(str(HELPER))});
const ageDays = (alert) => alert.ageDays;
const value = helper.slaAlertMetrics(
  helper.collectedAlerts([
    {{ageDays: 2, rule: {{severity: 'low'}}}},
    {{ageDays: 8, rule: {{security_severity_level: 'high'}}}},
    {{ageDays: 20, rule: {{security_severity_level: 'critical'}}}},
  ], 'Code scanning'),
  helper.collectedAlerts([
    {{ageDays: 1, security_vulnerability: {{severity: 'medium'}}}},
    {{ageDays: 15, security_vulnerability: {{severity: 'high'}}}},
  ], 'Dependabot'),
  helper.collectedAlerts([
    {{ageDays: 3, push_protection_bypassed: true}},
    {{ageDays: 9, push_protection_bypassed: true}},
    {{ageDays: 20, push_protection_bypassed: false}},
  ], 'Secret scanning'),
  ageDays,
);
process.stdout.write(JSON.stringify(value));
"""

    assert _node_json(source) == {
        "codeScanning": 3,
        "dependabot": 2,
        "secretScanning": 3,
        "codeAged7": 2,
        "codeAged14": 1,
        "codeAged30": 0,
        "highSeverityCodeAged": 1,
        "dependabotAged7": 1,
        "dependabotAged14": 1,
        "dependabotAged30": 0,
        "criticalDependabotAged": 1,
        "secretAged7": 2,
        "secretAged14": 1,
        "secretAged30": 0,
        "secretBypassed": 2,
        "secretBypassedAged": 1,
    }


def test_sla_metrics_preserve_zero_and_unknown_collection_states() -> None:
    source = f"""
const helper = require({json.dumps(str(HELPER))});
const ageDays = (alert) => alert.ageDays;
const empty = helper.slaAlertMetrics(
  helper.collectedAlerts([], 'Code scanning'),
  helper.collectedAlerts([], 'Dependabot'),
  helper.collectedAlerts([], 'Secret scanning'),
  ageDays,
);
const unavailable = helper.slaAlertMetrics(
  helper.unavailableAlerts('Code scanning', new Error('forbidden')),
  helper.collectedAlerts(null, 'Dependabot'),
  helper.unavailableAlerts('Secret scanning', new Error('forbidden')),
  ageDays,
);
process.stdout.write(JSON.stringify({{empty, unavailable}}));
"""
    result = _node_json(source)

    assert set(result["empty"].values()) == {0}
    assert set(result["unavailable"].values()) == {"unknown"}


def test_sla_workflow_uses_compact_normalized_metric_projection() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    expected_metrics = (
        "slaAlertMetrics,",
        "const slaMetrics = slaAlertMetrics(",
        "${slaMetrics.codeScanning}",
        "${slaMetrics.dependabot}",
        "${slaMetrics.secretScanning}",
        "${slaMetrics.secretBypassed}",
        "${slaMetrics.codeAged7}",
        "${slaMetrics.dependabotAged7}",
        "${slaMetrics.secretAged7}",
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
    assert len(text.splitlines()) < 250

    assert "## Collection status" in text
    assert "process.env.GHAS_TOKEN || github.token" in text
    assert "dismissAlert" not in text
    assert "updateRepositorySecurityConfiguration" not in text
