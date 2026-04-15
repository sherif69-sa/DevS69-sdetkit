from __future__ import annotations

from pathlib import Path


README = Path('README.md')


def test_readme_mentions_top_tier_reporting_pipeline() -> None:
    text = README.read_text()

    assert '## Top-tier reporting sample pipeline' in text
    assert 'make top-tier-reporting' in text
    assert 'make top-tier-reporting-ci' in text
    assert 'make top-tier-reporting-merge-ready' in text
    assert 'top-tier-freshness-check-<date>.json' in text
    assert 'docs/portfolio-reporting-recipe.md' in text
    assert 'docs/kpi-schema.md' in text
    assert 'docs/top-tier-reporting-troubleshooting.md' in text
