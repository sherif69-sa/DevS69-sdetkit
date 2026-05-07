from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_mkdocs_excludes_only_top_level_docs_readme() -> None:
    mkdocs = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")

    assert "exclude_docs: |\n  /README.md\n" in mkdocs
    assert "exclude_docs: |\n  README.md\n" not in mkdocs


def test_project_docs_readme_stays_nav_visible() -> None:
    mkdocs = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")

    assert "project/README.md" in mkdocs
