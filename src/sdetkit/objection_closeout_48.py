from __future__ import annotations

from ._legacy_lane import run_lane

_DEFAULT_PAGE_TEMPLATE = "# Objection closeout\n\n## Objection closeout\n"
_CFG = {
    "name": "objection-closeout",
    "page_path": "docs/integrations-objection-closeout.md",
    "required_inputs": [
        "docs/artifacts/reliability-closeout-pack-47/reliability-closeout-summary-47.json"
    ],
    "required_boards": ["docs/artifacts/reliability-closeout-pack-47/delivery-board-47.md"],
    "summary_json": "objection-closeout-summary.json",
    "summary_md": "objection-closeout-summary.md",
    "pack_files": [
        "objection-plan-48.md",
        "faq-objection-map-48.csv",
        "objection-kpi-scorecard-48.json",
        "execution-log-48.md",
        "objection-delivery-board.md",
        "validation-commands-48.md",
    ],
    "evidence_json": "objection-execution-summary-48.json",
    "text_output": " objection closeout summary",
}


def main(argv: list[str] | None = None) -> int:
    return run_lane(argv, _CFG)
