from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day61_phase3_kickoff_closeout as d61


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-day61-phase3-kickoff-closeout.md\nday61-phase3-kickoff-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-61-big-upgrade-report.md\nintegrations-day61-phase3-kickoff-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 61 — Phase-3 kickoff:** set Phase-3 baseline and define ecosystem/trust KPIs.\n"
        "- **Day 62 — Community program setup:** publish office-hours cadence and participation rules.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day61-phase3-kickoff-closeout.md").write_text(
        d61._DAY61_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-61-big-upgrade-report.md").write_text("# Day 61 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day60-phase2-wrap-handoff-closeout-pack/day60-phase2-wrap-handoff-closeout-summary.json"
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
    board = root / "docs/artifacts/day60-phase2-wrap-handoff-closeout-pack/day60-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 60 delivery board",
                "- [ ] Day 60 Phase-2 wrap + handoff brief committed",
                "- [ ] Day 60 wrap reviewed with owner + backup",
                "- [ ] Day 60 risk ledger exported",
                "- [ ] Day 60 KPI scorecard snapshot exported",
                "- [ ] Day 61 execution priorities drafted from Day 60 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day61_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d61.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day61-phase3-kickoff-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day61_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d61.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day61-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day61-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day61-pack/day61-phase3-kickoff-closeout-summary.json").exists()
    assert (tmp_path / "artifacts/day61-pack/day61-phase3-kickoff-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/day61-pack/day61-phase3-kickoff-brief.md").exists()
    assert (tmp_path / "artifacts/day61-pack/day61-trust-ledger.csv").exists()
    assert (tmp_path / "artifacts/day61-pack/day61-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day61-pack/day61-execution-log.md").exists()
    assert (tmp_path / "artifacts/day61-pack/day61-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day61-pack/day61-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day61-pack/evidence/day61-execution-summary.json").exists()


def test_day61_strict_fails_without_day60(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day60-phase2-wrap-handoff-closeout-pack/day60-phase2-wrap-handoff-closeout-summary.json"
    ).unlink()
    assert d61.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day61_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day61-phase3-kickoff-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 61 Phase-3 kickoff closeout summary" in capsys.readouterr().out
