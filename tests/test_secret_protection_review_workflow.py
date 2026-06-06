from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(".github/workflows/secret-protection-review-bot.yml")


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_secret_protection_review_preserves_secret_alert_availability_status() -> None:
    text = _workflow_text()

    assert "return { available: true, alerts };" in text
    assert "return { available: false, alerts: [] };" in text
    assert "const secretAlertsResult = await fetchSecretAlerts();" in text
    assert "const secretAlertsAvailable = secretAlertsResult.available === true;" in text
    assert (
        "const secretCount = (count) => secretAlertsAvailable ? String(count) : 'unavailable';"
        in text
    )
    assert "const secretAgeBuckets = secretAlertsAvailable" in text


def test_secret_protection_review_does_not_render_unavailable_secret_alerts_as_zero() -> None:
    text = _workflow_text()

    assert "`- Open secret scanning alerts: **${secretCount(secretAlerts.length)}**`" in text
    assert (
        "`- Push-protection bypass follow-up alerts: **${secretCount(bypassedAlerts.length)}**`"
        in text
    )
    assert "`- Alert age buckets: \\`${secretAgeBuckets}\\``" in text
    assert "- Secret scanning alerts were unavailable for this run." in text


def test_secret_protection_review_suppresses_empty_standalone_trackers() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "const hasOpenSecretAlerts = secretAlertsAvailable && secretAlerts.length > 0;" in text
    assert (
        "const hasBypassedSecretAlerts = secretAlertsAvailable && bypassedAlerts.length > 0;"
        in text
    )
    assert (
        "const shouldOpenStandaloneIssue = hasOpenSecretAlerts || hasBypassedSecretAlerts;" in text
    )
    assert "if (!shouldOpenStandaloneIssue)" in text
    assert (
        "No standalone issue created: live secret scanning found no open alerts or bypassed alerts."
        in text
    )
    assert "console.log(" not in text

    guard = text.index("if (!shouldOpenStandaloneIssue)")
    create_issue = text.index("await github.rest.issues.create({")
    assert guard < create_issue
