from __future__ import annotations

from ._legacy_lane import run_lane

_DEFAULT_PAGE_TEMPLATE = "# Phase-1 wrap ()\n\n## Phase-1 wrap\n"
_CFG = {
    "name": "phase1-wrap",
    "page_path": "docs/integrations-phase1-wrap.md",
    "required_inputs": [
        "docs/artifacts/kpi-audit-pack/kpi-audit-summary.json",
        "docs/artifacts/weekly-review-pack/weekly-review-summary.json",
        "docs/artifacts/phase1-hardening-pack/phase1-hardening-summary.json",
    ],
    "required_page_marker": "## Phase-1 wrap",
    "summary_json": "phase1-wrap-summary.json",
    "summary_md": "phase1-wrap-summary.md",
    "pack_files": [
        "phase1-wrap-phase2-backlog.md",
        "phase1-wrap-handoff-actions.md",
        "phase1-wrap-validation-commands.md",
    ],
    "evidence_json": "phase1-wrap-execution-summary.json",
    "text_output": " phase-1 wrap summary",
}


def main(argv: list[str] | None = None) -> int:
    return run_lane(argv, _CFG)
