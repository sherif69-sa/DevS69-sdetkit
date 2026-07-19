from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(".github/workflows/maintenance-autopilot.yml")


def test_maintenance_autopilot_preserves_diagnostics_after_command_failure() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    upload_block = text.split("      - name: Upload autopilot artifacts", 1)[1].split(
        "      - name: Publish run summary", 1
    )[0]
    summary_block = text.split("      - name: Publish run summary", 1)[1].split(
        "      - name: Open/update security follow-up issue", 1
    )[0]

    assert "if: always()" in upload_block
    assert "if-no-files-found: warn" in upload_block
    assert "if: always()" in summary_block
    assert (
        "if [ -f build/maintenance/autopilot/autopilot-report.md ]; then"
        in summary_block
    )
    assert (
        "elif [ -f build/maintenance/autopilot/adaptive-diagnosis.md ]; then"
        in summary_block
    )
    assert (
        "Maintenance command failed before a diagnosis report was written."
        in summary_block
    )
