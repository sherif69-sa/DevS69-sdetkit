from __future__ import annotations

from ._legacy_lane import run_lane

_CFG = {
    "name": "kpi-audit",
    "page_path": "docs/integrations-kpi-audit.md",
    "required_inputs": [
        "docs/artifacts/kpi-audit-pack/kpi-baseline.json",
        "docs/artifacts/kpi-audit-pack/kpi-current.json",
    ],
    "required_page_marker": "## KPI audit",
    "summary_json": "kpi-audit-summary.json",
    "summary_md": "kpi-audit-scorecard.md",
    "pack_files": [
        "kpi-delta-table.md",
        "kpi-corrective-actions.md",
        "kpi-audit-validation-commands.md",
    ],
    "evidence_json": "kpi-audit-execution-summary.json",
    "text_output": " KPI audit summary",
}


def main(argv: list[str] | None = None) -> int:
    return run_lane(argv, _CFG)
