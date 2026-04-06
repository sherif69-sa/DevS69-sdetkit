from __future__ import annotations

from ._legacy_lane import run_lane

_DEFAULT_PAGE_TEMPLATE = "# KPI instrumentation ()\n\n## KPI instrumentation\n"
_CFG = {
    "name": "kpi-instrumentation",
    "page_path": "docs/integrations-kpi-instrumentation.md",
    "required_inputs": ["docs/artifacts/demo-asset2-pack/demo-asset2-summary.json"],
    "required_boards": ["docs/artifacts/demo-asset2-pack/demo-asset2-delivery-board.md"],
    "summary_json": "kpi-instrumentation-summary.json",
    "summary_md": "kpi-instrumentation-summary.md",
    "pack_files": [
        "kpi-dictionary.csv",
        "alert-policy.md",
        "delivery-board.md",
        "kpi-instrumentation-validation-commands.md",
    ],
    "evidence_json": "kpi-instrumentation-execution-summary.json",
    "text_output": " KPI instrumentation summary",
}


def main(argv: list[str] | None = None) -> int:
    return run_lane(argv, _CFG)
