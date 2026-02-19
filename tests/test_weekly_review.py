from __future__ import annotations

from pathlib import Path

from sdetkit import weekly_review


def test_weekly_review_repo_passes_core_kpis() -> None:
    review = weekly_review.build_weekly_review(Path('.').resolve())
    assert review.kpis['days_planned'] == 6
    assert review.kpis['days_completed'] >= 6
    assert review.kpis['completion_rate_percent'] == 100


def test_weekly_review_flags_missing_files(tmp_path: Path) -> None:
    (tmp_path / 'README.md').write_text('# temp\n', encoding='utf-8')
    (tmp_path / 'docs').mkdir()
    (tmp_path / 'docs' / 'day-1-ultra-upgrade-report.md').write_text('ok\n', encoding='utf-8')

    review = weekly_review.build_weekly_review(tmp_path)
    assert review.kpis['days_completed'] < review.kpis['days_planned']
    assert any(item['status'] == 'incomplete' for item in review.shipped)
