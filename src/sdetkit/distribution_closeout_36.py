from __future__ import annotations

from ._legacy_lane import run_lane

_DEFAULT_PAGE_TEMPLATE = "# Distribution closeout\n\n## Distribution closeout\n"
_CFG = {
    "name": "distribution-closeout",
    "page_path": "docs/integrations-distribution-closeout.md",
    "required_inputs": ["docs/artifacts/kpi-instrumentation-pack/kpi-instrumentation-summary.json"],
    "required_boards": ["docs/artifacts/kpi-instrumentation-pack/delivery-board.md"],
    "summary_json": "distribution-closeout-summary.json",
    "summary_md": "distribution-closeout-summary.md",
    "pack_files": [
        "distribution-message-kit.md",
        "launch-plan.csv",
        "experiment-backlog.md",
        "delivery-board.md",
        "validation-commands.md",
    ],
    "evidence_json": "execution-summary.json",
    "text_output": " community distribution summary",
}


def main(argv: list[str] | None = None) -> int:
    return run_lane(argv, _CFG)
