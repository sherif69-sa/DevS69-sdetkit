from __future__ import annotations

from ._legacy_lane import run_lane

_DEFAULT_PAGE_TEMPLATE = "# Phase-2 kickoff ()\n\n## Phase-2 kickoff\n"
_CFG = {
    "name": "phase2-kickoff",
    "page_path": "docs/integrations-phase2-kickoff.md",
    "required_inputs": [
        "docs/artifacts/phase1-wrap-pack/phase1-wrap-summary.json",
        "docs/artifacts/phase1-wrap-pack/phase1-wrap-phase2-backlog.md",
    ],
    "required_boards": ["docs/artifacts/phase1-wrap-pack/phase1-wrap-phase2-backlog.md"],
    "summary_json": "phase2-kickoff-summary.json",
    "summary_md": "phase2-kickoff-summary.md",
    "pack_files": [
        "phase2-kickoff-baseline-snapshot.json",
        "phase2-kickoff-delivery-board.md",
        "phase2-kickoff-validation-commands.md",
    ],
    "evidence_json": "phase2-kickoff-execution-summary.json",
    "text_output": " phase-2 kickoff summary",
}


def main(argv: list[str] | None = None) -> int:
    return run_lane(argv, _CFG)
