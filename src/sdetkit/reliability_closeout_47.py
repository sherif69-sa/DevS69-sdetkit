from __future__ import annotations

from ._legacy_lane import run_lane

_DEFAULT_PAGE_TEMPLATE = "# Reliability closeout\n\n## Reliability closeout\n"
_CFG = {
    "name": "reliability-closeout",
    "page_path": "docs/integrations-reliability-closeout.md",
    "required_inputs": [
        "docs/artifacts/optimization-closeout-pack/optimization-closeout-summary.json"
    ],
    "required_boards": ["docs/artifacts/optimization-closeout-pack/optimization-delivery-board.md"],
    "summary_json": "reliability-closeout-summary-47.json",
    "summary_md": "reliability-closeout-summary-47.md",
    "pack_files": [
        "reliability-plan-47.md",
        "incident-map-47.csv",
        "reliability-kpi-scorecard-47.json",
        "execution-log-47.md",
        "delivery-board-47.md",
        "validation-commands-47.md",
    ],
    "evidence_json": "reliability-execution-summary-47.json",
    "text_output": " reliability closeout summary",
}


def main(argv: list[str] | None = None) -> int:
    return run_lane(argv, _CFG)
