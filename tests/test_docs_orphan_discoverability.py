from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
MKDOCS = ROOT / "mkdocs.yml"

CANDIDATES = (
    "operator-evidence-review-guide.md",
    "release-readiness-evidence-handoff.md",
    "upgrade-next-commands.md",
    "policy-and-baselines.md",
    "evidence-circuit-architecture-checkpoint.md",
    "evidence-graph-summary.md",
    "repo-index-engine.md",
    "dashboard-reporting-polish.md",
    "evidence-circuit-review-pack.md",
    "next-10-followups.md",
    "operations-handbook.md",
    "real-workflow-operations.md",
    "sdetkit-vs-ad-hoc.md",
    "examples.md",
    "operations-execution-checklist.md",
)

GROUP_HEADINGS = (
    "## Evidence review and release handoff",
    "## Operations and follow-up",
    "## Policy and repository structure",
    "## Examples and positioning",
)

FORBIDDEN_LINK_PREFIXES = (
    "archive/",
    "artifacts/",
    "roadmap/reports/",
    "business_execution/",
)


def _nav_targets() -> list[str]:
    pattern = re.compile(r":\s+([A-Za-z0-9_./-]+\.md)\s*$")
    return [
        match.group(1)
        for line in MKDOCS.read_text(encoding="utf-8").splitlines()
        if (match := pattern.search(line))
    ]


def _exclude_block() -> str:
    lines = MKDOCS.read_text(encoding="utf-8").splitlines()
    start = lines.index("exclude_docs: |")
    block = []
    for line in lines[start:]:
        if block and line and not line.startswith("  "):
            break
        block.append(line)
    return "\n".join(block) + "\n"


def test_material_map_exists_with_exact_structure() -> None:
    path = DOCS / "orphan-docs-material-map.md"
    text = path.read_text(encoding="utf-8")

    assert len(re.findall(r"(?m)^# ", text)) == 1
    assert text.startswith("# Curated advanced docs material map\n")
    normalized_text = " ".join(text.split())
    assert "not a primary onboarding path" in normalized_text
    assert "does not reclassify" in normalized_text
    assert "Choose a page by the task" in normalized_text
    assert text.count("| Page | Use when | Why it remains secondary |") == 4

    for heading in GROUP_HEADINGS:
        assert text.count(heading) == 1


def test_all_ranked_candidates_are_linked_once() -> None:
    text = (DOCS / "orphan-docs-material-map.md").read_text(encoding="utf-8")

    for candidate in CANDIDATES:
        assert (DOCS / candidate).is_file()
        assert text.count(f"]({candidate})") == 1


def test_candidates_stay_out_of_direct_navigation() -> None:
    nav_targets = _nav_targets()

    for candidate in CANDIDATES:
        assert candidate not in nav_targets

    assert nav_targets.count("orphan-docs-material-map.md") == 1


def test_canonical_docs_map_links_secondary_material_map() -> None:
    text = (DOCS / "docs-map.md").read_text(encoding="utf-8")

    assert text.count("[Curated advanced docs material map](orphan-docs-material-map.md)") == 1


def test_material_map_does_not_link_intentional_non_primary_families() -> None:
    text = (DOCS / "orphan-docs-material-map.md").read_text(encoding="utf-8")
    markdown_targets = re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)

    for target in markdown_targets:
        normalized = target.split("#", 1)[0]
        assert not normalized.startswith(FORBIDDEN_LINK_PREFIXES)
        assert not normalized.endswith("-report.md")
        assert "big-upgrade-report-" not in normalized
        assert "ultra-upgrade-report-" not in normalized


def test_mkdocs_exclusion_contract_is_unchanged() -> None:
    expected = """exclude_docs: |
  /README.md
  artifacts/**
  roadmap/reports/**
  *-report.md
  impact-*-*-report.md
  big-upgrade-report-*.md
  ultra-upgrade-report-*.md
  executive-*.md
  cto-*.md
  production-*.md
  kpi-baseline-week-*.md
  repo-*-20*.md
  agentos-*.md
  automation-templates-engine.md
  integrations-*.md
  !integrations-and-extension-boundary.md
"""
    assert _exclude_block() == expected
