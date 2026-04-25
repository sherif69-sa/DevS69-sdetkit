from __future__ import annotations

from ._legacy_lane import run_lane

# Public test/fixture defaults intentionally kept as module attributes.
_DEFAULT_PAGE_TEMPLATE = "# KPI audit ()\n\n## KPI audit\n"
_DEFAULT_BASELINE = {"stars_per_week": 10, "ctr": 1.0, "discussions": 5, "prs": 4}
_DEFAULT_CURRENT = {"stars_per_week": 12, "ctr": 1.1, "discussions": 6, "prs": 5}

_CFG = {
    "name": "kpi-audit",
    "page_path": "docs/integrations-kpi-audit.md",
    "required_inputs": [
        "docs/artifacts/kpi-audit-pack/kpi-baseline.json",
        "docs/artifacts/kpi-audit-pack/kpi-current.json",
    ],
    "required_page_marker": "## KPI audit",
    "summary_json": "kpi-audit-summary.json",
    "summary_md": "kpi-audit-scorecard.md",
    "pack_files": [
        "kpi-delta-table.md",
        "kpi-corrective-actions.md",
        "kpi-audit-validation-commands.md",
    ],
    "evidence_json": "kpi-audit-execution-summary.json",
    "text_output": " KPI audit summary",
    "default_page_template": _DEFAULT_PAGE_TEMPLATE,
    "default_baseline": _DEFAULT_BASELINE,
    "default_current": _DEFAULT_CURRENT,
}


def main(argv: list[str] | None = None) -> int:
    return run_lane(argv, _CFG)
