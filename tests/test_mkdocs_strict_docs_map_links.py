from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_mkdocs_excludes_docs_readme_conflict() -> None:
    mkdocs = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")

    assert "exclude_docs: |" in mkdocs
    assert "  /README.md" in mkdocs


def test_docs_map_does_not_link_to_excluded_readme() -> None:
    docs_map = (ROOT / "docs" / "docs-map.md").read_text(encoding="utf-8")

    assert "README.md)" not in docs_map
    assert "(index.md)" in docs_map


def test_built_docs_do_not_link_to_intentionally_excluded_targets() -> None:
    warning_prone_docs = [
        ROOT / "docs" / "platform-problem-authoring.md",
        ROOT / "docs" / "kpi-schema.md",
        ROOT / "docs" / "portfolio-reporting-recipe.md",
        ROOT / "docs" / "top-tier-program-dashboard.md",
        ROOT / "docs" / "cto-execution-workflow.md",
    ]
    excluded_link_fragments = [
        "](artifacts/",
        "](automation-templates-engine.md)",
        "](kpi-baseline-week-",
        "](cto-",
        "](executive-",
    ]

    offenders: list[str] = []
    for doc_path in warning_prone_docs:
        doc_text = doc_path.read_text(encoding="utf-8")
        for fragment in excluded_link_fragments:
            if fragment in doc_text:
                offenders.append(f"{doc_path.relative_to(ROOT)} contains {fragment}")

    assert offenders == []
