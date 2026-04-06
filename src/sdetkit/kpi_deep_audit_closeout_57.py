from __future__ import annotations

from ._legacy_lane import run_lane

_DEFAULT_PAGE_TEMPLATE = "# KPI deep audit closeout\n\n## KPI deep audit closeout\n"
_CFG = {
    "name": "kpi-deep-audit-closeout",
    "page_path": "docs/integrations-kpi-deep-audit-closeout.md",
    "required_inputs": [
        "docs/artifacts/stabilization-closeout-pack/stabilization-closeout-summary.json"
    ],
    "required_boards": [
        "docs/artifacts/stabilization-closeout-pack/stabilization-delivery-board.md"
    ],
    "summary_json": "kpi-deep-audit-closeout-summary.json",
    "summary_md": "kpi-deep-audit-closeout-summary.md",
    "pack_files": [
        "kpi-deep-audit-brief.md",
        "kpi-deep-audit-risk-ledger.csv",
        "kpi-deep-audit-scorecard.json",
        "kpi-deep-audit-execution-log.md",
        "kpi-deep-audit-delivery-board.md",
        "kpi-deep-audit-validation-commands.md",
    ],
    "evidence_json": "kpi-deep-audit-execution-summary.json",
    "text_output": "KPI Deep Audit Closeout summary",
}


def main(argv: list[str] | None = None) -> int:
    return run_lane(argv, _CFG)
