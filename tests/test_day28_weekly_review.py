from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day28_weekly_review as d28


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-day28-weekly-review.md\nday28-weekly-review\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text("day-28-ultra-upgrade-report.md\n", encoding="utf-8")
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 28 — Weekly review #4:** document wins, misses, and corrective actions.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day28-weekly-review.md").write_text(
        d28._DAY28_DEFAULT_PAGE, encoding="utf-8"
    )

    d25 = root / "docs/artifacts/day25-community-pack"
    d26 = root / "docs/artifacts/day26-external-contribution-pack"
    d27 = root / "docs/artifacts/day27-kpi-pack"
    d25.mkdir(parents=True, exist_ok=True)
    d26.mkdir(parents=True, exist_ok=True)
    d27.mkdir(parents=True, exist_ok=True)
    (d25 / "day25-community-summary.json").write_text(
        '{"summary": {"activation_score": 95}}\n', encoding="utf-8"
    )
    (d26 / "day26-external-contribution-summary.json").write_text(
        '{"summary": {"activation_score": 93}}\n', encoding="utf-8"
    )
    (d27 / "day27-kpi-summary.json").write_text(
        '{"summary": {"activation_score": 97}}\n', encoding="utf-8"
    )


def test_day28_weekly_review_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d28.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day28-weekly-review"
    assert out["summary"]["activation_score"] >= 90


def test_day28_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d28.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day28-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day28-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day28-pack/day28-weekly-review-summary.json").exists()
    assert (tmp_path / "artifacts/day28-pack/day28-kpi-rollup.md").exists()
    assert (tmp_path / "artifacts/day28-pack/day28-wins-misses-actions.md").exists()
    assert (tmp_path / "artifacts/day28-pack/day28-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day28-pack/evidence/day28-execution-summary.json").exists()


def test_day28_strict_fails_when_sections_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/integrations-day28-weekly-review.md").write_text(
        "# Weekly review #4 (Day 28)\n", encoding="utf-8"
    )
    rc = d28.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day28_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day28-weekly-review", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 28 weekly review summary" in capsys.readouterr().out
