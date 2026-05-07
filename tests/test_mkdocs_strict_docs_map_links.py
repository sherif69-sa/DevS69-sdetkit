from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_mkdocs_excludes_docs_readme_conflict() -> None:
    mkdocs = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")

    assert "exclude_docs: |" in mkdocs
    assert "  /README.md" in mkdocs


def test_docs_map_does_not_link_to_excluded_readme() -> None:
    docs_map = (ROOT / "docs" / "docs-map.md").read_text(encoding="utf-8")

    assert "(README.md)" not in docs_map
    assert "(index.md)" in docs_map
