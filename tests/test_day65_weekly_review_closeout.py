from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day65_weekly_review_closeout as d65


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-day65-weekly-review-closeout.md\nday65-weekly-review-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-65-big-upgrade-report.md\nintegrations-day65-weekly-review-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 65 — Weekly review #9:** report baseline movement and community signal quality.\n"
        "- **Day 66 — Integration expansion #2:** publish advanced GitLab CI implementation path.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day65-weekly-review-closeout.md").write_text(
        d65._DAY65_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-65-big-upgrade-report.md").write_text("# Day 65 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day64-integration-expansion-closeout-pack/day64-integration-expansion-closeout-summary.json"
    )
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(
        json.dumps(
            {
                "summary": {"activation_score": 100, "strict_pass": True},
                "checks": [{"passed": True}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    board = (
        root / "docs/artifacts/day64-integration-expansion-closeout-pack/day64-delivery-board.md"
    )
    board.write_text(
        "\n".join(
            [
                "# Day 64 delivery board",
                "- [ ] Day 64 integration brief committed",
                "- [ ] Day 64 advanced workflow blueprint published",
                "- [ ] Day 64 matrix and concurrency plan exported",
                "- [ ] Day 64 KPI scorecard snapshot exported",
                "- [ ] Day 65 weekly review priorities drafted from Day 64 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    workflow = root / ".github/workflows/day64-advanced-github-actions-reference.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text("name: Day64 Advanced GitHub Actions Reference\n", encoding="utf-8")


def test_day65_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d65.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day65-weekly-review-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day65_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d65.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day65-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day65-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day65-pack/day65-weekly-review-closeout-summary.json").exists()
    assert (tmp_path / "artifacts/day65-pack/day65-weekly-review-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/day65-pack/day65-weekly-brief.md").exists()
    assert (tmp_path / "artifacts/day65-pack/day65-kpi-dashboard.json").exists()
    assert (tmp_path / "artifacts/day65-pack/day65-governance-decision-register.md").exists()
    assert (tmp_path / "artifacts/day65-pack/day65-risk-ledger.csv").exists()
    assert (tmp_path / "artifacts/day65-pack/day65-execution-log.md").exists()
    assert (tmp_path / "artifacts/day65-pack/day65-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day65-pack/day65-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day65-pack/evidence/day65-execution-summary.json").exists()


def test_day65_strict_fails_without_day64(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day64-integration-expansion-closeout-pack/day64-integration-expansion-closeout-summary.json"
    ).unlink()
    assert d65.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day65_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day65-weekly-review-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 65 weekly review closeout summary" in capsys.readouterr().out
