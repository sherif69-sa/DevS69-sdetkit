from __future__ import annotations

from pathlib import Path


def test_maintenance_autopilot_uploads_investigation_and_safe_fix_artifacts() -> None:
    text = Path(".github/workflows/maintenance-autopilot.yml").read_text(encoding="utf-8")

    expected_paths = [
        "build/maintenance/autopilot/autopilot-report.json",
        "build/maintenance/autopilot/autopilot-report.md",
        "build/maintenance/autopilot/command-center-dry-run-plan.json",
        "build/maintenance/autopilot/command-center-live-plan.json",
        "build/maintenance/autopilot/sdet_check.json",
        "build/maintenance/autopilot/doctor.json",
        "build/maintenance/autopilot/review.json",
        "build/maintenance/autopilot/security-check.json",
        "build/maintenance/autopilot/adaptive-diagnosis.json",
        "build/maintenance/autopilot/adaptive-diagnosis.md",
        "build/maintenance/autopilot/adaptive-diagnosis-error.json",
        "build/maintenance/autopilot/safe-fix-plan.json",
        "build/maintenance/autopilot/adaptive-safe-remediation-result.json",
        "build/maintenance/autopilot/adaptive-safe-remediation-result.md",
        "build/maintenance/autopilot/adaptive-safe-remediation-error.json",
        "build/maintenance/autopilot/adaptive-safe-commit-result.json",
        "build/maintenance/autopilot/adaptive-safe-fix-learning-result.json",
        "build/maintenance/autopilot/adaptive-safe-fix-learning-rollup.json",
        "build/maintenance/autopilot/adaptive-safe-fix-learning-error.json",
        ".sdetkit/maintenance/failure-memory.jsonl",
        ".sdetkit/maintenance/adaptive-safe-fix-memory.jsonl",
    ]

    for artifact_path in expected_paths:
        assert artifact_path in text
