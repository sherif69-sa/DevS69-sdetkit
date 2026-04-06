from __future__ import annotations

from ._legacy_lane import run_lane

_DEFAULT_PAGE_TEMPLATE = "# Experiment lane\n\n## Experiment lane\n"
_CFG = {
    "name": "experiment-lane",
    "page_path": "docs/integrations-experiment-lane.md",
    "required_inputs": [
        "docs/artifacts/distribution-closeout-pack/distribution-closeout-summary.json"
    ],
    "required_boards": ["docs/artifacts/distribution-closeout-pack/delivery-board.md"],
    "summary_json": "experiment-lane-summary.json",
    "summary_md": "experiment-lane-summary.md",
    "pack_files": [
        "experiment-matrix.csv",
        "hypothesis-brief.md",
        "experiment-scorecard.json",
        "decision-log.md",
        "delivery-board.md",
        "validation-commands.md",
    ],
    "evidence_json": "execution-summary.json",
    "text_output": " experiment lane summary",
}


def main(argv: list[str] | None = None) -> int:
    return run_lane(argv, _CFG)
