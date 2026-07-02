from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_ghas_hotspot_policy.py"
WORKFLOW = ROOT / ".github" / "workflows" / "ghas-codeql-hotspots-bot.yml"


def _module():
    spec = importlib.util.spec_from_file_location("build_ghas_hotspot_policy", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _alert(path: str, *, rule_id: str = "CVE-test") -> dict[str, object]:
    return {
        "created_at": "2026-07-01T00:00:00Z",
        "rule": {
            "id": rule_id,
            "name": rule_id,
            "security_severity_level": "high",
        },
        "tool": {"name": "osv-scanner"},
        "most_recent_instance": {"location": {"path": path}},
    }


def test_fixture_only_alerts_are_artifact_only() -> None:
    module = _module()
    alerts = [
        *[_alert("tests/fixtures/public_adoption_target/go.mod") for _ in range(36)],
        *[
            _alert("tests/fixtures/public_adoption_target/requirements-security.txt")
            for _ in range(15)
        ],
    ]

    snapshot, markdown = module.build_policy(
        {
            "collection_status": "collected",
            "repository": "sherif69-sa/DevS69-sdetkit",
            "alerts": alerts,
        },
        now=datetime(2026, 7, 2, tzinfo=UTC),
    )

    assert snapshot["actionable"] is False
    assert snapshot["totals"] == {
        "open_alerts": 51,
        "production_alerts": 0,
        "fixture_alerts": 51,
    }
    assert snapshot["fixture_only_issue_creation"] is False
    assert "No production-path remediation issue is required." in markdown
    assert "Fixture findings remain available" in markdown


def test_production_alert_requires_rolling_tracker() -> None:
    module = _module()

    snapshot, markdown = module.build_policy(
        {
            "collection_status": "collected",
            "alerts": [_alert("src/sdetkit/security.py")],
        },
        now=datetime(2026, 7, 2, tzinfo=UTC),
    )

    assert snapshot["actionable"] is True
    assert snapshot["totals"]["production_alerts"] == 1
    assert snapshot["actionable_reasons"] == ["production-path code-scanning alerts: 1"]
    assert "src/sdetkit/security.py" in markdown


def test_collection_failure_fails_closed() -> None:
    module = _module()

    snapshot, markdown = module.build_policy(
        {
            "collection_status": "unavailable",
            "notes": ["API denied"],
            "alerts": [],
        },
        now=datetime(2026, 7, 2, tzinfo=UTC),
    )

    assert snapshot["actionable"] is True
    assert snapshot["actionable_reasons"] == ["code-scanning alert collection is unavailable"]
    assert "API denied" in markdown


def test_workflow_uses_fixture_aware_rolling_policy() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "python scripts/build_ghas_hotspot_policy.py" in workflow
    assert "ACTIONABLE: ${{ steps.policy.outputs.actionable }}" in workflow
    assert "const rollingTitle = '🧪 GHAS production hotspot follow-up';" in workflow
    assert "issue.user?.login === 'github-actions[bot]'" in workflow
    assert "issue.title.startsWith('🧪 GHAS CodeQL hotspots')" in workflow
    assert "state_reason: 'completed'" in workflow
    assert "const weekOf" not in workflow
    assert "if (!actionable)" in workflow
    assert "core.notice('GHAS alerts are fixture-only; artifacts retained')" in workflow
    assert "push:" in workflow
    assert len(workflow.splitlines()) < 250
