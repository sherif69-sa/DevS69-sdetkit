from __future__ import annotations

from ._legacy_lane import run_lane

_DEFAULT_PAGE_TEMPLATE = "# Continuous upgrade closeout 4\n\n## Continuous upgrade closeout\n"
_CFG = {
    "name": "continuous-upgrade-closeout-4",
    "page_path": "docs/integrations-continuous-upgrade-closeout-4.md",
    "summary_json": "continuous-upgrade-closeout-4-summary.json",
    "summary_md": "continuous-upgrade-closeout-4-summary.md",
    "pack_files": ["continuous-upgrade-closeout-4-board.md"],
    "evidence_json": "continuous-upgrade-closeout-4-execution-summary.json",
    "text_output": "continuous upgrade closeout 4 summary",
}


def main(argv: list[str] | None = None) -> int:
    return run_lane(argv, _CFG)
