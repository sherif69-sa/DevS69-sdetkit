from __future__ import annotations

from ._legacy_lane import run_lane

_DEFAULT_PAGE_TEMPLATE = "# Distribution batch\n\n## Distribution batch\n"
_CFG = {
    "name": "distribution-batch",
    "page_path": "docs/integrations-distribution-batch.md",
    "required_inputs": ["docs/artifacts/experiment-lane-pack/experiment-lane-summary.json"],
    "required_boards": ["docs/artifacts/experiment-lane-pack/delivery-board.md"],
    "summary_json": "distribution-batch-summary.json",
    "summary_md": "distribution-batch-summary.md",
    "pack_files": [
        "channel-plan.csv",
        "post-copy.md",
        "kpi-scorecard.json",
        "execution-log.md",
        "delivery-board.md",
        "validation-commands.md",
    ],
    "evidence_json": "execution-summary.json",
    "text_output": " distribution batch summary",
}


def main(argv: list[str] | None = None) -> int:
    return run_lane(argv, _CFG)
