from __future__ import annotations

from pathlib import Path

DOCS_INDEX = Path("docs/index.md")
RECIPE = Path("docs/portfolio-reporting-recipe.md")


def test_docs_index_mentions_top_tier_troubleshooting() -> None:
    text = DOCS_INDEX.read_text()
    assert "Top-tier reporting troubleshooting" in text
    assert "top-tier-reporting-troubleshooting.md" in text


def test_portfolio_recipe_links_troubleshooting_page() -> None:
    text = RECIPE.read_text()
    assert "Top-tier reporting troubleshooting" in text
    assert "top-tier-reporting-troubleshooting.md" in text
