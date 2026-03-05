from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day69_case_study_prep1_closeout as d69


def _seed_repo(root: Path) -> None:
    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)
    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-day69-case-study-prep1-closeout.md\nday69-case-study-prep1-closeout\n",
        encoding="utf-8",
    )
    (root / "docs/index.md").write_text(
        "day-69-big-upgrade-report.md\nintegrations-day69-case-study-prep1-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text("Day 69\nDay 70\n", encoding="utf-8")
    (root / "docs/integrations-day69-case-study-prep1-closeout.md").write_text(
        d69._DAY69_DEFAULT_PAGE, encoding="utf-8"
    )

    summary = (
        root
        / "docs/artifacts/day68-integration-expansion4-closeout-pack/day68-integration-expansion4-closeout-summary.json"
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
        root / "docs/artifacts/day68-integration-expansion4-closeout-pack/day68-delivery-board.md"
    )
    board.write_text(
        "\n".join(
            [
                "# Day 68 delivery board",
                "- [ ] Day 68 item 1",
                "- [ ] Day 68 item 2",
                "- [ ] Day 68 item 3",
                "- [ ] Day 68 item 4",
                "- [ ] Day 68 item 5",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "docs/roadmap/plans/day69-reliability-case-study.json").write_text(
        json.dumps(
            {
                "case_id": "day69-001",
                "metric": "failure-rate",
                "baseline": {"value": 5.1},
                "after": {"value": 2.9},
                "confidence": 0.93,
                "owner": "qa-platform",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_day69_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d69.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day69-case-study-prep1-closeout"
    assert out["summary"]["strict_pass"] is True


def test_day69_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d69.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day69-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day69-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day69-pack/day69-case-study-prep1-closeout-summary.json").exists()
    assert (tmp_path / "artifacts/day69-pack/day69-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day69-pack/evidence/day69-execution-summary.json").exists()


def test_day69_strict_fails_without_day68_summary(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day68-integration-expansion4-closeout-pack/day68-integration-expansion4-closeout-summary.json"
    ).unlink()
    assert d69.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day69_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day69-case-study-prep1-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 69 case-study prep #1 closeout summary" in capsys.readouterr().out
