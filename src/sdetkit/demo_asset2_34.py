from __future__ import annotations

from ._legacy_lane import run_lane

_DEFAULT_PAGE_TEMPLATE = "# Demo asset #2 ()\n\n## Demo asset #2\n"
_CFG = {
    "name": "demo-asset2",
    "page_path": "docs/integrations-demo-asset2.md",
    "required_inputs": ["docs/artifacts/demo-asset-pack/demo-asset-summary.json"],
    "required_boards": ["docs/artifacts/demo-asset-pack/demo-delivery-board.md"],
    "summary_json": "demo-asset2-summary.json",
    "summary_md": "demo-asset2-summary.md",
    "pack_files": [
        "demo-asset2-plan.json",
        "demo-asset2-script.md",
        "demo-asset2-delivery-board.md",
        "demo-asset2-validation-commands.md",
    ],
    "evidence_json": "demo-asset2-execution-summary.json",
    "text_output": " demo asset #2 summary",
}


def main(argv: list[str] | None = None) -> int:
    return run_lane(argv, _CFG)
