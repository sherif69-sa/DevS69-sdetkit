from __future__ import annotations

from ._legacy_lane import run_lane

_DEFAULT_PAGE_TEMPLATE = "# Weekly review #4 ()\n\n## Weekly review lane\n"
_CFG = {
    "name": "weekly-review-lane",
    "page_path": "docs/integrations-weekly-review.md",
    "required_inputs": [
        "docs/artifacts/community-activation-pack/community-activation-summary.json",
        "docs/artifacts/external-contribution-pack/external-contribution-summary.json",
        "docs/artifacts/kpi-audit-pack/kpi-audit-summary.json",
    ],
    "required_page_marker": "## Weekly review lane",
    "summary_json": "weekly-review-summary.json",
    "summary_md": "weekly-review-kpi-rollup.md",
    "pack_files": ["weekly-review-wins-misses-actions.md", "weekly-review-validation-commands.md"],
    "evidence_json": "weekly-review-execution-summary.json",
    "text_output": " weekly review summary",
}


def main(argv: list[str] | None = None) -> int:
    return run_lane(argv, _CFG)
