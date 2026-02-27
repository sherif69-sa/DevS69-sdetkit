from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day77_community_touchpoint_closeout as d77


def _seed_repo(root: Path) -> None:
    (root / "README.md").write_text(
        "docs/integrations-day77-community-touchpoint-closeout.md\nday77-community-touchpoint-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-77-big-upgrade-report.md\nintegrations-day77-community-touchpoint-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 76 — Contributor recognition board:** publish contributor spotlight and release credits model.\n"
        "- **Day 77 — Community touchpoint #1:** run first office-hours session and summarize outcomes.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day77-community-touchpoint-closeout.md").write_text(
        d77._DAY77_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-77-big-upgrade-report.md").write_text("# Day 77 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day76-contributor-recognition-closeout-pack/day76-contributor-recognition-closeout-summary.json"
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
    board = root / "docs/artifacts/day76-contributor-recognition-closeout-pack/day76-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 76 delivery board",
                "- [ ] Day 76 integration brief committed",
                "- [ ] Day 76 contributor recognition plan committed",
                "- [ ] Day 76 recognition credits ledger exported",
                "- [ ] Day 76 recognition KPI scorecard snapshot exported",
                "- [ ] Day 77 scale priorities drafted from Day 76 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    touchpoint_plan = root / ".day77-community-touchpoint-plan.json"
    touchpoint_plan.write_text(
        json.dumps(
            {
                "plan_id": "day77-community-touchpoint-001",
                "contributors": ["maintainers", "community-team"],
                "touchpoint_tracks": ["office-hours", "release-highlights"],
                "baseline": {"sessions": 1, "participants": 15},
                "target": {"sessions": 3, "participants": 40},
                "owner": "community-ops",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_day77_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d77.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day77-community-touchpoint-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day77_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d77.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day77-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day77-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day77-pack/day77-community-touchpoint-closeout-summary.json").exists()
    assert (tmp_path / "artifacts/day77-pack/day77-community-touchpoint-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/day77-pack/day77-integration-brief.md").exists()
    assert (tmp_path / "artifacts/day77-pack/day77-community-touchpoint-plan.md").exists()
    assert (tmp_path / "artifacts/day77-pack/day77-touchpoint-session-ledger.json").exists()
    assert (tmp_path / "artifacts/day77-pack/day77-touchpoint-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day77-pack/day77-execution-log.md").exists()
    assert (tmp_path / "artifacts/day77-pack/day77-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day77-pack/day77-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day77-pack/evidence/day77-execution-summary.json").exists()


def test_day77_strict_fails_without_day76(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day76-contributor-recognition-closeout-pack/day76-contributor-recognition-closeout-summary.json"
    ).unlink()
    assert d77.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day77_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day77-community-touchpoint-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 77 community touchpoint closeout summary" in capsys.readouterr().out
