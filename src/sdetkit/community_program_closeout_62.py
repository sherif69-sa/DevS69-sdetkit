from __future__ import annotations

from ._legacy_lane import run_lane

_DEFAULT_PAGE_TEMPLATE = "# Community program closeout ()\n\n## Community program closeout\n"
_CFG = {
    "name": "community-program-closeout",
    "page_path": "docs/integrations-community-program-closeout.md",
    "required_inputs": [
        "docs/artifacts/phase3-kickoff-closeout-pack/phase3-kickoff-closeout-summary.json"
    ],
    "required_boards": [
        "docs/artifacts/phase3-kickoff-closeout-pack/phase3-kickoff-delivery-board.md"
    ],
    "summary_json": "community-program-closeout-summary.json",
    "summary_md": "community-program-closeout-summary.md",
    "pack_files": [
        "community-program-community-launch-brief.md",
        "community-program-office-hours-cadence.md",
        "community-program-participation-policy.md",
        "community-program-moderation-runbook.md",
        "community-program-kpi-scorecard.json",
        "community-program-execution-log.md",
        "community-program-delivery-board.md",
        "community-program-validation-commands.md",
    ],
    "evidence_json": "community-program-execution-summary.json",
    "text_output": "Community Program Closeout summary",
}


def main(argv: list[str] | None = None) -> int:
    return run_lane(argv, _CFG)
