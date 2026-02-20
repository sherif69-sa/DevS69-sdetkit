from __future__ import annotations

from pathlib import Path

from sdetkit import weekly_review


def test_weekly_review_repo_passes_core_kpis() -> None:
    review = weekly_review.build_weekly_review(Path(".").resolve())
    assert review.kpis["days_planned"] == 6
    assert review.kpis["days_completed"] >= 6
    assert review.kpis["completion_rate_percent"] == 100


def test_week2_review_repo_passes_core_kpis() -> None:
    review = weekly_review.build_weekly_review(Path(".").resolve(), week=2)
    assert review.week == 2
    assert review.kpis["days_planned"] == 6
    assert review.kpis["days_completed"] >= 6
    assert review.kpis["completion_rate_percent"] == 100


def test_week2_review_adds_growth_signals_and_deltas() -> None:
    review = weekly_review.build_weekly_review(
        Path(".").resolve(),
        week=2,
        signals={"traffic": 1800, "stars": 90, "discussions": 24, "blocker_fixes": 7},
        previous_signals={"traffic": 1200, "stars": 77, "discussions": 18, "blocker_fixes": 5},
    )
    assert review.growth_signals == {
        "traffic": 1800,
        "stars": 90,
        "discussions": 24,
        "blocker_fixes": 7,
    }
    assert review.growth_deltas == {
        "traffic": 600,
        "stars": 13,
        "discussions": 6,
        "blocker_fixes": 2,
    }


def test_weekly_review_flags_missing_files(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# temp\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "day-1-ultra-upgrade-report.md").write_text("ok\n", encoding="utf-8")

    review = weekly_review.build_weekly_review(tmp_path)
    assert review.kpis["days_completed"] < review.kpis["days_planned"]
    assert any(item["status"] == "incomplete" for item in review.shipped)


def test_week3_review_repo_passes_core_kpis() -> None:
    review = weekly_review.build_weekly_review(Path(".").resolve(), week=3)
    assert review.week == 3
    assert review.kpis["days_planned"] == 6
    assert review.kpis["days_completed"] >= 6
    assert review.kpis["completion_rate_percent"] == 100


def test_week3_review_adds_growth_signals_and_deltas() -> None:
    review = weekly_review.build_weekly_review(
        Path(".").resolve(),
        week=3,
        signals={"traffic": 2550, "stars": 132, "discussions": 33, "blocker_fixes": 10},
        previous_signals={"traffic": 2100, "stars": 120, "discussions": 28, "blocker_fixes": 8},
    )
    assert review.growth_signals == {
        "traffic": 2550,
        "stars": 132,
        "discussions": 33,
        "blocker_fixes": 10,
    }
    assert review.growth_deltas == {
        "traffic": 450,
        "stars": 12,
        "discussions": 5,
        "blocker_fixes": 2,
    }


def test_week3_emit_pack_writes_closeout_artifacts(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "docs" / "artifacts").mkdir(parents=True)

    for day in range(15, 21):
        (root / "docs" / f"day-{day}-ultra-upgrade-report.md").write_text("ok\n", encoding="utf-8")
    for artifact in (
        "day15-github-actions-quickstart-sample.md",
        "day16-gitlab-ci-quickstart-sample.md",
        "day17-quality-contribution-delta-sample.md",
        "day18-reliability-evidence-pack-sample.md",
        "day19-release-readiness-board-sample.md",
        "day20-release-narrative-sample.md",
    ):
        (root / "docs" / "artifacts" / artifact).write_text("ok\n", encoding="utf-8")

    args = [
        "--root",
        str(root),
        "--week",
        "3",
        "--signals-file",
        "docs/artifacts/day21-growth-signals.json",
        "--previous-signals-file",
        "docs/artifacts/day14-growth-signals.json",
        "--emit-pack-dir",
        "docs/artifacts/day21-weekly-pack",
        "--format",
        "json",
        "--strict",
    ]

    (root / "docs" / "artifacts" / "day21-growth-signals.json").write_text(
        '{"traffic": 2550, "stars": 132, "discussions": 33, "blocker_fixes": 10}\n',
        encoding="utf-8",
    )
    (root / "docs" / "artifacts" / "day14-growth-signals.json").write_text(
        '{"traffic": 1800, "stars": 90, "discussions": 24, "blocker_fixes": 7}\n', encoding="utf-8"
    )

    assert weekly_review.main(args) == 0

    pack = root / "docs" / "artifacts" / "day21-weekly-pack"
    assert (pack / "day21-closeout-checklist.md").exists()
    assert (pack / "day21-kpi-scorecard.json").exists()
    assert (pack / "day21-contributor-response-plan.md").exists()
    assert (pack / "day21-release-narrative-brief.md").exists()
