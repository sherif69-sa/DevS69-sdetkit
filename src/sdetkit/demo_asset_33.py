from __future__ import annotations

from ._legacy_lane import run_lane

_DEFAULT_PAGE_TEMPLATE = "# Demo asset ()\n\n## Demo asset\n"
_CFG = {
    "name": "demo-asset",
    "page_path": "docs/integrations-demo-asset.md",
    "required_inputs": ["docs/artifacts/release-cadence-pack/release-cadence-summary.json"],
    "required_boards": ["docs/artifacts/release-cadence-pack/release-delivery-board.md"],
    "summary_json": "demo-asset-summary.json",
    "summary_md": "demo-asset-summary.md",
    "pack_files": [
        "demo-asset-plan.json",
        "demo-script.md",
        "demo-delivery-board.md",
        "demo-validation-commands.md",
    ],
    "evidence_json": "demo-execution-summary.json",
    "text_output": " demo asset summary",
}


def main(argv: list[str] | None = None) -> int:
    return run_lane(argv, _CFG)
