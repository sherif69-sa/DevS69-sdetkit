from __future__ import annotations

from pathlib import Path


WORKFLOW = Path('.github/workflows/top-tier-reporting-sample.yml')


def test_top_tier_reporting_workflow_runs_make_target_and_contract_tests() -> None:
    text = WORKFLOW.read_text()

    assert 'run: make top-tier-reporting' in text
    assert 'tests/test_build_portfolio_scorecard.py' in text
    assert 'tests/test_build_kpi_weekly_snapshot.py' in text
    assert 'tests/test_check_top_tier_reporting_contract.py' in text
    assert 'tests/test_check_top_tier_bundle_manifest.py' in text


def test_top_tier_reporting_workflow_uploads_key_artifacts() -> None:
    text = WORKFLOW.read_text()

    assert 'docs/artifacts/portfolio-scorecard-sample-2026-04-17.json' in text
    assert 'docs/artifacts/kpi-weekly-from-portfolio-2026-04-17.json' in text
    assert 'docs/artifacts/kpi-weekly-contract-check-2026-04-17.json' in text
    assert 'docs/artifacts/top-tier-contract-check-2026-04-17.json' in text
    assert 'docs/artifacts/top-tier-bundle-manifest-2026-04-17.json' in text
    assert 'docs/artifacts/top-tier-bundle-manifest-check-2026-04-17.json' in text
