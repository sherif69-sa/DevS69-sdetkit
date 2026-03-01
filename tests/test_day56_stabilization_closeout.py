from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day56_stabilization_closeout as d56


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-day56-stabilization-closeout.md\nday56-stabilization-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-56-big-upgrade-report.md\nintegrations-day56-stabilization-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 56 — Stabilization closeout:** enforce deterministic follow-through and recovery loops.\n"
        "- **Day 57 — KPI deep audit:** validate strict trendlines and blockers.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day56-stabilization-closeout.md").write_text(
        d56._DAY56_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-56-big-upgrade-report.md").write_text("# Day 56 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day55-contributor-activation-closeout-pack/day55-contributor-activation-closeout-summary.json"
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
        root / "docs/artifacts/day55-contributor-activation-closeout-pack/day55-delivery-board.md"
    )
    board.write_text(
        "\n".join(
            [
                "# Day 55 delivery board",
                "- [ ] Day 55 contributor brief committed",
                "- [ ] Day 55 activation plan reviewed with owner + backup",
                "- [ ] Day 55 contributor ladder exported",
                "- [ ] Day 55 KPI scorecard snapshot exported",
                "- [ ] Day 56 priorities drafted from Day 55 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day56_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d56.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day56-stabilization-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day56_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d56.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day56-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day56-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day56-pack/day56-stabilization-closeout-summary.json").exists()
    assert (tmp_path / "artifacts/day56-pack/day56-stabilization-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/day56-pack/day56-stabilization-brief.md").exists()
    assert (tmp_path / "artifacts/day56-pack/day56-risk-ledger.csv").exists()
    assert (tmp_path / "artifacts/day56-pack/day56-stabilization-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day56-pack/day56-execution-log.md").exists()
    assert (tmp_path / "artifacts/day56-pack/day56-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day56-pack/day56-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day56-pack/evidence/day56-execution-summary.json").exists()


def test_day56_strict_fails_without_day55(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day55-contributor-activation-closeout-pack/day55-contributor-activation-closeout-summary.json"
    ).unlink()
    assert d56.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day56_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day56-stabilization-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 56 stabilization closeout summary" in capsys.readouterr().out
