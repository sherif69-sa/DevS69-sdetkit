from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day78_ecosystem_priorities_closeout as d78


def _seed_repo(root: Path) -> None:
    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)
    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-day78-ecosystem-priorities-closeout.md\necosystem-priorities-closeout\n",
        encoding="utf-8",
    )
    (root / "docs/index.md").write_text(
        "day-78-big-upgrade-report.md\nintegrations-day78-ecosystem-priorities-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text("Day 77\nDay 78\n", encoding="utf-8")
    (root / "docs/integrations-day78-ecosystem-priorities-closeout.md").write_text(
        d78._DAY78_DEFAULT_PAGE, encoding="utf-8"
    )

    summary = (
        root
        / "docs/artifacts/day77-community-touchpoint-closeout-pack/day77-community-touchpoint-closeout-summary.json"
    )
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(
        json.dumps(
            {
                "summary": {"activation_score": 97, "strict_pass": True},
                "checks": [{"passed": True}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    board = root / "docs/artifacts/day77-community-touchpoint-closeout-pack/day77-delivery-board.md"
    board.write_text(
        "\n".join(["# Day 77 delivery board", *["- [ ] Day 77 item" for _ in range(5)]]) + "\n",
        encoding="utf-8",
    )

    (root / "docs/roadmap/plans/day78-ecosystem-priorities-plan.json").write_text(
        json.dumps(
            {
                "plan_id": "day78-001",
                "contributors": ["platform", "docs"],
                "ecosystem_tracks": ["integrations", "playbooks"],
                "baseline": {"score": 63},
                "target": {"score": 88},
                "owner": "ecosystem-eng",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_day78_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d78.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "ecosystem-priorities-closeout"
    assert out["summary"]["strict_pass"] is True


def test_day78_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d78.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day78-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day78-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/day78-pack/day78-ecosystem-priorities-closeout-summary.json"
    ).exists()
    assert (tmp_path / "artifacts/day78-pack/day78-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day78-pack/evidence/day78-execution-summary.json").exists()


def test_day78_strict_fails_without_day77_summary(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day77-community-touchpoint-closeout-pack/day77-community-touchpoint-closeout-summary.json"
    ).unlink()
    assert d78.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day78_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(
        ["ecosystem-priorities-closeout", "--root", str(tmp_path), "--format", "text"]
    )
    assert rc == 0
    assert "Ecosystem Priorities Closeout summary" in capsys.readouterr().out
