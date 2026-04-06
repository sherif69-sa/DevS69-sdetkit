from __future__ import annotations

from ._legacy_lane import run_lane

_DEFAULT_PAGE_TEMPLATE = "# Expansion automation\n\n## Expansion automation\n"
_CFG = {
    "name": "expansion-automation",
    "page_path": "docs/integrations-expansion-automation.md",
    "required_inputs": ["docs/artifacts/scale-lane-pack/scale-lane-summary.json"],
    "required_boards": ["docs/artifacts/scale-lane-pack/delivery-board.md"],
    "summary_json": "expansion-automation-summary.json",
    "summary_md": "expansion-automation-summary.md",
    "pack_files": [
        "expansion-plan.md",
        "automation-matrix.csv",
        "expansion-kpi-scorecard.json",
        "execution-log.md",
        "delivery-board.md",
        "validation-commands.md",
    ],
    "evidence_json": "execution-summary.json",
    "text_output": "Expansion automation summary",
}


def main(argv: list[str] | None = None) -> int:
    return run_lane(argv, _CFG)
