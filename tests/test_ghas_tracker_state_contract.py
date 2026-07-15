from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/ghas_tracker_state.js"
WORKFLOWS = {
    "sla": ROOT / ".github/workflows/ghas-alert-sla-bot.yml",
    "review": ROOT / ".github/workflows/ghas-review-bot.yml",
    "configuration": (ROOT / ".github/workflows/security-configuration-audit-bot.yml"),
}


def _node_json(expression: str) -> Any:
    source = f"""
const helper = require({json.dumps(str(HELPER))});
const value = ({expression});
process.stdout.write(JSON.stringify(value));
"""
    completed = subprocess.run(
        ["node", "-e", source],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_available_empty_is_authoritative_zero() -> None:
    result = _node_json("helper.collectedAlerts([], 'Dependabot alerts')")
    assert result == {
        "status": "collected",
        "alerts": [],
        "count": 0,
        "note": None,
    }
    assert _node_json("helper.countOrUnknown(helper.collectedAlerts([], 'Dependabot alerts'))") == 0


def test_available_nonempty_preserves_exact_count() -> None:
    result = _node_json(
        "helper.collectedAlerts([{number: 1}, {number: 2}], 'Code scanning alerts')"
    )
    assert result["status"] == "collected"
    assert result["count"] == 2
    assert len(result["alerts"]) == 2


def test_unavailable_and_invalid_are_unknown_never_zero() -> None:
    unavailable = _node_json(
        "helper.unavailableAlerts('Secret scanning alerts', new Error('forbidden'))"
    )
    assert unavailable["status"] == "unavailable"
    assert unavailable["count"] is None
    assert "forbidden" in unavailable["note"]

    invalid = _node_json("helper.collectedAlerts(null, 'Dependabot alerts')")
    assert invalid["status"] == "invalid"
    assert invalid["count"] is None
    assert "invalid null payload" in invalid["note"]

    assert (
        _node_json("helper.countOrUnknown(helper.unavailableAlerts('x', new Error('no access')))")
        == "unknown"
    )
    assert _node_json("helper.countOrUnknown(helper.collectedAlerts(null, 'x'))") == "unknown"


def test_derived_metrics_remain_unknown_when_collection_is_unknown() -> None:
    assert (
        _node_json(
            "helper.metricOrUnknown("
            "helper.unavailableAlerts('x', new Error('denied')), "
            "(alerts) => alerts.length)"
        )
        == "unknown"
    )
    assert (
        _node_json(
            "helper.metricOrUnknown("
            "helper.collectedAlerts([{severity: 'high'}], 'x'), "
            "(alerts) => alerts.filter((item) => "
            "item.severity === 'high').length)"
        )
        == 1
    )


def test_digest_metrics_preserve_authoritative_zero() -> None:
    result = _node_json(
        "helper.digestAlertMetrics("
        "helper.collectedAlerts([], 'Code scanning'), "
        "helper.collectedAlerts([], 'Dependabot'), "
        "helper.collectedAlerts([], 'Secret scanning'))"
    )

    assert result == {
        "codeScanning": 0,
        "dependabot": 0,
        "secretScanning": 0,
        "pushProtectionBypassed": 0,
    }


def test_digest_metrics_never_leak_null_or_undefined() -> None:
    result = _node_json(
        "helper.digestAlertMetrics("
        "helper.collectedAlerts([{number: 1}, {number: 2}], 'Code scanning'), "
        "helper.unavailableAlerts('Dependabot', new Error('forbidden')), "
        "helper.collectedAlerts(null, 'Secret scanning'))"
    )

    assert result == {
        "codeScanning": 2,
        "dependabot": "unknown",
        "secretScanning": "unknown",
        "pushProtectionBypassed": "unknown",
    }


def test_digest_metrics_preserve_collected_bypass_count() -> None:
    result = _node_json(
        "helper.digestAlertMetrics("
        "helper.collectedAlerts([], 'Code scanning'), "
        "helper.collectedAlerts([], 'Dependabot'), "
        "helper.collectedAlerts(["
        "{push_protection_bypassed: true}, "
        "{push_protection_bypassed: false}, "
        "{push_protection_bypassed: true}], 'Secret scanning'))"
    )

    assert result == {
        "codeScanning": 0,
        "dependabot": 0,
        "secretScanning": 3,
        "pushProtectionBypassed": 2,
    }


def test_workflows_use_shared_state_contract() -> None:
    texts = {key: path.read_text(encoding="utf-8") for key, path in WORKFLOWS.items()}

    for text in texts.values():
        assert "scripts/ghas_tracker_state.js" in text
        assert "Collection status" in text
        assert "process.env.GHAS_TOKEN || github.token" in text

    assert "countOrUnknown" in texts["sla"]
    assert "countOrUnknown" in texts["configuration"]
    assert "digestAlertMetrics" in texts["review"]
    assert "return [];" not in texts["sla"]
    assert "Array.isArray(response.data) ? response.data.length : 0" not in texts["review"]
    assert "Array.isArray(response.data) ? response.data.length : 0" not in texts["configuration"]


def test_review_bot_renders_only_normalized_digest_metrics() -> None:
    text = WORKFLOWS["review"].read_text(encoding="utf-8")

    assert "const digestMetrics = digestAlertMetrics(" in text
    assert "${digestMetrics.codeScanning}" in text
    assert "${digestMetrics.dependabot}" in text
    assert "${digestMetrics.secretScanning}" in text
    assert "${digestMetrics.pushProtectionBypassed}" in text
    assert "${codeScanning.count}" not in text
    assert "${dependabot.count}" not in text
    assert "${secretScanning.count}" not in text
    assert "${pushProtectionBypassed.count}" not in text


def test_review_bot_uses_cadence_aware_workflow_freshness() -> None:
    text = WORKFLOWS["review"].read_text(encoding="utf-8")

    assert "{ file: 'security-configuration-audit-bot.yml', maxAgeDays: 35 }" in text
    assert "ageDays >= trackedWorkflow.maxAgeDays" in text
    assert "Maximum age (days)" in text
    assert "const staleWorkflowDays = 14;" not in text


def test_security_workflow_permissions_do_not_expand() -> None:
    expected_permissions = {
        "sla": {"contents": "read", "issues": "write", "security-events": "read"},
        "review": {
            "actions": "read",
            "contents": "read",
            "issues": "write",
            "security-events": "read",
        },
        "configuration": {
            "contents": "read",
            "issues": "write",
            "security-events": "read",
        },
    }

    for key, path in WORKFLOWS.items():
        text = path.read_text(encoding="utf-8")
        block_match = re.search(
            r"(?ms)^permissions:\n(?P<body>(?:  [^\n]+\n)+)",
            text,
        )
        assert block_match is not None
        body = block_match.group("body")
        observed = {}
        for line in body.splitlines():
            name, value = line.strip().split(":", 1)
            observed[name] = value.strip()
        assert observed == expected_permissions[key]


def test_actions_remain_pinned_and_no_security_mutation_is_added() -> None:
    for path in WORKFLOWS.values():
        text = path.read_text(encoding="utf-8")
        actions = re.findall(r"uses:\s*[^@\s]+@([0-9a-f]{40})", text)
        assert actions
        assert all(len(sha) == 40 for sha in actions)

        forbidden = (
            "dismissAlert",
            "dismissed_reason",
            "updateRepositorySecurityConfiguration",
            "PATCH /repos/{owner}/{repo}/code-security-configuration",
        )
        assert not any(token in text for token in forbidden)


def test_security_docs_define_zero_and_unknown() -> None:
    text = (ROOT / "docs/security.md").read_text(encoding="utf-8")
    assert "## GHAS tracker collection semantics" in text
    assert "Authoritative zero" in text
    assert "Unknown" in text
    normalized_text = " ".join(text.split())
    assert "does not authorize alert dismissal" in normalized_text
