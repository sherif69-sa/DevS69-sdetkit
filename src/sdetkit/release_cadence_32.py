from __future__ import annotations

from ._legacy_lane import run_lane

_DEFAULT_PAGE_TEMPLATE = "# Release cadence ()\n\n## Release cadence\n"
_CFG = {
    "name": "release-cadence",
    "page_path": "docs/integrations-release-cadence.md",
    "required_inputs": ["docs/artifacts/phase2-kickoff-pack/phase2-kickoff-summary.json"],
    "required_boards": ["docs/artifacts/phase2-kickoff-pack/phase2-kickoff-delivery-board.md"],
    "summary_json": "release-cadence-summary.json",
    "summary_md": "release-cadence-summary.md",
    "pack_files": [
        "release-cadence-calendar.json",
        "release-changelog-template.md",
        "release-delivery-board.md",
        "release-validation-commands.md",
    ],
    "evidence_json": "release-cadence-execution-summary.json",
    "text_output": " release cadence summary",
}


def main(argv: list[str] | None = None) -> int:
    return run_lane(argv, _CFG)
