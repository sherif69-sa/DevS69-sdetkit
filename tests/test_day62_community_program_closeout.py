from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day62_community_program_closeout as d62


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-day62-community-program-closeout.md\nday62-community-program-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-62-big-upgrade-report.md\nintegrations-day62-community-program-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 62 — Community program setup:** publish office-hours cadence and participation rules.\n"
        "- **Day 63 — Contributor onboarding activation:** launch orientation flow and ownership handoff loops.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day62-community-program-closeout.md").write_text(
        d62._DAY62_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-62-big-upgrade-report.md").write_text("# Day 62 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day61-phase3-kickoff-closeout-pack/day61-phase3-kickoff-closeout-summary.json"
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
    board = root / "docs/artifacts/day61-phase3-kickoff-closeout-pack/day61-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 61 delivery board",
                "- [ ] Day 61 Phase-3 kickoff brief committed",
                "- [ ] Day 61 kickoff reviewed with owner + backup",
                "- [ ] Day 61 trust ledger exported",
                "- [ ] Day 61 KPI scorecard snapshot exported",
                "- [ ] Day 62 community program priorities drafted from Day 61 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day62_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d62.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day62-community-program-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day62_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d62.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day62-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day62-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/day62-pack/day62-community-program-closeout-summary.json"
    ).exists()
    assert (tmp_path / "artifacts/day62-pack/day62-community-program-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/day62-pack/day62-community-launch-brief.md").exists()
    assert (tmp_path / "artifacts/day62-pack/day62-office-hours-cadence.md").exists()
    assert (tmp_path / "artifacts/day62-pack/day62-participation-policy.md").exists()
    assert (tmp_path / "artifacts/day62-pack/day62-moderation-runbook.md").exists()
    assert (tmp_path / "artifacts/day62-pack/day62-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day62-pack/day62-execution-log.md").exists()
    assert (tmp_path / "artifacts/day62-pack/day62-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day62-pack/day62-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day62-pack/evidence/day62-execution-summary.json").exists()


def test_day62_strict_fails_without_day61(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day61-phase3-kickoff-closeout-pack/day61-phase3-kickoff-closeout-summary.json"
    ).unlink()
    assert d62.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day62_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day62-community-program-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 62 community program closeout summary" in capsys.readouterr().out
