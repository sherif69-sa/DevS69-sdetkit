from __future__ import annotations

from ._legacy_lane import run_lane

_DEFAULT_PAGE_TEMPLATE = "# Scale lane\n\n## Scale lane\n"
_CFG = {
    "name": "scale-lane",
    "page_path": "docs/integrations-scale-lane.md",
    "required_inputs": ["docs/artifacts/playbook-post-pack/playbook-post-summary.json"],
    "required_boards": ["docs/artifacts/playbook-post-pack/delivery-board.md"],
    "summary_json": "scale-lane-summary.json",
    "summary_md": "scale-lane-summary.md",
    "pack_files": [
        "scale-plan.md",
        "channel-matrix.csv",
        "scale-kpi-scorecard.json",
        "execution-log.md",
        "delivery-board.md",
        "validation-commands.md",
    ],
    "evidence_json": "execution-summary.json",
    "text_output": " scale lane summary",
}


def main(argv: list[str] | None = None) -> int:
    return run_lane(argv, _CFG)
