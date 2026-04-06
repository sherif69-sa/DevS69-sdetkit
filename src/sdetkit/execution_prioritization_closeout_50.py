from __future__ import annotations

from ._legacy_lane import run_lane

_DEFAULT_PAGE_TEMPLATE = (
    "# Execution prioritization closeout\n\n## Execution prioritization closeout\n"
)
_CFG = {
    "name": "execution-prioritization-closeout",
    "page_path": "docs/integrations-execution-prioritization-closeout.md",
    "required_inputs": [
        "docs/artifacts/weekly-review-closeout-pack-49/weekly-review-closeout-summary-49.json"
    ],
    "required_boards": ["docs/artifacts/weekly-review-closeout-pack-49/delivery-board-49.md"],
    "summary_json": "execution-prioritization-closeout-summary.json",
    "summary_md": "execution-prioritization-closeout-summary.md",
    "pack_files": [
        "execution-prioritization-brief.md",
        "execution-prioritization-risk-register.csv",
        "execution-prioritization-kpi-scorecard.json",
        "execution-prioritization-execution-log.md",
        "execution-prioritization-delivery-board.md",
        "execution-prioritization-validation-commands.md",
    ],
    "evidence_json": "execution-prioritization-execution-summary.json",
    "text_output": " execution prioritization closeout summary",
}


def main(argv: list[str] | None = None) -> int:
    return run_lane(argv, _CFG)
