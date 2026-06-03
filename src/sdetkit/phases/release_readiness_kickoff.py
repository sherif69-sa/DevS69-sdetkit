from __future__ import annotations

from ._legacy_workflow import run_lane

_DEFAULT_PAGE_TEMPLATE = "# Release readiness kickoff ()\n\n## Release readiness kickoff\n"
_CFG = {
    "page_template": _DEFAULT_PAGE_TEMPLATE,
    "name": "release-readiness-kickoff",
    "page_path": "docs/integrations-release-readiness-kickoff.md",
    "required_inputs": [
        "docs/artifacts/baseline-wrap-pack/baseline-wrap-summary.json",
        "docs/artifacts/baseline-wrap-pack/baseline-wrap-release-readiness-backlog.md",
    ],
    "required_boards": [
        "docs/artifacts/baseline-wrap-pack/baseline-wrap-release-readiness-backlog.md"
    ],
    "summary_json": "release-readiness-kickoff-summary.json",
    "summary_md": "release-readiness-kickoff-summary.md",
    "pack_files": [
        "release-readiness-kickoff-baseline-snapshot.json",
        "release-readiness-kickoff-delivery-board.md",
        "release-readiness-kickoff-validation-commands.md",
    ],
    "evidence_json": "release-readiness-kickoff-execution-summary.json",
    "text_output": " release readiness kickoff summary",
}


def main(argv: list[str] | None = None) -> int:
    return run_lane(argv, _CFG)
