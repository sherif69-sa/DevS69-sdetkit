from __future__ import annotations

from ._legacy_workflow import run_lane

_DEFAULT_PAGE_TEMPLATE = "# Baseline wrap ()\n\n## Baseline wrap\n"
_CFG = {
    "page_template": _DEFAULT_PAGE_TEMPLATE,
    "name": "baseline-wrap",
    "page_path": "docs/integrations-baseline-wrap.md",
    "required_inputs": [
        "docs/artifacts/kpi-audit-pack/kpi-audit-summary.json",
        "docs/artifacts/weekly-review-pack/weekly-review-summary.json",
        "docs/artifacts/baseline-hardening-pack/baseline-hardening-summary.json",
    ],
    "required_page_marker": "## Baseline wrap",
    "summary_json": "baseline-wrap-summary.json",
    "summary_md": "baseline-wrap-summary.md",
    "pack_files": [
        "baseline-wrap-release-readiness-backlog.md",
        "baseline-wrap-handoff-actions.md",
        "baseline-wrap-validation-commands.md",
    ],
    "evidence_json": "baseline-wrap-execution-summary.json",
    "text_output": " baseline wrap summary",
}


def main(argv: list[str] | None = None) -> int:
    return run_lane(argv, _CFG)
