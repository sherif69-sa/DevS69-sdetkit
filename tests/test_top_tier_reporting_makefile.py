from __future__ import annotations

from pathlib import Path


MAKEFILE = Path('Makefile')


def test_top_tier_reporting_makefile_exposes_config_variables() -> None:
    text = MAKEFILE.read_text()

    assert 'DATE_TAG ?=' in text
    assert 'WINDOW_START ?=' in text
    assert 'WINDOW_END ?=' in text
    assert 'GENERATED_AT ?=' in text


def test_top_tier_reporting_target_uses_parameterized_variables() -> None:
    text = MAKEFILE.read_text()

    assert 'top-tier-reporting: venv' in text
    assert 'portfolio-input-sample-$(DATE_TAG).jsonl' in text
    assert '--window-start $(WINDOW_START)' in text
    assert '--window-end $(WINDOW_END)' in text
    assert '--generated-at $(GENERATED_AT)' in text
    assert 'top-tier-bundle-manifest-$(DATE_TAG).json' in text
    assert 'promote_top_tier_bundle.py --bundle-dir docs/artifacts/top-tier-bundle --date-tag $(DATE_TAG)' in text


def test_top_tier_reporting_ci_target_includes_freshness_and_contract_tests() -> None:
    text = MAKEFILE.read_text()

    assert 'top-tier-reporting-ci: top-tier-reporting reporting-freshness-check' in text
    assert 'tests/test_check_top_tier_artifact_set.py' in text
    assert 'tests/test_check_reporting_freshness.py' in text
    assert 'top-tier-reporting-merge-ready: top-tier-reporting-ci' in text
    assert 'tests/test_top_tier_reporting_workflow.py' in text
    assert 'tests/test_top_tier_reporting_readme.py' in text
    assert 'top-tier-artifact-set-check-$(DATE_TAG).json' in text
    assert 'top-tier-freshness-check-$(DATE_TAG).json' in text
