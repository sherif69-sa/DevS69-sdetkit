from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(".github/workflows/ghas-metrics-export-bot.yml")


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_ghas_metrics_monthly_governance_workflows_use_monthly_stale_threshold() -> None:
    text = _workflow_text()

    assert "const defaultStaleWorkflowDays = 14;" in text
    assert "const workflowFreshnessThresholdDays = {" in text
    assert "'security-configuration-audit-bot.yml': 45," in text
    assert "'workflow-governance-bot.yml': 45," in text
    assert (
        "const staleThresholdDays = "
        "workflowFreshnessThresholdDays[workflowFile] || defaultStaleWorkflowDays;"
    ) in text
    assert "stale_threshold_days: staleThresholdDays," in text
    assert "stale: updatedAgeDays !== null ? updatedAgeDays >= staleThresholdDays : null," in text


def test_ghas_metrics_workflow_freshness_table_reports_generic_stale_threshold() -> None:
    text = _workflow_text()

    assert "| Stale threshold (days) | Stale |" in text
    assert "14d stale" not in text
    assert "stale_14d" not in text
