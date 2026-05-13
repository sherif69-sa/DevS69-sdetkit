from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(".github/workflows/adaptive-sentinel-monitor.yml")


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_scheduled_adaptive_sentinel_monitor_triggers_are_safe() -> None:
    text = _workflow_text()

    assert "name: Adaptive Sentinel Monitor" in text
    assert "workflow_dispatch:" in text
    assert "schedule:" in text
    assert "cron:" in text
    assert "permissions:" in text
    assert "contents: read" in text


def test_scheduled_adaptive_sentinel_monitor_runs_read_only_scan() -> None:
    text = _workflow_text()

    assert "python -m sdetkit adaptive sentinel scan" in text
    assert "--root ." in text
    assert "--out-dir build/sdetkit/sentinel" in text
    assert "--format json" in text
    assert "--no-fail" in text
    assert "--no-write" not in text
    assert "git push" not in text
    assert "commit-safe-fixes" not in text
    assert "auto-remediate" not in text


def test_scheduled_adaptive_sentinel_monitor_uploads_artifacts_and_summary() -> None:
    text = _workflow_text()

    assert "GITHUB_STEP_SUMMARY" in text
    assert "Adaptive Sentinel Monitor" in text
    assert "build/sdetkit/sentinel/sentinel.json" in text
    assert "build/sdetkit/sentinel/sentinel.md" in text
    assert "Upload adaptive sentinel monitor artifacts" in text
    assert "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02" in text
    assert "name: adaptive-sentinel-monitor" in text
    assert "build/sdetkit/sentinel/" in text
    assert ".sdetkit/adaptive-sentinel/" in text


def test_scheduled_adaptive_sentinel_monitor_uses_existing_ci_install_pattern() -> None:
    text = _workflow_text()

    assert "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd" in text
    assert "actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405" in text
    assert 'python-version: "3.12"' in text
    assert "python -m pip install -c constraints-ci.txt -r requirements-test.txt -e ." in text
