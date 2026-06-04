from __future__ import annotations

from ._legacy_workflow import run_lane

_DEFAULT_PAGE_TEMPLATE = "# Example asset ()\n\n## Example asset\n"
_CFG = {
    "page_template": _DEFAULT_PAGE_TEMPLATE,
    "name": "example-asset",
    "page_path": "docs/integrations-example-asset.md",
    "required_inputs": ["docs/artifacts/release-cadence-pack/release-cadence-summary.json"],
    "required_boards": ["docs/artifacts/release-cadence-pack/release-delivery-board.md"],
    "summary_json": "example-asset-summary.json",
    "summary_md": "example-asset-summary.md",
    "pack_files": [
        "example-asset-plan.json",
        "example-script.md",
        "example-delivery-board.md",
        "example-validation-commands.md",
    ],
    "evidence_json": "example-execution-summary.json",
    "text_output": " example asset summary",
}


def main(argv: list[str] | None = None) -> int:
    return run_lane(argv, _CFG)
