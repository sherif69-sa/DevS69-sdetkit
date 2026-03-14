from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day49_weekly_review_closeout as d49


def _seed_repo(root: Path) -> None:
    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)
    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)
    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)
    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)
    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-weekly-review-closeout.md\nweekly-review-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-49-big-upgrade-report.md\nintegrations-weekly-review-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 49 — Weekly review closeout:** convert objection wins into deterministic weekly review loops.\n"
        "- **Day 50 — Execution prioritization:** lock ownership and priorities for release motion.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-weekly-review-closeout.md").write_text(
        d49._DAY49_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/impact-49-big-upgrade-report.md").write_text("# Day 49 report\n", encoding="utf-8")

    summary = (
        root / "docs/artifacts/day48-objection-closeout-pack/day48-objection-closeout-summary.json"
    )
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(
        json.dumps(
            {
                "summary": {"activation_score": 99, "strict_pass": True},
                "checks": [{"check_id": "ok", "passed": True}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    board = root / "docs/artifacts/day48-objection-closeout-pack/day48-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 48 delivery board",
                "- [ ] Day 48 objection plan draft committed",
                "- [ ] Day 48 review notes captured with owner + backup",
                "- [ ] Day 48 FAQ objection map exported",
                "- [ ] Day 48 KPI scorecard snapshot exported",
                "- [ ] Day 49 weekly-review priorities drafted from Day 48 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day49_weekly_review_closeout_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d49.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day49-advanced-weekly-review-control-tower"
    assert out["legacy_name"] == "weekly-review-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day49_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d49.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day49-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day49-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day49-pack/weekly-review-closeout-summary.json").exists()
    assert (tmp_path / "artifacts/day49-pack/weekly-review-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/day49-pack/day49-weekly-review-brief.md").exists()
    assert (tmp_path / "artifacts/day49-pack/day49-weekly-review-risk-register.csv").exists()
    assert (tmp_path / "artifacts/day49-pack/day49-weekly-review-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day49-pack/day49-advanced-priority-matrix.json").exists()
    assert (tmp_path / "artifacts/day49-pack/day49-execution-log.md").exists()
    assert (tmp_path / "artifacts/day49-pack/day49-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day49-pack/day49-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day49-pack/evidence/day49-execution-summary.json").exists()


def test_day49_strict_fails_when_day48_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day48-objection-closeout-pack/day48-objection-closeout-summary.json"
    ).unlink()
    rc = d49.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day49_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["weekly-review-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 49 advanced weekly review control tower summary" in capsys.readouterr().out


def test_day49_advanced_alias_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(
        ["day49-advanced-weekly-review-control-tower", "--root", str(tmp_path), "--format", "text"]
    )
    assert rc == 0
    assert "advanced weekly review control tower" in capsys.readouterr().out


def test_day49_non_day_alias_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["weekly-review-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "advanced weekly review control tower" in capsys.readouterr().out
