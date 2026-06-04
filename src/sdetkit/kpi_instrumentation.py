from __future__ import annotations

from ._legacy_workflow import run_lane

_DEFAULT_PAGE_TEMPLATE = "# KPI instrumentation ()\n\n## KPI instrumentation\n"
_CFG = {
    "page_template": _DEFAULT_PAGE_TEMPLATE,
    "name": "kpi-instrumentation",
    "page_path": "docs/integrations-kpi-instrumentation.md",
    "required_inputs": ["docs/artifacts/example-asset2-pack/example-asset2-summary.json"],
    "required_boards": ["docs/artifacts/example-asset2-pack/example-asset2-delivery-board.md"],
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
