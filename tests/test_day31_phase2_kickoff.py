from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day31_phase2_kickoff as d31


def _seed_repo(root: Path) -> None:
    (root / "README.md").write_text(
        "docs/integrations-day31-phase2-kickoff.md\nday31-phase2-kickoff\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-31-ultra-upgrade-report.md\nintegrations-day31-phase2-kickoff.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 31 — Phase-2 kickoff:** set baseline metrics from end of Phase 1 and define weekly growth targets.\n"
        "- **Day 32 — Release cadence setup:** lock weekly release rhythm and changelog publication checklist.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day31-phase2-kickoff.md").write_text(d31._DAY31_DEFAULT_PAGE, encoding="utf-8")
    (root / "docs/day-31-ultra-upgrade-report.md").write_text("# Day 31 report\n", encoding="utf-8")

    summary = root / "docs/artifacts/day30-wrap-pack/day30-phase1-wrap-summary.json"
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(
        json.dumps(
            {
                "summary": {"activation_score": 97, "strict_pass": True},
                "rollup": {"average_activation_score": 96.0},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    backlog = root / "docs/artifacts/day30-wrap-pack/day30-phase2-backlog.md"
    backlog.write_text(
        "\n".join(
            [
                "# Locked Phase-2 backlog",
                "- [ ] Day 31 baseline metrics + weekly targets",
                "- [ ] Day 32 release cadence + changelog checklist",
                "- [ ] Day 33 demo asset #1 (doctor)",
                "- [ ] Day 34 demo asset #2 (repo audit)",
                "- [ ] Day 35 weekly review #5",
                "- [ ] Day 36 demo asset #3 (security gate)",
                "- [ ] Day 37 demo asset #4 (cassette replay)",
                "- [ ] Day 38 distribution batch #1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day31_kickoff_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d31.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day31-phase2-kickoff"
    assert out["summary"]["activation_score"] >= 95


def test_day31_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d31.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day31-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day31-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day31-pack/day31-phase2-kickoff-summary.json").exists()
    assert (tmp_path / "artifacts/day31-pack/day31-phase2-kickoff-summary.md").exists()
    assert (tmp_path / "artifacts/day31-pack/day31-baseline-snapshot.json").exists()
    assert (tmp_path / "artifacts/day31-pack/day31-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day31-pack/day31-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day31-pack/evidence/day31-execution-summary.json").exists()


def test_day31_strict_fails_when_day30_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/artifacts/day30-wrap-pack/day30-phase1-wrap-summary.json").unlink()
    rc = d31.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day31_strict_fails_when_backlog_is_not_phase2_ready(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/artifacts/day30-wrap-pack/day30-phase2-backlog.md").write_text("- [ ] Day 31 baseline\n", encoding="utf-8")
    rc = d31.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day31_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day31-phase2-kickoff", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 31 phase-2 kickoff summary" in capsys.readouterr().out
