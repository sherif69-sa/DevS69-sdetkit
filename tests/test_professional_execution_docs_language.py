from __future__ import annotations

from pathlib import Path

MKDOCS = Path("mkdocs.yml")
EXECUTION_PLAN = Path("docs/operations-execution-plan.md")
EXECUTION_GUIDE = Path("docs/operations-execution-guide.md")


def test_mkdocs_execution_nav_uses_professional_labels() -> None:
    text = MKDOCS.read_text(encoding="utf-8")

    assert "Upgrade execution plan: operations-execution-plan.md" in text
    assert "Sequential execution guide: operations-execution-guide.md" in text

    assert "Phase-by-phase execution plan: operations-execution-plan.md" not in text
    assert "Phase execution one-by-one: operations-execution-guide.md" not in text


def test_execution_plan_uses_professional_stage_headings() -> None:
    text = EXECUTION_PLAN.read_text(encoding="utf-8")

    required = [
        "## Baseline readiness — Build the baseline evidence lane",
        "## Quality governance — Expand the quality engine",
        "## Operational governance — Enforce enterprise governance",
        "## Ecosystem readiness — Scale integrations",
        "## Metrics readiness — Operationalize metrics and commercialization",
        "## Readiness control loop (run every stage)",
    ]

    banned = [
        "## Platform readiness — Expand the quality engine",
        "## Operational readiness — Enforce enterprise governance",
        "## Adoption readiness — Scale ecosystem integrations",
        "## Scale readiness — Operationalize metrics and commercialization",
        "## Phase control loop (run every phase)",
    ]

    for phrase in required:
        assert phrase in text

    for phrase in banned:
        assert phrase not in text


def test_execution_guide_prefers_readiness_stage_language() -> None:
    text = EXECUTION_GUIDE.read_text(encoding="utf-8")

    required = [
        "readiness stages",
        "readiness-stage exit criteria",
        "Readiness-stage completion contract",
        "Readiness-stage decision record template",
        "active readiness queue",
    ]

    banned = [
        "all 6 phases",
        "one phase at a time",
        "Phase completion contract",
        "Phase gate decision record template",
        "active phase queue",
    ]

    for phrase in required:
        assert phrase in text

    for phrase in banned:
        assert phrase not in text
