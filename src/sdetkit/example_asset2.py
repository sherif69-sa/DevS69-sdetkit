from __future__ import annotations

from ._legacy_workflow import run_lane

_DEFAULT_PAGE_TEMPLATE = "# Example asset #2 ()\n\n## Example asset #2\n"
_CFG = {
    "page_template": _DEFAULT_PAGE_TEMPLATE,
    "name": "example-asset2",
    "page_path": "docs/integrations-example-asset2.md",
    "required_inputs": ["docs/artifacts/example-asset-pack/example-asset-summary.json"],
    "required_boards": ["docs/artifacts/example-asset-pack/example-delivery-board.md"],
    "summary_json": "example-asset2-summary.json",
    "summary_md": "example-asset2-summary.md",
    "pack_files": [
        "example-asset2-plan.json",
        "example-asset2-script.md",
        "example-asset2-delivery-board.md",
        "example-asset2-validation-commands.md",
    ],
    "evidence_json": "example-asset2-execution-summary.json",
    "text_output": " example asset #2 summary",
}


def main(argv: list[str] | None = None) -> int:
    return run_lane(argv, _CFG)
