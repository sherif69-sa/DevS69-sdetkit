from __future__ import annotations

from ._legacy_lane import run_lane

_DEFAULT_PAGE_TEMPLATE = "# Weekly review closeout\n\n## Weekly review closeout\n"
_CFG = {
    "name": "weekly-review-closeout",
    "page_path": "docs/integrations-weekly-review-closeout.md",
    "required_inputs": ["docs/artifacts/objection-closeout-pack/objection-closeout-summary.json"],
    "summary_json": "weekly-review-closeout-summary.json",
    "summary_md": "weekly-review-closeout-summary.md",
    "pack_files": [
        "weekly-review-brief-49.md",
        "weekly-review-risk-register-49.csv",
        "weekly-review-kpi-scorecard-49.json",
        "advanced-priority-matrix-49.json",
        "execution-log-49.md",
        "weekly-review-delivery-board.md",
        "validation-commands-49.md",
    ],
    "evidence_json": "weekly-review-execution-summary-49.json",
    "text_output": " advanced weekly review control tower summary",
}


def main(argv: list[str] | None = None) -> int:
    return run_lane(argv, _CFG)
