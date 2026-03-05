from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day76_contributor_recognition_closeout as d76


def _seed_repo(root: Path) -> None:
    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)
    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-day76-contributor-recognition-closeout.md\ncontributor-recognition-closeout\n",
        encoding="utf-8",
    )
    (root / "docs/index.md").write_text(
        "day-76-big-upgrade-report.md\nintegrations-day76-contributor-recognition-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text("Day 75\nDay 76\n", encoding="utf-8")
    (root / "docs/integrations-day76-contributor-recognition-closeout.md").write_text(
        d76._DAY76_DEFAULT_PAGE, encoding="utf-8"
    )

    summary = (
        root
        / "docs/artifacts/day75-trust-assets-refresh-closeout-pack/day75-trust-assets-refresh-closeout-summary.json"
    )
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(
        json.dumps(
            {
                "summary": {"activation_score": 95, "strict_pass": True},
                "checks": [{"passed": True}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    board = root / "docs/artifacts/day75-trust-assets-refresh-closeout-pack/day75-delivery-board.md"
    board.write_text(
        "\n".join(["# Day 75 delivery board", *["- [ ] Day 75 item" for _ in range(5)]]) + "\n",
        encoding="utf-8",
    )

    (root / "docs/roadmap/plans/day76-contributor-recognition-plan.json").write_text(
        json.dumps(
            {
                "plan_id": "day76-001",
                "contributors": ["alice", "bob"],
                "recognition_tracks": ["docs", "release"],
                "baseline": {"score": 60},
                "target": {"score": 85},
                "owner": "community-eng",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_day76_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d76.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day76-contributor-recognition-closeout"
    assert out["summary"]["strict_pass"] is True


def test_day76_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d76.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day76-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day76-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/day76-pack/day76-contributor-recognition-closeout-summary.json"
    ).exists()
    assert (tmp_path / "artifacts/day76-pack/day76-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day76-pack/evidence/day76-execution-summary.json").exists()


def test_day76_strict_fails_without_day75_summary(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day75-trust-assets-refresh-closeout-pack/day75-trust-assets-refresh-closeout-summary.json"
    ).unlink()
    assert d76.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day76_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["contributor-recognition-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 76 contributor recognition closeout summary" in capsys.readouterr().out
