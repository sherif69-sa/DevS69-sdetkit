from __future__ import annotations

from pathlib import Path


WORKFLOW = Path('.github/workflows/top-tier-reporting-sample.yml')


def test_top_tier_reporting_workflow_runs_make_target_and_contract_tests() -> None:
    text = WORKFLOW.read_text()

    assert 'make top-tier-reporting-ci' in text
    assert '- name: Run top-tier reporting CI lane' in text
    assert 'DATE_TAG: 2026-04-17' in text
    assert 'WINDOW_START: 2026-04-11' in text
    assert 'WINDOW_END: 2026-04-17' in text
    assert 'GENERATED_AT: 2026-04-17T10:00:00Z' in text


def test_top_tier_reporting_workflow_uploads_key_artifacts() -> None:
    text = WORKFLOW.read_text()

    assert 'docs/artifacts/portfolio-scorecard-sample-${{ env.DATE_TAG }}.json' in text
    assert 'docs/artifacts/kpi-weekly-from-portfolio-${{ env.DATE_TAG }}.json' in text
    assert 'docs/artifacts/kpi-weekly-contract-check-${{ env.DATE_TAG }}.json' in text
    assert 'docs/artifacts/top-tier-contract-check-${{ env.DATE_TAG }}.json' in text
    assert 'docs/artifacts/top-tier-bundle-manifest-${{ env.DATE_TAG }}.json' in text
    assert 'docs/artifacts/top-tier-bundle-manifest-check-${{ env.DATE_TAG }}.json' in text
    assert 'docs/artifacts/top-tier-freshness-check-${{ env.DATE_TAG }}.json' in text
